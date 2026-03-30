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
    """Get all results with optional filters."""
    results = sheets_service.get_results_by_filter(section, academic_year, subject_code)
    return {"success": True, "results": results, "total": len(results)}


@router.get("/student/{register_number}")
async def get_student_results(register_number: str):
    """Get all results for a specific student."""
    all_results = sheets_service.get_all_results()
    student_results = [
        r for r in all_results
        if str(r.get("RegisterNumber", "")).upper() == register_number.upper()
    ]
    return {"success": True, "results": student_results, "total": len(student_results)}


@router.get("/dashboard")
async def get_dashboard_stats(
    section: Optional[str] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_code: Optional[str] = Query(None),
):
    """Get dashboard statistics with optional filters."""
    stats = sheets_service.get_dashboard_stats(section, academic_year, subject_code)
    return {"success": True, "stats": stats}
