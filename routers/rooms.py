from fastapi import APIRouter, HTTPException, Depends
from core.auth import verify_api_key
from models.schemas import RoomCreate, RoomJoin, RoomResponse, RoomStatus, PlayerState
from services.room_manager import rooms, generate_room_code

router = APIRouter(tags=["Rooms"])


@router.post("/api/rooms", response_model=RoomResponse)
def create_room(data: RoomCreate, _: str = Depends(verify_api_key)):
    """방 생성 — 방 코드 반환"""
    code = generate_room_code()
    rooms[code] = {
        "status": RoomStatus.WAITING,
        "players": [
            {
                "name": data.player_name,
                "character_id": data.character_id,
                "profile_image_url": data.profile_image_url,
                "hp": 100,
                "special_gauge": 0,
                "ws": None,
            }
        ],
    }
    return RoomResponse(
        room_code=code,
        status=RoomStatus.WAITING,
        players=[PlayerState(**{k: v for k, v in rooms[code]["players"][0].items() if k != "ws"})],
    )


@router.post("/api/rooms/{room_code}/join", response_model=RoomResponse)
def join_room(room_code: str, data: RoomJoin, _: str = Depends(verify_api_key)):
    """방 참가"""
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[room_code]
    if len(room["players"]) >= 2:
        raise HTTPException(status_code=400, detail="Room is full")
    room["players"].append(
        {
            "name": data.player_name,
            "character_id": data.character_id,
            "profile_image_url": data.profile_image_url,
            "hp": 100,
            "special_gauge": 0,
            "ws": None,
        }
    )
    # HTTP 참가 완료 → ready (실제 playing은 WS 연결 후 websocket.py에서 변경)
    room["status"] = RoomStatus.READY
    return RoomResponse(
        room_code=room_code,
        status=RoomStatus.READY,
        players=[
            PlayerState(**{k: v for k, v in p.items() if k != "ws"})
            for p in room["players"]
        ],
    )


@router.get("/api/rooms/{room_code}", response_model=RoomResponse)
def get_room(room_code: str, _: str = Depends(verify_api_key)):
    """방 정보 조회"""
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[room_code]
    return RoomResponse(
        room_code=room_code,
        status=room["status"],
        players=[
            PlayerState(**{k: v for k, v in p.items() if k != "ws"})
            for p in room["players"]
        ],
    )
