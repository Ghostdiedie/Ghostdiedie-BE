import uuid

users: dict[str, dict] = {}


def create_user(name: str, profile_image_url: str | None = None) -> dict:
    """Create a user and return user info with id."""
    user_id = uuid.uuid4().hex[:12]
    users[user_id] = {
        "user_id": user_id,
        "name": name,
        "profile_image_url": profile_image_url,
    }
    return users[user_id]


def get_user(user_id: str) -> dict | None:
    return users.get(user_id)
