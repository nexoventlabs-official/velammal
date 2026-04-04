from typing import Optional
from fastapi import APIRouter, Query
from app.services.google_sheets import sheets_service

router = APIRouter(prefix="/api/results", tags=["Results"])


@router.get("/")
async def get_all_results(
    section: Optional[str] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_code: Optional[str] = Query(None),
):
    results = sheets_service.get_results_by_filter(section, academic_year, subject_code)
    return {"success": True, "results": results, "total": len(results)}


@router.get("/student/{register_number}")
async def get_student_results(register_number: str):
    """Get all results for a specific student across all subjects."""
    all_results = sheets_service.get_all_results()
    student_results = [
        r for r in all_results
        if str(r.get("RegisterNumber", "")).upper() == register_number.upper()
    ]

    # Build summary
    total_subjects = len(student_results)
    total_pass = sum(1 for r in student_results if str(r.get("Status", "")).upper() == "PASS")
    marks_list = [int(r.get("MarksObtained", 0) or 0) for r in student_results]
    avg_marks = round(sum(marks_list) / len(marks_list), 2) if marks_list else 0

    # CO aggregation across subjects
    co_totals = {}
    for co in ["CO1", "CO2", "CO3", "CO4", "CO5"]:
        vals = [int(r.get(co, 0) or 0) for r in student_results if r.get(co)]
        if vals:
            co_totals[co] = round(sum(vals) / len(vals), 1)

    student_info = {}
    if student_results:
        first = student_results[0]
        student_info = {
            "RegisterNumber": first.get("RegisterNumber", ""),
            "StudentName": first.get("StudentName", ""),
            "Section": first.get("Section", ""),
            "Branch": first.get("Branch", ""),
            "Year": first.get("Year", ""),
            "AcademicYear": first.get("AcademicYear", ""),
        }

    return {
        "success": True,
        "student": student_info,
        "results": student_results,
        "summary": {
            "total_subjects": total_subjects,
            "passed": total_pass,
            "failed": total_subjects - total_pass,
            "average_marks": avg_marks,
            "highest": max(marks_list) if marks_list else 0,
            "lowest": min(marks_list) if marks_list else 0,
            "co_averages": co_totals,
        },
        "total": total_subjects,
    }


@router.get("/dashboard")
async def get_dashboard_stats(
    section: Optional[str] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_code: Optional[str] = Query(None),
):
    stats = sheets_service.get_dashboard_stats(section, academic_year, subject_code)
    return {"success": True, "stats": stats}


@router.get("/sheets")
async def list_sheets_with_stats():
    """List all result sheets with basic stats."""
    sheets = sheets_service.list_results_worksheets()
    return {"success": True, "sheets": sheets, "total": len(sheets)}


@router.get("/sheets/{sheet_name}/results")
async def get_sheet_results(sheet_name: str):
    """Get all student results from a specific sheet."""
    results = sheets_service.get_sheet_results(sheet_name)
    return {"success": True, "results": results, "total": len(results)}


@router.get("/sheets/{sheet_name}/stats")
async def get_sheet_stats(sheet_name: str):
    """Get pass/fail/average stats for a specific sheet."""
    stats = sheets_service.get_sheet_stats(sheet_name)
    return {"success": True, "stats": stats}
