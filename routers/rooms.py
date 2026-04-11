import time
from fastapi import APIRouter, HTTPException, Depends, Query
from core.auth import verify_api_key
from models.schemas import RoomResponse, RoomStatus, PlayerState
from services.room_manager import rooms, generate_room_code, ROOM_EXPIRE_SECONDS
from services.combat import get_character_stats

router = APIRouter(tags=["Rooms"])


@router.get("/api/room/create", response_model=RoomResponse)
def create_room(
    player_name: str = Query(...),
    character_id: int = Query(...),
    profile_image_url: str = Query(None),
    _: str = Depends(verify_api_key),
):
    """Create a room and return its 8-digit room code."""
    code = generate_room_code()
    stats = get_character_stats(character_id)
    rooms[code] = {
        "status": RoomStatus.WAITING,
        "created_at": time.time(),
        "players": [
            {
                "name": player_name,
                "character_id": character_id,
                "profile_image_url": profile_image_url,
                "hp": stats["hp"],
                "special_gauge": stats["special_gauge"],
                "ws": None,
                "confirmed": False,
            }
        ],
    }

    return {
        "room_code": code,
        "status": RoomStatus.WAITING,
        "players": [
            PlayerState(
                name=player_name,
                character_id=character_id,
                profile_image_url=profile_image_url,
                hp=stats["hp"],
                special_gauge=stats["special_gauge"],
            )
        ],
    }


@router.get("/api/room/join")
def join_room(
    code: str = Query(...),
    player_name: str = Query(...),
    character_id: int = Query(...),
    profile_image_url: str = Query(None),
    _: str = Depends(verify_api_key),
):
    """Join an existing room by code. Returns success."""
    if code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[code]
    if time.time() - room.get("created_at", 0) > ROOM_EXPIRE_SECONDS:
        del rooms[code]
        raise HTTPException(status_code=410, detail="Room has expired. Please create a new room.")
    if len(room["players"]) >= 2:
        raise HTTPException(status_code=400, detail="Room is full")

    stats = get_character_stats(character_id)
    room["players"].append(
        {
            "name": player_name,
            "character_id": character_id,
            "profile_image_url": profile_image_url,
            "hp": stats["hp"],
            "special_gauge": stats["special_gauge"],
            "ws": None,
            "confirmed": False,
        }
    )
    room["status"] = RoomStatus.READY

    return {"success": True, "room_code": code, "message": "Joined room successfully"}


@router.get("/api/room/confirm")
def confirm_room(
    code: str = Query(...),
    player_index: int = Query(..., ge=0, le=1),
    _: str = Depends(verify_api_key),
):
    """
    Confirm readiness for a player.
    Both players must call this. When both confirm, game can start.
    """
    if code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[code]
    if len(room["players"]) < 2:
        raise HTTPException(status_code=400, detail="Waiting for opponent to join")
    if player_index >= len(room["players"]):
        raise HTTPException(status_code=400, detail="Invalid player_index")

    room["players"][player_index]["confirmed"] = True

    both_confirmed = all(p["confirmed"] for p in room["players"])

    if both_confirmed:
        room["status"] = RoomStatus.PLAYING

    return {
        "success": True,
        "room_code": code,
        "player_index": player_index,
        "confirmed": True,
        "both_confirmed": both_confirmed,
        "message": "Game starting!" if both_confirmed else "Waiting for opponent to confirm",
    }


@router.get("/api/room/status")
def get_room_status(
    code: str = Query(...),
    _: str = Depends(verify_api_key),
):
    """Check room status (for polling confirm state, etc.)."""
    if code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[code]
    elapsed = time.time() - room.get("created_at", time.time())
    remaining = max(0, ROOM_EXPIRE_SECONDS - int(elapsed))

    if remaining == 0 and room.get("status") != RoomStatus.PLAYING:
        del rooms[code]
        raise HTTPException(status_code=410, detail="Room has expired.")

    players = [
        {
            "name": p["name"],
            "character_id": p["character_id"],
            "profile_image_url": p.get("profile_image_url"),
            "confirmed": p.get("confirmed", False),
        }
        for p in room["players"]
    ]

    both_confirmed = len(room["players"]) == 2 and all(p.get("confirmed") for p in room["players"])

    return {
        "room_code": code,
        "status": room["status"],
        "players": players,
        "both_confirmed": both_confirmed,
        "expires_in_seconds": remaining,
    }
