"""
Ghostdiedie combat damage engine.

Available attacks (matches frontend CV detection):
  - left punch   : base damage
  - right punch  : base damage
  - kick         : 1.3x damage, slightly longer range feel
  - headbutt     : 1.15x damage, short forward burst
  - special      : 3x damage, costs full gauge (100)

All characters share identical stats — balance is in the gameplay, not the roster.
"""

import time

# ── Shared stats (all characters identical) ──────────────────────────────────
BASE_HP          = 200
BASE_PUNCH       = 8     # left punch / right punch damage
KICK_MULTIPLIER  = 1.3   # kick hits harder than a punch
HEADBUTT_MULTIPLIER = 1.15
SPECIAL_MULTIPLIER = 3.0  # special = big hit, gauge cost required
SPECIAL_GAUGE_COST = 100  # must fill the whole gauge to use special
MAX_GAUGE        = 100

# ── Combat modifiers ─────────────────────────────────────────────────────────
FIRST_HIT_WINDOW      = 1.0   # seconds of opponent inactivity → counter-hit
FIRST_HIT_MULTIPLIER  = 1.2   # counter-hit bonus
BLOCK_REDUCTION       = 0.5   # blocked hit deals 50% damage
GAUGE_PER_HIT         = 12    # gauge gained on a successful attack
GAUGE_PER_BLOCK       = 8     # gauge gained on blocking a hit

# Recognised attack strings sent from the frontend
ATTACK_ACTIONS = ("right punch", "left punch", "kick", "headbutt", "special")


def get_character_stats(character_id: int) -> dict:
    """Return combat stats. All characters are equal."""
    return {
        "hp": BASE_HP,
        "max_hp": BASE_HP,
        "attack": BASE_PUNCH,
        "special_gauge": 0,
        "max_gauge": MAX_GAUGE,
    }


def init_combat_state(players: list[dict]) -> dict:
    """Initialize combat state when both WebSocket clients connect."""
    state = {
        "start_time": None,
        "players": [],
    }
    for p in players:
        stats = get_character_stats(p["character_id"])
        stats.update({
            "last_action": None,
            "last_action_time": 0.0,
            "blocking": False,
        })
        state["players"].append(stats)
    return state


def process_action(combat: dict, player_index: int, action: str) -> dict:
    """
    Process a player action and return the result.

    Returns:
        {
            "damage": int,           # Damage dealt to the defender
            "attacker_hp": int,      # Current attacker HP
            "defender_hp": int,      # Current defender HP
            "attacker_gauge": int,   # Current attacker gauge
            "defender_gauge": int,   # Current defender gauge
            "first_hit": bool,       # Whether the first-hit bonus applied
            "blocked": bool,         # Whether the hit was blocked
            "is_special": bool,      # Whether the action was a special move
            "ko": bool,              # Whether the defender was KO'd
            "ko_winner": int | None, # Winner index when a KO occurs
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

    # Update block state
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

    # Non-attack actions are only relayed to the opponent
    if action not in ATTACK_ACTIONS:
        attacker["blocking"] = False
        attacker["last_action"] = action
        attacker["last_action_time"] = now
        return result

    # Handle attacks: punches → base, kick/headbutt → boosted, special → 3x
    attacker["blocking"] = False
    base_damage = attacker["attack"]   # BASE_PUNCH for everyone
    is_special = action == "special"
    is_kick = action == "kick"
    is_headbutt = action == "headbutt"

    if is_kick:
        base_damage = int(base_damage * KICK_MULTIPLIER)
    elif is_headbutt:
        base_damage = int(base_damage * HEADBUTT_MULTIPLIER)

    if is_special:
        if attacker["special_gauge"] < SPECIAL_GAUGE_COST:
            return result  # Not enough gauge; ignore the action
        attacker["special_gauge"] -= SPECIAL_GAUGE_COST
        base_damage = int(base_damage * SPECIAL_MULTIPLIER)
        result["is_special"] = True
    else:
        # Charge gauge on normal attacks
        attacker["special_gauge"] = min(
            attacker["special_gauge"] + GAUGE_PER_HIT,
            attacker["max_gauge"],
        )

    # First-hit bonus if the opponent has not attacked recently
    time_since_opponent = now - defender["last_action_time"]
    if time_since_opponent > FIRST_HIT_WINDOW and not is_special:
        base_damage = int(base_damage * FIRST_HIT_MULTIPLIER)
        result["first_hit"] = True

    # Reduce damage if the defender is blocking
    if defender["blocking"]:
        base_damage = int(base_damage * BLOCK_REDUCTION)
        result["blocked"] = True
        # The defender also gains a small amount of gauge
        defender["special_gauge"] = min(
            defender["special_gauge"] + GAUGE_PER_BLOCK,
            defender["max_gauge"],
        )

    # Apply damage
    defender["hp"] = max(0, defender["hp"] - base_damage)

    # Update action timestamp
    attacker["last_action"] = action
    attacker["last_action_time"] = now

    result["damage"] = base_damage
    result["attacker_hp"] = attacker["hp"]
    result["defender_hp"] = defender["hp"]
    result["attacker_gauge"] = attacker["special_gauge"]
    result["defender_gauge"] = defender["special_gauge"]

    # Check for KO
    if defender["hp"] <= 0:
        result["ko"] = True
        result["ko_winner"] = player_index

    return result
