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
# Supports both raw JSON and base64-encoded JSON
if settings.RESULTS_CREDENTIALS_JSON:
    creds_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), settings.RESULTS_CREDENTIALS_FILE)
    try:
        import base64
        creds_str = settings.RESULTS_CREDENTIALS_JSON.strip()
        
        # Try base64 decode first (preferred for Render to avoid escape issues)
        try:
            decoded = base64.b64decode(creds_str).decode('utf-8')
            creds_data = json.loads(decoded)
            print("✓ Decoded base64 credentials")
        except:
            # Fall back to raw JSON
            creds_data = json.loads(creds_str)
            print("✓ Parsed raw JSON credentials")
        
        with open(creds_path, "w") as f:
            json.dump(creds_data, f)
        print(f"✓ Wrote Google credentials to {creds_path}")
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid RESULTS_CREDENTIALS_JSON: {e}")
    except Exception as e:
        print(f"ERROR: Could not write credentials file: {e}")
