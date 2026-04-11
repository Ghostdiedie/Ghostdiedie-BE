import json
import logging
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.room_manager import rooms
from services.combat import init_combat_state, process_action
from models.schemas import WSGameStart, WSOpponentLeft, WSType, PlayerState

router = APIRouter()
logger = logging.getLogger("ghostdiedie.websocket")


def _to_player_state(player: dict, combat_player: dict = None) -> PlayerState:
    """Convert a room player entry into PlayerState for WebSocket messages."""
    return PlayerState(
        name=player["name"],
        character_id=player["character_id"],
        profile_image_url=player.get("profile_image_url"),
        hp=combat_player["hp"] if combat_player else 100,
        special_gauge=combat_player["special_gauge"] if combat_player else 0,
    )


def _get_players_list(room: dict) -> list[dict]:
    """Get [owner, guest] as a list for combat system compatibility."""
    return [room["owner"], room["guest"]]


@router.websocket("/ws/{room_code}")
async def websocket_game(websocket: WebSocket, room_code: str):
    if room_code not in rooms:
        await websocket.close(code=4004, reason="Room not found")
        return

    room = rooms[room_code]

    if room["guest"] is None:
        await websocket.close(code=4001, reason="Room not full yet")
        return

    if not (room["owner"]["confirmed"] and room["guest"]["confirmed"]):
        await websocket.close(code=4001, reason="Both players must confirm before connecting")
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
        await websocket.close(code=4003, reason="Room is full")
        return

    opponent_index = 1 - player_index
    logger.info("ws assigned room=%s player_index=%s opponent_index=%s", room_code, player_index, opponent_index)

    # When both WebSocket connected → init combat and send GAME_START
    if players[opponent_index]["ws"] is not None and "combat" not in room:
        room["combat"] = init_combat_state(players)
        room["combat"]["start_time"] = time.time()
        room["status"] = "playing"

        for idx in range(2):
            opp_idx = 1 - idx
            combat_me = room["combat"]["players"][idx]
            combat_opp = room["combat"]["players"][opp_idx]
            msg = WSGameStart(
                type=WSType.GAME_START,
                player_index=idx,
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

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue

            msg_type = message.get("type")
            action = message.get("action")

            if msg_type == "player_action" and action and "combat" in room:
                result = process_action(room["combat"], player_index, action)
                logger.info(
                    "player_action room=%s player_index=%s action=%s damage=%s blocked=%s ko=%s",
                    room_code,
                    player_index,
                    action,
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
                    loser_idx = 1 - winner_idx
                    duration = int(time.time() - room["combat"]["start_time"])

                    game_end_msg = {
                        "type": "game_end",
                        "winner_index": winner_idx,
                        "winner_name": players[winner_idx]["name"],
                        "loser_name": players[loser_idx]["name"],
                        "duration_seconds": duration,
                    }

                    for idx in range(2):
                        if players[idx]["ws"]:
                            await players[idx]["ws"].send_json(game_end_msg)

                    room["status"] = "finished"
                    logger.info(
                        "game_end room=%s winner_index=%s duration=%s",
                        room_code,
                        winner_idx,
                        duration,
                    )

            else:
                if players[opponent_index]["ws"]:
                    logger.info("relay room=%s player_index=%s type=%s", room_code, player_index, msg_type)
                    await players[opponent_index]["ws"].send_json(message)

    except WebSocketDisconnect:
        players[player_index]["ws"] = None
        room["status"] = "finished"
        logger.info("ws disconnected room=%s player_index=%s", room_code, player_index)

        if players[opponent_index]["ws"]:
            msg = WSOpponentLeft(type=WSType.OPPONENT_LEFT)
            await players[opponent_index]["ws"].send_json(msg.model_dump())

        if all(p["ws"] is None for p in players):
            del rooms[room_code]
