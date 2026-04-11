import random
import time
import threading

rooms: dict[str, dict] = {}

ROOM_EXPIRE_SECONDS = 180  # 3 minutes


def generate_room_code() -> str:
    """Generate an 8-digit numeric room code."""
    while True:
        code = "".join(random.choices("0123456789", k=8))
        if code not in rooms:
            return code


def cleanup_expired_rooms():
    """Delete expired rooms that are not currently playing."""
    now = time.time()
    expired = [
        code for code, room in rooms.items()
        if now - room.get("created_at", now) > ROOM_EXPIRE_SECONDS
        and room.get("status") != "playing"
    ]
    for code in expired:
        del rooms[code]
    return expired


def _cleanup_loop():
    """Clean up expired rooms every 10 seconds."""
    while True:
        time.sleep(10)
        expired = cleanup_expired_rooms()
        if expired:
            for code in expired:
                print(f"[room_manager] Room {code} expired after {ROOM_EXPIRE_SECONDS} seconds.")


# Run cleanup in a background thread
_cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
_cleanup_thread.start()
