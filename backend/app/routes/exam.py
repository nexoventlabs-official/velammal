import os
import uuid
import json
import shutil
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.config import settings
from app.models import ExamConfig, ExamResult, ProcessingResponse, get_exam_format
from app.services.google_sheets import sheets_service
from app.services.student_db import student_db
from app.services.ocr_engine import ocr_engine
from app.services import cloudinary_service

router = APIRouter(prefix="/api/exam", tags=["Exam Processing"])

# In-memory session store for active scanning sessions
active_sessions = {}


@router.get("/exam-format/{total_marks}")
async def get_format(total_marks: int):
    """Return the dynamic exam section structure for given total marks."""
    fmt = get_exam_format(total_marks)
    return {"success": True, "format": fmt}


@router.post("/start-session")
async def start_exam_session(config: ExamConfig):
    """Start a new exam scanning session with exam configuration."""
    fmt = get_exam_format(config.total_marks)
    config.exam_type = fmt["exam_type"]
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = {
        "config": config.model_dump(),
        "format": fmt,
        "students": [],
        "current_student_pages": [],
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "result_sheet": config.result_sheet,
        "reg_prefix": config.reg_prefix,
    }
    return {
        "success": True,
        "session_id": session_id,
        "message": f"Session started for {config.subject_name} ({config.subject_code})",
        "config": config.model_dump(),
        "format": fmt,
    }


@router.post("/upload-pages/{session_id}")
async def upload_exam_pages(
    session_id: str,
    files: List[UploadFile] = File(...),
):
    """Upload exam sheet pages for a student (multiple pages per student)."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = active_sessions[session_id]
    session_dir = os.path.join(settings.UPLOAD_DIR, session_id)
    student_id = str(uuid.uuid4())[:8]
    student_dir = os.path.join(session_dir, student_id)
    os.makedirs(student_dir, exist_ok=True)

    saved_paths = []
    cloudinary_ids = []
    for i, file in enumerate(files):
        ext = os.path.splitext(file.filename)[1] or ".png"
        file_path = os.path.join(student_dir, f"page_{i+1}{ext}")
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        saved_paths.append(file_path)

        # Upload to Cloudinary for temporary storage
        cloud_result = cloudinary_service.upload_image(file_path, folder=f"examscan/{session_id}")
        if cloud_result["public_id"]:
            cloudinary_ids.append(cloud_result["public_id"])

    session["current_student_pages"] = saved_paths
    session["current_cloudinary_ids"] = cloudinary_ids

    # Process OCR on the uploaded pages (pass exam format for Groq Vision)
    exam_format = session.get("format", None)
    reg_prefix = session.get("reg_prefix", "")
    ocr_result = ocr_engine.process_exam_sheet(saved_paths, exam_format=exam_format, reg_prefix=reg_prefix)

    # Delete from Cloudinary after OCR is done — images no longer needed
    cloudinary_service.delete_images(cloudinary_ids)

    # Clean up local files too
    for p in saved_paths:
        try:
            os.remove(p)
        except Exception:
            pass

    return {
        "success": True,
        "student_upload_id": student_id,
        "pages_uploaded": len(saved_paths),
        "ocr_result": {
            "registration_number": ocr_result.get("registration_number"),
            "marks_obtained": ocr_result.get("marks_obtained", 0),
            "confidence": ocr_result.get("confidence", 0),
            "page_count": ocr_result.get("page_count", len(saved_paths)),
            "engine": ocr_result.get("engine", "unknown"),
            "part_a_marks": ocr_result.get("part_a_marks", {}),
            "part_bc_marks": ocr_result.get("part_bc_marks", {}),
            "course_outcomes": ocr_result.get("course_outcomes", {}),
            "part_a_total": ocr_result.get("part_a_total", 0),
            "part_bc_total": ocr_result.get("part_bc_total", 0),
            "grand_total": ocr_result.get("grand_total", 0),
            "written_totals": ocr_result.get("written_totals", {}),
        },
        "message": "Pages uploaded and processed successfully",
    }


@router.post("/complete-student/{session_id}")
async def complete_student_marks(
    session_id: str,
    register_number: str = Form(...),
    marks_obtained: int = Form(...),
    part_a_total: int = Form(0),
    part_bc_total: int = Form(0),
    section_marks_json: str = Form("{}"),
):
    """
    Complete processing for one student.
    Accepts section-wise marks (Part A, Part B&C, Course Outcomes).
    Looks up student in main DB, saves result to results DB.
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = active_sessions[session_id]
    config = session["config"]

    # Look up student in MongoDB (uploaded Excel data)
    student = student_db.find_student(session_id, register_number)

    if not student:
        student_data = {
            "register_number": register_number,
            "student_name": "Unknown",
            "email": "N/A",
            "section": config["section"],
            "branch": config["branch"],
            "year": config["year"],
        }
    else:
        student_data = {
            "register_number": student.get("register_number", register_number),
            "student_name": student.get("student_name", "Unknown"),
            "email": student.get("email", "N/A"),
            "section": student.get("section", config["section"]),
            "branch": student.get("branch", config["branch"]),
            "year": student.get("year", config["year"]),
        }

    # Determine pass/fail
    status = "PASS" if marks_obtained >= config["pass_marks"] else "FAIL"

    # Create result record with section-wise data
    result = ExamResult(
        register_number=register_number,
        student_name=student_data["student_name"],
        email=student_data["email"],
        section=student_data["section"],
        academic_year=config.get("academic_year", ""),
        year=config.get("year", ""),
        subject_name=config["subject_name"],
        subject_code=config["subject_code"],
        total_marks=config["total_marks"],
        marks_obtained=marks_obtained,
        pass_marks=config["pass_marks"],
        status=status,
        part_a_total=part_a_total,
        part_bc_total=part_bc_total,
        section_marks_json=section_marks_json,
    )

    # Save to results DB (Google Sheet) — main sheet + specific worksheet
    saved = sheets_service.save_result(result)

    # Also save to the specific result worksheet if one was selected
    result_sheet = session.get("result_sheet", "")
    if result_sheet:
        sheets_service.save_result_to_worksheet(result_sheet, result)

    # Track in session
    session["students"].append(result.model_dump())

    return {
        "success": True,
        "result": result.model_dump(),
        "saved_to_db": saved,
        "message": f"Marks saved for {register_number} - {student_data['student_name']} ({status})",
    }


@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """Get current session info and processed students."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = active_sessions[session_id]
    return {
        "success": True,
        "session_id": session_id,
        "config": session["config"],
        "students_processed": len(session["students"]),
        "students": session["students"],
        "status": session["status"],
    }


@router.post("/end-session/{session_id}")
async def end_exam_session(session_id: str):
    """End the scanning session."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = active_sessions[session_id]
    session["status"] = "completed"

    # Clean up temporary student data from MongoDB
    student_db.cleanup_session(session_id)

    total = len(session["students"])
    passed = sum(1 for s in session["students"] if s["status"] == "PASS")

    return {
        "success": True,
        "message": "Session completed",
        "summary": {
            "total_students": total,
            "passed": passed,
            "failed": total - passed,
            "subject": session["config"]["subject_name"],
        },
    }


@router.get("/sessions")
async def list_sessions():
    """List all scanning sessions."""
    sessions_list = []
    for sid, session in active_sessions.items():
        sessions_list.append({
            "session_id": sid,
            "config": session["config"],
            "students_processed": len(session["students"]),
            "status": session["status"],
            "created_at": session["created_at"],
        })
    return {"success": True, "sessions": sessions_list}
