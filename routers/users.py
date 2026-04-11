import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from core.auth import verify_api_key
from services.user_manager import create_user
from routers.face import faces

router = APIRouter(tags=["Users"])
logger = logging.getLogger("ghostdiedie.users")


@router.get("/api/user/register")
def register_user(
    name: str = Query(...),
    face_id: str = Query(default=""),
    _: str = Depends(verify_api_key),
):
    """Register a user with name + face_id (from POST /api/face). Returns user_id."""
    face_url = faces.get(face_id) if face_id else None

    user = create_user(name, face_url)
    logger.info("registered user user_id=%s name=%s face_id=%s", user["user_id"], name, face_id or "(skipped)")
    return {
        "status": "ok",
        "user_id": user["user_id"],
        "name": user["name"],
        "profile_image_url": user["profile_image_url"],
    }
