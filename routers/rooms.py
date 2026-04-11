import time
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from core.auth import verify_api_key
from services.room_manager import rooms, generate_room_code, ROOM_EXPIRE_SECONDS
from services.user_manager import get_user

router = APIRouter(tags=["Rooms"])
logger = logging.getLogger("ghostdiedie.rooms")


def _user_info(player: dict, role: str) -> dict:
    """Return clean user info for response."""
    return {
        "user_id": player["user_id"],
        "name": player["name"],
        "profile_image_url": player["profile_image_url"],
        "role": role,  # "owner" or "guest"
    }


@router.get("/api/room/create")
def create_room(
    user_id: str = Query(...),
    character_id: int = Query(...),
    _: str = Depends(verify_api_key),
):
    """Owner creates a room. Returns room code and owner info."""
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Register first.")

    code = generate_room_code()
    rooms[code] = {
        "status": "waiting",
        "created_at": time.time(),
        "owner": {
            **user,
            "character_id": character_id,
            "confirmed": False,
            "ws": None,
        },
        "guest": None,
    }
    logger.info("room created code=%s owner=%s character_id=%s", code, user_id, character_id)

    return {
        "code": code,
        "owner": _user_info(user, "owner"),
        "expires_in": ROOM_EXPIRE_SECONDS,
    }


@router.get("/api/room/join")
def join_room(
    code: str = Query(...),
    user_id: str = Query(...),
    character_id: int = Query(...),
    _: str = Depends(verify_api_key),
):
    """Guest joins a room by code. Returns both players' info."""
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Register first.")

    if code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    room = rooms[code]

    if time.time() - room["created_at"] > ROOM_EXPIRE_SECONDS and room["status"] != "playing":
        del rooms[code]
        raise HTTPException(status_code=410, detail="Room expired")

    if room["guest"] is not None:
        raise HTTPException(status_code=400, detail="Room is full")

    room["guest"] = {
        **user,
        "character_id": character_id,
        "confirmed": False,
        "ws": None,
    }
    room["status"] = "ready"
    logger.info("room joined code=%s guest=%s character_id=%s", code, user_id, character_id)

    return {
        "success": True,
        "code": code,
        "owner": _user_info(room["owner"], "owner"),
        "guest": _user_info(user, "guest"),
    }


@router.get("/api/room/confirm")
def confirm_room(
    code: str = Query(...),
    user_id: str = Query(...),
    _: str = Depends(verify_api_key),
):
    """Player confirms readiness. When both confirm, game can start."""
    if code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    room = rooms[code]

    if room["guest"] is None:
        raise HTTPException(status_code=400, detail="Waiting for guest to join")

    if room["owner"]["user_id"] == user_id:
        room["owner"]["confirmed"] = True
    elif room["guest"]["user_id"] == user_id:
        room["guest"]["confirmed"] = True
    else:
        raise HTTPException(status_code=403, detail="You are not in this room")

    both_confirmed = room["owner"]["confirmed"] and room["guest"]["confirmed"]

    if both_confirmed:
        room["status"] = "confirmed"
    logger.info(
        "room confirm code=%s user=%s owner_confirmed=%s guest_confirmed=%s",
        code,
        user_id,
        room["owner"]["confirmed"],
        room["guest"]["confirmed"],
    )

    return {
        "confirmed": True,
        "both_confirmed": both_confirmed,
    }


@router.get("/api/room/character")
def set_room_character(
    code: str = Query(...),
    user_id: str = Query(...),
    character_id: int = Query(...),
    _: str = Depends(verify_api_key),
):
    """Update the selected character before WebSocket game start."""
    if code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    room = rooms[code]

    if room["owner"]["user_id"] == user_id:
        room["owner"]["character_id"] = character_id
    elif room["guest"] and room["guest"]["user_id"] == user_id:
        room["guest"]["character_id"] = character_id
    else:
        raise HTTPException(status_code=403, detail="You are not in this room")
    logger.info("room character updated code=%s user=%s character_id=%s", code, user_id, character_id)

    return {
        "updated": True,
        "character_id": character_id,
    }


@router.get("/api/room/status")
def get_room_status(
    code: str = Query(...),
    _: str = Depends(verify_api_key),
):
    """Poll room state."""
    if code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    room = rooms[code]
    elapsed = time.time() - room["created_at"]
    remaining = max(0, ROOM_EXPIRE_SECONDS - int(elapsed))

    if remaining == 0 and room["status"] not in ("playing", "confirmed"):
        del rooms[code]
        raise HTTPException(status_code=410, detail="Room expired")

    result = {
        "code": code,
        "status": room["status"],
        "owner": _user_info(room["owner"], "owner"),
        "both_confirmed": False,
        "expires_in": remaining,
    }

    if room["guest"]:
        result["guest"] = _user_info(room["guest"], "guest")
        result["both_confirmed"] = room["owner"]["confirmed"] and room["guest"]["confirmed"]
    else:
        result["guest"] = None

    return result
