import random
import string

rooms: dict[str, dict] = {}

def generate_room_code() -> str:
    """4자리 방 코드 생성"""
    while True:
        code = "".join(random.choices(string.ascii_uppercase, k=4))
        if code not in rooms:
            return code
