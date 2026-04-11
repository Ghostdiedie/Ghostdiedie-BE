from fastapi import APIRouter, HTTPException, Depends
from core.config import supabase
from core.auth import verify_api_key

router = APIRouter()


@router.get("/api/characters")
def get_characters(_: str = Depends(verify_api_key)):
    """선택 가능한 캐릭터 전체 목록"""
    try:
        result = supabase.table("characters").select("*").execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/characters/{character_id}")
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
