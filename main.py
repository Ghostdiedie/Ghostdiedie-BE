"""
Ghostdiedie Club Backend
FastAPI + Supabase + WebSocket
"""
import os
import random
import string
import json
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# ---------- Supabase  ----------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_KEY = os.getenv("API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL / SUPABASE_KEY 환경변수가 필요합니다 (.env 확인)")
if not API_KEY:
    raise RuntimeError("API_KEY 환경변수가 필요합니다 (.env 확인)")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- API Key 인증 ----------
api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(key: str = Depends(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

# ---------- FastAPI 앱 ----------
app = FastAPI(title="Ghostdiedie Club API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- 방 관리 (인메모리) ----------
rooms: dict[str, dict] = {}

def generate_room_code() -> str:
    """4자리 방 코드 생성"""
    while True:
        code = "".join(random.choices(string.ascii_uppercase, k=4))
        if code not in rooms:
            return code

# ---------- Pydantic 모델 ----------
class MatchCreate(BaseModel):
    player_name: str
    winner_character_id: int
    loser_character_id: int
    duration_seconds: int

class MatchResponse(BaseModel):
    match_id: str
    created_at: str

class RoomCreate(BaseModel):
    player_name: str
    character_id: int

class RoomJoin(BaseModel):
    player_name: str
    character_id: int

# ---------- 라우트 ----------
@app.get("/")
def root():
    return {"status": "ok", "service": "ghostdiedie-club"}

@app.get("/test")
def test_page():
    return FileResponse("test_ws.html")

@app.get("/api/characters")
def get_characters(_: str = Depends(verify_api_key)):
    """선택 가능한 캐릭터 전체 목록"""
    try:
        result = supabase.table("characters").select("*").execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/characters/{character_id}")
def get_character(character_id: int, _: str = Depends(verify_api_key)):
    """특정 캐릭터 상세 정보"""
    try:
        result = (
            supabase.table("characters")
            .select("*")
            .eq("id", character_id)
            .single()
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Character not found")
        return result.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/matches", response_model=MatchResponse)
def create_match(match: MatchCreate, _: str = Depends(verify_api_key)):
    """경기 결과 저장"""
    try:
        payload = {
            "player_name": match.player_name,
            "winner_character_id": match.winner_character_id,
            "loser_character_id": match.loser_character_id,
            "duration_seconds": match.duration_seconds,
        }
        result = supabase.table("matches").insert(payload).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Insert failed")
        row = result.data[0]
        return MatchResponse(match_id=str(row["id"]), created_at=str(row["created_at"]))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/leaderboard")
def get_leaderboard(limit: int = 10, _: str = Depends(verify_api_key)):
    """플레이어별 승수 랭킹"""
    try:
        result = (
            supabase.table("matches")
            .select("player_name")
            .execute()
        )
        counts = {}
        for row in result.data:
            name = row["player_name"]
            counts[name] = counts.get(name, 0) + 1
        ranked = sorted(
            [{"player_name": k, "wins": v} for k, v in counts.items()],
            key=lambda x: x["wins"],
            reverse=True,
        )
        return ranked[:limit]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------- 방 API ----------
@app.post("/api/rooms")
def create_room(data: RoomCreate, _: str = Depends(verify_api_key)):
    """방 생성 — 방 코드 반환"""
    code = generate_room_code()
    rooms[code] = {
        "status": "waiting",  # waiting / playing / finished
        "players": [
            {"name": data.player_name, "character_id": data.character_id, "ws": None}
        ],
    }
    return {"room_code": code, "status": "waiting"}

@app.post("/api/rooms/{room_code}/join")
def join_room(room_code: str, data: RoomJoin, _: str = Depends(verify_api_key)):
    """방 참가"""
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[room_code]
    if len(room["players"]) >= 2:
        raise HTTPException(status_code=400, detail="Room is full")
    room["players"].append(
        {"name": data.player_name, "character_id": data.character_id, "ws": None}
    )
    room["status"] = "playing"
    return {"room_code": room_code, "status": "playing"}

@app.get("/api/rooms/{room_code}")
def get_room(room_code: str, _: str = Depends(verify_api_key)):
    """방 정보 조회"""
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[room_code]
    return {
        "room_code": room_code,
        "status": room["status"],
        "players": [
            {"name": p["name"], "character_id": p["character_id"]}
            for p in room["players"]
        ],
    }

# ---------- WebSocket 대전 ----------
@app.websocket("/ws/{room_code}")
async def websocket_game(websocket: WebSocket, room_code: str):
    room_code = room_code.upper()
    if room_code not in rooms:
        await websocket.close(code=4004, reason="Room not found")
        return

    room = rooms[room_code]
    await websocket.accept()

    # 빈 슬롯에 WebSocket 연결
    player_index = None
    for i, p in enumerate(room["players"]):
        if p["ws"] is None:
            p["ws"] = websocket
            player_index = i
            break

    if player_index is None:
        await websocket.close(code=4003, reason="Room is full")
        return

    # 상대에게 입장 알림
    opponent_index = 1 - player_index
    if len(room["players"]) > opponent_index and room["players"][opponent_index]["ws"]:
        await room["players"][opponent_index]["ws"].send_json({
            "type": "opponent_joined",
            "player_name": room["players"][player_index]["name"],
            "character_id": room["players"][player_index]["character_id"],
        })

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # 상대에게 메시지 전달 (움직임, 공격, 등)
            if len(room["players"]) > opponent_index and room["players"][opponent_index]["ws"]:
                await room["players"][opponent_index]["ws"].send_json(message)
    except WebSocketDisconnect:
        room["players"][player_index]["ws"] = None
        # 상대에게 퇴장 알림
        if len(room["players"]) > opponent_index and room["players"][opponent_index]["ws"]:
            await room["players"][opponent_index]["ws"].send_json({
                "type": "opponent_left",
            })
        # 둘 다 나가면 방 삭제
        if all(p["ws"] is None for p in room["players"]):
            del rooms[room_code]
