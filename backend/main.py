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
    return {"status": "healthy", "service": "ExamScan AI"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
