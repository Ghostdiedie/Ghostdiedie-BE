import asyncio
import json
import logging
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.room_manager import rooms
from services.combat import init_combat_state, process_action, get_character_stats
from models.schemas import WSGameStart, WSOpponentLeft, WSType, PlayerState

router = APIRouter()
logger = logging.getLogger("ghostdiedie.websocket")

# Per-action attack range (max distance for the hit to land).
# FIGHTER_MIN_DISTANCE on the frontend is 1.8 (touching distance).
# Values include a small buffer for position-sync lag.
ATTACK_RANGES = {
    "left punch":  2.3,
    "right punch": 2.3,
    "kick":        3.0,
    "headbutt":    1.9,
    "special":     2.5,
}

# Countdown duration must match the frontend constants:
# 5 steps × 1000 ms + 1400 ms for FIGHT! display
COUNTDOWN_TOTAL_MS = 6400


def _distance(pos_a: list, pos_b: list) -> float:
    dx = pos_a[0] - pos_b[0]
    dy = pos_a[1] - pos_b[1]
    dz = pos_a[2] - pos_b[2]
    return (dx * dx + dy * dy + dz * dz) ** 0.5


async def _handle_post_round(
    room: dict,
    room_code: str,
    players: list,
    winner_idx: int,
    current_round: int,
    current_round_wins: list,
):
    """Wait after a round ends, then send round_start or game_end."""
    loser_idx = 1 - winner_idx
    await asyncio.sleep(3.5)

    if current_round_wins[winner_idx] >= 2:
        duration = int(time.time() - room["combat"]["start_time"])
        game_end_msg = {
            "type": "game_end",
            "winner_index": winner_idx,
            "winner_name": players[winner_idx]["name"],
            "loser_name": players[loser_idx]["name"],
            "duration_seconds": duration,
            "round_wins": current_round_wins,
        }
        room["status"] = "finished"
        for idx in range(2):
            if players[idx]["ws"]:
                try:
                    await players[idx]["ws"].send_json(game_end_msg)
                except Exception:
                    pass
        logger.info(
            "game_end room=%s winner_index=%s duration=%s",
            room_code,
            winner_idx,
            duration,
        )
    else:
        next_round = current_round + 1
        room["current_round"] = next_round
        for i, combat_player in enumerate(room["combat"]["players"]):
            stats = get_character_stats(players[i]["character_id"])
            combat_player["hp"] = stats["hp"]
            combat_player["max_hp"] = stats["max_hp"]
            combat_player["special_gauge"] = 0
            combat_player["last_action"] = None
            combat_player["last_action_time"] = 0.0
            combat_player["blocking"] = False
        room["combat"]["ko_processed"] = False  # re-enable combat

        server_now_ms = int(time.time() * 1000)
        countdown_start_ms = server_now_ms + 1500
        room["fight_start_time"] = (countdown_start_ms + COUNTDOWN_TOTAL_MS) / 1000.0

        for idx in range(2):
            opp_idx = 1 - idx
            combat_me = room["combat"]["players"][idx]
            combat_opp = room["combat"]["players"][opp_idx]
            round_start_msg = {
                "type": "round_start",
                "round_number": next_round,
                "round_wins": current_round_wins,
                "server_now_ms": server_now_ms,
                "countdown_start_ms": countdown_start_ms,
                "me": {
                    "hp": combat_me["hp"],
                    "max_hp": combat_me["max_hp"],
                    "special_gauge": 0,
                },
                "opponent": {
                    "hp": combat_opp["hp"],
                    "max_hp": combat_opp["max_hp"],
                    "special_gauge": 0,
                },
            }
            if players[idx]["ws"]:
                try:
                    await players[idx]["ws"].send_json(round_start_msg)
                except Exception:
                    pass

        logger.info(
            "round_start sent room=%s round=%s round_wins=%s countdown_start_ms=%s",
            room_code,
            next_round,
            current_round_wins,
            countdown_start_ms,
        )


AFK_TIMEOUT_SECONDS = 30  # seconds of inactivity before AFK timeout
AFK_CHECK_INTERVAL = 3  # seconds between AFK checks when no messages arrive


def _to_player_state(player: dict, combat_player: dict = None) -> PlayerState:
    """Convert a room player entry into PlayerState for WebSocket messages."""
    return PlayerState(
        name=player["name"],
        character_id=player["character_id"],
        profile_image_url=player.get("profile_image_url"),
        hp=combat_player["hp"] if combat_player else 200,
        max_hp=combat_player["max_hp"] if combat_player else 200,
        special_gauge=combat_player["special_gauge"] if combat_player else 0,
    )


def _get_players_list(room: dict) -> list[dict]:
    """Get [owner, guest] as a list for combat system compatibility."""
    return [room["owner"], room["guest"]]


@router.websocket("/ws/{room_code}")
async def websocket_game(websocket: WebSocket, room_code: str):
    if room_code not in rooms:
        logger.warning("ws rejected room=%s reason=room_not_found", room_code)
        await websocket.close(code=4004, reason="Room not found")
        return

    room = rooms[room_code]

    if room["guest"] is None:
        logger.warning("ws rejected room=%s reason=room_not_full", room_code)
        await websocket.close(code=4001, reason="Room not full yet")
        return

    if not (room["owner"]["confirmed"] and room["guest"]["confirmed"]):
        logger.warning(
            "ws rejected room=%s reason=not_confirmed owner_confirmed=%s guest_confirmed=%s",
            room_code,
            room["owner"]["confirmed"],
            room["guest"]["confirmed"],
        )
        await websocket.close(
            code=4001, reason="Both players must confirm before connecting"
        )
        return

    if not (
        room["owner"].get("character_selected")
        and room["guest"].get("character_selected")
    ):
        logger.warning(
            "ws rejected room=%s reason=character_not_selected owner_selected=%s guest_selected=%s",
            room_code,
            room["owner"].get("character_selected"),
            room["guest"].get("character_selected"),
        )
        await websocket.close(
            code=4001, reason="Both players must select a character before connecting"
        )
        return

    await websocket.accept()
    logger.info("ws accepted room=%s", room_code)

    # Determine which player is connecting (owner=0, guest=1)
    players = _get_players_list(room)
    player_index = None
    for i, p in enumerate(players):
        if p["ws"] is None:
            p["ws"] = websocket
            player_index = i
            break

    if player_index is None:
        logger.warning(
            "ws rejected room=%s reason=room_already_has_two_sockets", room_code
        )
        await websocket.close(code=4003, reason="Room is full")
        return

    opponent_index = 1 - player_index
    logger.info(
        "ws assigned room=%s player_index=%s opponent_index=%s",
        room_code,
        player_index,
        opponent_index,
    )

    # When both WebSocket connected → init combat and send GAME_START
    if players[opponent_index]["ws"] is not None and "combat" not in room:
        room["combat"] = init_combat_state(players)
        room["combat"]["start_time"] = time.time()
        room["last_activity"] = [time.time(), time.time()]
        room["round_wins"] = [0, 0]
        room["current_round"] = 1
        room["status"] = "playing"
        # Track last known position of each player for range checks
        room["positions"] = [[0.0, 0.0, 6.0], [0.0, 0.0, -6.0]]
        server_now_ms = int(time.time() * 1000)
        countdown_start_ms = server_now_ms + 1500
        # No combat allowed until the countdown finishes
        room["fight_start_time"] = (countdown_start_ms + COUNTDOWN_TOTAL_MS) / 1000.0

        for idx in range(2):
            opp_idx = 1 - idx
            combat_me = room["combat"]["players"][idx]
            combat_opp = room["combat"]["players"][opp_idx]
            msg = WSGameStart(
                type=WSType.GAME_START,
                player_index=idx,
                server_now_ms=server_now_ms,
                countdown_start_ms=countdown_start_ms,
                me=_to_player_state(players[idx], combat_me),
                opponent=_to_player_state(players[opp_idx], combat_opp),
            )
            await players[idx]["ws"].send_json(msg.model_dump())
        logger.info(
            "game_start sent room=%s p0_character=%s p1_character=%s",
            room_code,
            players[0]["character_id"],
            players[1]["character_id"],
        )

    afk_triggered = False
    try:
        last_position_log_at = 0.0
        while True:
            # Receive with timeout for AFK detection
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=AFK_CHECK_INTERVAL,
                )
            except asyncio.TimeoutError:
                data = None

            # ── AFK check (only during active combat) ──
            if "combat" in room and "last_activity" in room:
                now_check = time.time()
                afk_idx = None
                for idx in range(2):
                    if now_check - room["last_activity"][idx] > AFK_TIMEOUT_SECONDS:
                        afk_idx = idx
                        break
                if afk_idx is not None:
                    afk_msg = {"type": "afk_timeout", "afk_player_index": afk_idx}
                    for p_idx in range(2):
                        if players[p_idx]["ws"]:
                            try:
                                await players[p_idx]["ws"].send_json(afk_msg)
                            except Exception:
                                pass
                    room["status"] = "finished"
                    afk_triggered = True
                    logger.info("afk_timeout room=%s afk_player=%s", room_code, afk_idx)
                    break

            if data is None:
                continue

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue

            msg_type = message.get("type")
            action = message.get("action")
            now = time.time()

            # Update AFK activity timestamp
            if "last_activity" in room:
                if msg_type == "player_action":
                    room["last_activity"][player_index] = now
                elif msg_type == "position_sync":
                    room["last_activity"][player_index] = now
                elif msg_type == "attack_anim":
                    room["last_activity"][player_index] = now

            if msg_type == "position_sync":
                pos = message.get("position")
                if pos and len(pos) == 3 and "positions" in room:
                    room["positions"][player_index] = pos
                if now - last_position_log_at >= 1.0:
                    logger.info(
                        "recv room=%s player_index=%s type=position_sync position=%s isMoving=%s movingBackward=%s",
                        room_code,
                        player_index,
                        pos,
                        message.get("isMoving"),
                        message.get("movingBackward"),
                    )
                    last_position_log_at = now
            else:
                logger.info(
                    "recv room=%s player_index=%s type=%s action=%s",
                    room_code,
                    player_index,
                    msg_type,
                    action,
                )

            if (
                msg_type == "player_action"
                and action
                and "combat" in room
                and not room["combat"].get("ko_processed", False)
            ):
                # Block actions during countdown
                if room.get("fight_start_time") and now < room["fight_start_time"]:
                    logger.info(
                        "player_action EARLY room=%s player_index=%s action=%s remaining=%.2fs",
                        room_code, player_index, action, room["fight_start_time"] - now,
                    )
                    continue

                # Range check — block attacks that are too far away
                if "positions" in room:
                    dist = _distance(
                        room["positions"][player_index],
                        room["positions"][opponent_index],
                    )
                    max_range = ATTACK_RANGES.get(action)
                    if max_range is not None and dist > max_range:
                        logger.info(
                            "player_action MISSED room=%s player_index=%s action=%s dist=%.2f max=%.2f",
                            room_code,
                            player_index,
                            action,
                            dist,
                            max_range,
                        )
                        # Whiff — inform attacker, no effect on defender'
                        combat_p = room["combat"]["players"]
                        await websocket.send_json(
                            {
                                "type": "action_result",
                                "action": action,
                                "damage": 0,
                                "first_hit": False,
                                "blocked": False,
                                "is_special": False,
                                "missed": True,
                                "my_hp": combat_p[player_index]["hp"],
                                "opponent_hp": combat_p[opponent_index]["hp"],
                                "my_gauge": combat_p[player_index]["special_gauge"],
                                "opponent_gauge": combat_p[opponent_index][
                                    "special_gauge"
                                ],
                            }
                        )
                        continue

                result = process_action(room["combat"], player_index, action)
                logger.info(
                    "player_action room=%s player_index=%s action=%s dist=%.2f damage=%s blocked=%s ko=%s",
                    room_code,
                    player_index,
                    action,
                    (
                        _distance(
                            room["positions"][player_index],
                            room["positions"][opponent_index],
                        )
                        if "positions" in room
                        else -1
                    ),
                    result["damage"],
                    result["blocked"],
                    result["ko"],
                )

                attacker_msg = {
                    "type": "action_result",
                    "action": action,
                    "damage": result["damage"],
                    "first_hit": result["first_hit"],
                    "blocked": result["blocked"],
                    "is_special": result["is_special"],
                    "my_hp": result["attacker_hp"],
                    "opponent_hp": result["defender_hp"],
                    "my_gauge": result["attacker_gauge"],
                    "opponent_gauge": result["defender_gauge"],
                }
                await websocket.send_json(attacker_msg)

                if players[opponent_index]["ws"]:
                    defender_msg = {
                        "type": "hit_received",
                        "action": action,
                        "damage": result["damage"],
                        "first_hit": result["first_hit"],
                        "blocked": result["blocked"],
                        "is_special": result["is_special"],
                        "my_hp": result["defender_hp"],
                        "opponent_hp": result["attacker_hp"],
                        "my_gauge": result["defender_gauge"],
                        "opponent_gauge": result["attacker_gauge"],
                    }
                    await players[opponent_index]["ws"].send_json(defender_msg)

                if result["ko"]:
                    winner_idx = result["ko_winner"]
                    room["round_wins"][winner_idx] += 1
                    current_round_wins = list(room["round_wins"])
                    current_round = room["current_round"]

                    # Block further action processing until next round
                    room["combat"]["ko_processed"] = True

                    logger.info(
                        "round_ko room=%s winner_index=%s round_wins=%s game_over=%s",
                        room_code,
                        winner_idx,
                        current_round_wins,
                        current_round_wins[winner_idx] >= 2,
                    )

                    # Send round_end immediately so clients can show the win overlay
                    round_end_msg = {
                        "type": "round_end",
                        "round_number": current_round,
                        "winner_index": winner_idx,
                        "winner_name": players[winner_idx]["name"],
                        "round_wins": current_round_wins,
                        "game_over": current_round_wins[winner_idx] >= 2,
                    }
                    for idx in range(2):
                        if players[idx]["ws"]:
                            await players[idx]["ws"].send_json(round_end_msg)

                    # After a delay send either round_start or game_end
                    asyncio.create_task(
                        _handle_post_round(
                            room,
                            room_code,
                            players,
                            winner_idx,
                            current_round,
                            current_round_wins,
                        )
                    )

            else:
                if players[opponent_index]["ws"]:
                    if msg_type not in {"position_sync", "webrtc_ice"}:
                        logger.info(
                            "relay room=%s player_index=%s type=%s",
                            room_code,
                            player_index,
                            msg_type,
                        )
                    await players[opponent_index]["ws"].send_json(message)

    except WebSocketDisconnect:
        logger.info("ws disconnected room=%s player_index=%s", room_code, player_index)

    # ── Cleanup ──
    players[player_index]["ws"] = None
    if afk_triggered:
        if players[opponent_index]["ws"]:
            try:
                await players[opponent_index]["ws"].close(
                    code=4002, reason="AFK timeout"
                )
            except Exception:
                pass
    else:
        room["status"] = "finished"
        if players[opponent_index]["ws"]:
            try:
                msg = WSOpponentLeft(type=WSType.OPPONENT_LEFT)
                await players[opponent_index]["ws"].send_json(msg.model_dump())
            except Exception:
                pass

    if room_code in rooms and all(p["ws"] is None for p in players):
        del rooms[room_code]
