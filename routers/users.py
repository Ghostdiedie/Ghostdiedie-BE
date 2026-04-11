from fastapi import APIRouter, HTTPException, Depends, Query
from core.auth import verify_api_key
from services.user_manager import create_user
from routers.face import faces

router = APIRouter(tags=["Users"])


@router.get("/api/user/register")
def register_user(
    name: str = Query(...),
    face_id: str = Query(...),
    _: str = Depends(verify_api_key),
):
    """Register a user with name + face_id (from POST /api/face). Returns user_id."""
    face_url = faces.get(face_id)
    if not face_url:
        raise HTTPException(status_code=404, detail="face_id not found. Upload face first.")

    user = create_user(name, face_url)
    return {
        "status": "ok",
        "user_id": user["user_id"],
        "name": user["name"],
        "profile_image_url": user["profile_image_url"],
    }
