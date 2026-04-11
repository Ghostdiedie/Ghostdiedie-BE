import uuid
from core.config import supabase


def create_user(name: str, profile_image_url: str | None = None) -> dict:
    """Create a user in Supabase and return user info."""
    user_id = uuid.uuid4().hex[:12]
    row = {
        "id": user_id,
        "name": name,
        "profile_image_url": profile_image_url,
    }
    result = supabase.table("users").insert(row).execute()
    if not result.data:
        raise Exception("Failed to create user")
    return {
        "user_id": user_id,
        "name": name,
        "profile_image_url": profile_image_url,
    }


def get_user(user_id: str) -> dict | None:
    """Fetch a user from Supabase by id."""
    result = supabase.table("users").select("*").eq("id", user_id).execute()
    if not result.data:
        return None
    row = result.data[0]
    return {
        "user_id": row["id"],
        "name": row["name"],
        "profile_image_url": row.get("profile_image_url"),
    }
