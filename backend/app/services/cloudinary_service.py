"""Cloudinary service for temporary scan image storage."""
import cloudinary
import cloudinary.uploader
from typing import List
from app.config import settings

# Configure on import
if settings.CLOUDINARY_CLOUD_NAME:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )
    CLOUDINARY_AVAILABLE = True
    print("Cloudinary configured")
else:
    CLOUDINARY_AVAILABLE = False
    print("WARNING: Cloudinary not configured")


def upload_image(file_path: str, folder: str = "examscan") -> dict:
    """Upload an image to Cloudinary. Returns {public_id, url}."""
    if not CLOUDINARY_AVAILABLE:
        return {"public_id": None, "url": None}
    try:
        result = cloudinary.uploader.upload(file_path, folder=folder)
        return {"public_id": result["public_id"], "url": result["secure_url"]}
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return {"public_id": None, "url": None}


def delete_images(public_ids: List[str]):
    """Delete images from Cloudinary after marks are extracted."""
    if not CLOUDINARY_AVAILABLE or not public_ids:
        return
    for pid in public_ids:
        if pid:
            try:
                cloudinary.uploader.destroy(pid)
            except Exception as e:
                print(f"Cloudinary delete error for {pid}: {e}")
