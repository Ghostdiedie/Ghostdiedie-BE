"""
Ghostdiedie 전투 데미지 엔진

- 기본 데미지: 캐릭터 attack 값
- 선빵 보너스: 상대가 쿨다운 중이 아닐 때 먼저 때리면 1.5배
- 방어 감소: 상대가 block 중이면 데미지 50% 감소
- 필살기: 게이지 100 소모, 데미지 3배
- HP 0 이하 → 게임 종료
"""

import time

# 캐릭터 기본 공격력 (DB 값과 동일, 서버 시작 시 캐싱용)
DEFAULT_ATTACK = {
    1: 15,   # Jin
    2: 13,   # Kazuya
    3: 17,   # Heihachi
    4: 14,   # Paul
    5: 12,   # King
}

DEFAULT_HP = {
    1: 100,  # Jin
    2: 110,  # Kazuya
    3: 95,   # Heihachi
    4: 105,  # Paul
    5: 115,  # King
}

DEFAULT_MAX_GAUGE = {
    1: 100,
    2: 120,
    3: 80,
    4: 100,
    5: 90,
}

FIRST_HIT_WINDOW = 0.3       # 선빵 판정 시간 (초)
FIRST_HIT_MULTIPLIER = 1.5   # 선빵 데미지 배율
BLOCK_REDUCTION = 0.5         # 방어 시 데미지 감소율
SPECIAL_MULTIPLIER = 3.0      # 필살기 데미지 배율
SPECIAL_GAUGE_COST = 100      # 필살기 게이지 소모량
KICK_MULTIPLIER = 1.2         # 킥 데미지 배율 (펀치보다 약간 강함)
GAUGE_PER_HIT = 15            # 공격 시 게이지 충전량
GAUGE_PER_BLOCK = 5           # 방어 시 게이지 충전량

# 공격 액션 목록
ATTACK_ACTIONS = ("right punch", "left punch", "kick", "special")


def init_combat_state(players: list[dict]) -> dict:
    """방 생성 시 전투 상태 초기화"""
    state = {
        "start_time": None,
        "players": [],
    }
    for p in players:
        cid = p["character_id"]
        state["players"].append({
            "hp": DEFAULT_HP.get(cid, 100),
            "max_hp": DEFAULT_HP.get(cid, 100),
            "attack": DEFAULT_ATTACK.get(cid, 15),
            "special_gauge": 0,
            "max_gauge": DEFAULT_MAX_GAUGE.get(cid, 100),
            "last_action": None,
            "last_action_time": 0.0,
            "blocking": False,
        })
    return state


def process_action(combat: dict, player_index: int, action: str) -> dict:
    """
    플레이어 액션 처리 → 결과 반환

    Returns:
        {
            "damage": int,           # 상대에게 가한 데미지
            "attacker_hp": int,      # 공격자 현재 HP
            "defender_hp": int,      # 수비자 현재 HP
            "attacker_gauge": int,   # 공격자 게이지
            "defender_gauge": int,   # 수비자 게이지
            "first_hit": bool,       # 선빵 여부
            "blocked": bool,         # 방어됨 여부
            "is_special": bool,      # 필살기 여부
            "ko": bool,             # KO 여부
            "ko_winner": int | None, # KO 시 승자 인덱스
        }
    """
    attacker = combat["players"][player_index]
    defender = combat["players"][1 - player_index]
    now = time.time()

    result = {
        "damage": 0,
        "attacker_hp": attacker["hp"],
        "defender_hp": defender["hp"],
        "attacker_gauge": attacker["special_gauge"],
        "defender_gauge": defender["special_gauge"],
        "first_hit": False,
        "blocked": False,
        "is_special": False,
        "ko": False,
        "ko_winner": None,
    }

    # 방어 상태 업데이트
    if action == "block":
        attacker["blocking"] = True
        attacker["last_action"] = "block"
        attacker["last_action_time"] = now
        attacker["special_gauge"] = min(
            attacker["special_gauge"] + GAUGE_PER_BLOCK,
            attacker["max_gauge"],
        )
        result["attacker_gauge"] = attacker["special_gauge"]
        return result

    # 공격이 아닌 액션 (jump, walk, idle 등) → 상대에게 relay만
    if action not in ATTACK_ACTIONS:
        attacker["blocking"] = False
        attacker["last_action"] = action
        attacker["last_action_time"] = now
        return result

    # ── 공격 처리 ──
    attacker["blocking"] = False
    base_damage = attacker["attack"]
    is_special = action == "special"
    is_kick = action == "kick"

    # 킥은 펀치보다 약간 강함
    if is_kick:
        base_damage = int(base_damage * KICK_MULTIPLIER)

    # 필살기 처리
    if is_special:
        if attacker["special_gauge"] < SPECIAL_GAUGE_COST:
            return result  # 게이지 부족 → 무시
        attacker["special_gauge"] -= SPECIAL_GAUGE_COST
        base_damage = int(base_damage * SPECIAL_MULTIPLIER)
        result["is_special"] = True
    else:
        # 일반 공격 시 게이지 충전
        attacker["special_gauge"] = min(
            attacker["special_gauge"] + GAUGE_PER_HIT,
            attacker["max_gauge"],
        )

    # 선빵 보너스: 상대가 최근에 공격하지 않았으면 (쿨다운 밖)
    time_since_opponent = now - defender["last_action_time"]
    if time_since_opponent > FIRST_HIT_WINDOW and not is_special:
        base_damage = int(base_damage * FIRST_HIT_MULTIPLIER)
        result["first_hit"] = True

    # 방어 감소
    if defender["blocking"]:
        base_damage = int(base_damage * BLOCK_REDUCTION)
        result["blocked"] = True
        # 방어자도 게이지 소량 충전
        defender["special_gauge"] = min(
            defender["special_gauge"] + GAUGE_PER_BLOCK,
            defender["max_gauge"],
        )

    # 데미지 적용
    defender["hp"] = max(0, defender["hp"] - base_damage)

    # 타임스탬프 갱신
    attacker["last_action"] = action
    attacker["last_action_time"] = now

    result["damage"] = base_damage
    result["attacker_hp"] = attacker["hp"]
    result["defender_hp"] = defender["hp"]
    result["attacker_gauge"] = attacker["special_gauge"]
    result["defender_gauge"] = defender["special_gauge"]

    # KO 판정
    if defender["hp"] <= 0:
        result["ko"] = True
        result["ko_winner"] = player_index

    return result