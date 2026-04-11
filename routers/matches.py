from fastapi import APIRouter, HTTPException, Depends
from core.config import supabase
from core.auth import verify_api_key
from models.schemas import MatchCreate, MatchResponse

router = APIRouter()


@router.post("/api/matches", response_model=MatchResponse)
def create_match(match: MatchCreate, _: str = Depends(verify_api_key)):
    """경기 결과 저장"""
    try:
        payload = {
            "room_code": match.room_code,
            "winner_name": match.winner_name,
            "loser_name": match.loser_name,
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

@router.get("/api/leaderboard")
def get_leaderboard(limit: int = 10, _: str = Depends(verify_api_key)):
    """플레이어별 승수 랭킹"""
    try:
        result = (
            supabase.table("matches")
            .select("winner_name")
            .execute()
        )
        counts = {}
        for row in result.data:
            name = row["winner_name"]
            counts[name] = counts.get(name, 0) + 1
        ranked = sorted(
            [{"player_name": k, "wins": v} for k, v in counts.items()],
            key=lambda x: x["wins"],
            reverse=True,
        )
        return ranked[:limit]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
