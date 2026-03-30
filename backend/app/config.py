import os
import json
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # MongoDB
    MONGODB_URL: str = os.getenv("MONGODB_URL", "")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "examscan")

    # Results DB (marks-sheets service account)
    RESULTS_CREDENTIALS_FILE: str = os.getenv("RESULTS_CREDENTIALS_FILE", "results_credentials.json")
    RESULTS_CREDENTIALS_JSON: str = os.getenv("RESULTS_CREDENTIALS_JSON", "")  # JSON string for Render
    RESULTS_DB_SHEET_ID: str = os.getenv("RESULTS_DB_SHEET_ID", "")

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

    class Config:
        env_file = ".env"


settings = Settings()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# If RESULTS_CREDENTIALS_JSON env var is set (Render deployment),
# write it to a file so gspread can use it
if settings.RESULTS_CREDENTIALS_JSON:
    creds_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), settings.RESULTS_CREDENTIALS_FILE)
    if not os.path.exists(creds_path):
        try:
            with open(creds_path, "w") as f:
                f.write(settings.RESULTS_CREDENTIALS_JSON)
            print(f"Wrote credentials from env to {creds_path}")
        except Exception as e:
            print(f"WARNING: Could not write credentials file: {e}")
