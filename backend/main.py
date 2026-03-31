import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import exam, students, results, scanner

app = FastAPI(
    title="ExamScan AI - Exam Sheet Scanner & Grading System",
    description="AI-powered exam paper scanning, OCR-based marks extraction, and automated grading system",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(exam.router)
app.include_router(students.router)
app.include_router(results.router)
app.include_router(scanner.router)


@app.get("/")
async def root():
    return {
        "message": "ExamScan AI API is running",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/api/health")
async def health_check():
    from app.services.google_sheets import sheets_service
    from app.services.student_db import student_db
    
    spreadsheet_name = None
    try:
        if sheets_service.spreadsheet:
            spreadsheet_name = sheets_service.spreadsheet.title
    except:
        pass
    
    return {
        "status": "healthy",
        "service": "ExamScan AI",
        "connections": {
            "spreadsheet": sheets_service.spreadsheet is not None,
            "spreadsheet_name": spreadsheet_name,
            "results_db": sheets_service.results_db is not None,
            "results_client": sheets_service.results_client is not None,
            "mongodb": student_db.db is not None,
            "sheet_id_configured": bool(settings.RESULTS_DB_SHEET_ID),
            "credentials_configured": bool(settings.RESULTS_CREDENTIALS_JSON) or bool(settings.RESULTS_CREDENTIALS_FILE),
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
