from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import Response
from core.config import supabase, SUPABASE_URL
from core.auth import verify_api_key

router = APIRouter(tags=["Characters"])

BUCKET = "character-images"


@router.get("/api/characters")
def get_characters(_: str = Depends(verify_api_key)):
    """Return all selectable characters with stats and image URLs."""
    try:
        result = supabase.table("characters").select("*").execute()
        for char in result.data:
            char["image_url"] = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{char['id']}.webp"
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/characters/{character_id}")
def get_character(character_id: int, _: str = Depends(verify_api_key)):
    """Return details for one character, including the image URL."""
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
        result.data["image_url"] = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{character_id}.webp"
        return result.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/characters/{character_id}/image")
async def upload_character_image(
    character_id: int,
    file: UploadFile = File(...),
    _: str = Depends(verify_api_key),
):
    """Upload a character image in WebP format and overwrite any existing file."""
    # Confirm that the character exists
    result = supabase.table("characters").select("id").eq("id", character_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Character not found")

    content = await file.read()
    path = f"{character_id}.webp"

    try:
        # Try to remove the existing file first; ignore missing-file errors
        try:
            supabase.storage.from_(BUCKET).remove([path])
        except Exception:
            pass

        supabase.storage.from_(BUCKET).upload(
            path,
            content,
            file_options={"content-type": "image/webp"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    image_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"
    return {"character_id": character_id, "image_url": image_url}


@router.get("/api/characters/{character_id}/image")
def get_character_image(character_id: int):
    """Return a character image without requiring authentication."""
    path = f"{character_id}.webp"
    try:
        data = supabase.storage.from_(BUCKET).download(path)
        return Response(content=data, media_type="image/webp")
    except Exception:
        raise HTTPException(status_code=404, detail="Image not found")
