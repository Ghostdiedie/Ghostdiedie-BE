import random
import string
import time
import threading

rooms: dict[str, dict] = {}

ROOM_EXPIRE_SECONDS = 300  # 5분


def generate_room_code() -> str:
    """4자리 방 코드 생성"""
    while True:
        code = "".join(random.choices(string.ascii_uppercase, k=4))
        if code not in rooms:
            return code


def cleanup_expired_rooms():
    """만료된 방 삭제 (5분 경과 + playing 상태가 아닌 방)"""
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
    """30초마다 만료된 방 정리"""
    while True:
        time.sleep(30)
        expired = cleanup_expired_rooms()
        if expired:
            print(f"[room_manager] 만료된 방 삭제: {expired}")


# 백그라운드 스레드로 정리 실행
_cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
_cleanup_thread.start()
