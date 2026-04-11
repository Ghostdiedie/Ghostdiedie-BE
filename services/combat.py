"""
Ghostdiedie combat damage engine.

- Base damage: character attack stat
- First-hit bonus: 1.5x if the attacker strikes before the opponent acts
- Block reduction: 50% damage reduction while the defender is blocking
- Special move: costs 100 gauge and deals 3x damage
- HP at 0 or below ends the game
"""

import time

# Default character combat stats cached on server startup
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

FIRST_HIT_WINDOW = 0.3       # First-hit timing window in seconds
FIRST_HIT_MULTIPLIER = 1.5   # Damage multiplier for a first hit
BLOCK_REDUCTION = 0.5         # Damage reduction while blocking
SPECIAL_MULTIPLIER = 3.0      # Damage multiplier for special moves
SPECIAL_GAUGE_COST = 100      # Gauge cost for a special move
KICK_MULTIPLIER = 1.2         # Kick damage multiplier
GAUGE_PER_HIT = 15            # Gauge gained per attack
GAUGE_PER_BLOCK = 5           # Gauge gained per block

# Attack action list
ATTACK_ACTIONS = ("right punch", "left punch", "kick", "special")


def get_character_stats(character_id: int) -> dict:
    """Return combat stats for a character ID."""
    return {
        "hp": DEFAULT_HP.get(character_id, 100),
        "max_hp": DEFAULT_HP.get(character_id, 100),
        "attack": DEFAULT_ATTACK.get(character_id, 15),
        "special_gauge": 0,
        "max_gauge": DEFAULT_MAX_GAUGE.get(character_id, 100),
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

    # Handle attacks
    attacker["blocking"] = False
    base_damage = attacker["attack"]
    is_special = action == "special"
    is_kick = action == "kick"

    # Kicks do slightly more damage than punches
    if is_kick:
        base_damage = int(base_damage * KICK_MULTIPLIER)

    # Handle special moves
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
