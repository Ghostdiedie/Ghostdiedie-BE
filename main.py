"""
3D Tekken Game Backend
FastAPI + Supabase
"""
import os
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# ---------- Supabase 클라이언트 ----------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # anon key 사용

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL / SUPABASE_KEY 환경변수가 필요합니다 (.env 확인)")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- FastAPI 앱 ----------
app = FastAPI(title="Ghostdiedie Club API", version="0.1.0")

# React Native에서 호출 가능하도록 CORS 전부 허용 (해커톤용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Pydantic 모델 (요청/응답 스펙) ----------
class MatchCreate(BaseModel):
    player_name: str
    winner_character_id: int
    loser_character_id: int
    duration_seconds: int

class MatchResponse(BaseModel):
    match_id: str
    created_at: str

# ---------- 라우트 ----------
@app.get("/")
def root():
    return {"status": "ok", "service": "ghostdiedie-club"}

@app.get("/api/characters")
def get_characters():
    """선택 가능한 캐릭터 전체 목록"""
    try:
        result = supabase.table("characters").select("*").execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/characters/{character_id}")
def get_character(character_id: int):
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
def create_match(match: MatchCreate):
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
def get_leaderboard(limit: int = 10):
    """플레이어별 승수 랭킹"""
    try:
        result = (
            supabase.table("matches")
            .select("player_name")
            .execute()
        )
        # 플레이어별 승수 집계 (간단히 파이썬에서 처리)
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
