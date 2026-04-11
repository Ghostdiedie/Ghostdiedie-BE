import json
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.room_manager import rooms
from services.combat import init_combat_state, process_action
from models.schemas import WSGameStart, WSOpponentLeft, WSGameEnd, WSType, PlayerState

router = APIRouter()


def _to_player_state(p: dict, combat_player: dict = None) -> PlayerState:
    """room 딕셔너리의 플레이어 항목 → PlayerState"""
    return PlayerState(
        name=p["name"],
        character_id=p["character_id"],
        profile_image_url=p.get("profile_image_url"),
        hp=combat_player["hp"] if combat_player else p.get("hp", 100),
        special_gauge=combat_player["special_gauge"] if combat_player else p.get("special_gauge", 0),
    )


@router.websocket("/ws/{room_code}")
async def websocket_game(websocket: WebSocket, room_code: str):
    room_code = room_code.upper()
    if room_code not in rooms:
        await websocket.close(code=4004, reason="Room not found")
        return

    room = rooms[room_code]
    await websocket.accept()

    # 빈 슬롯에 WebSocket 연결
    player_index = None
    for i, p in enumerate(room["players"]):
        if p["ws"] is None:
            p["ws"] = websocket
            player_index = i
            break

    if player_index is None:
        await websocket.close(code=4003, reason="Room is full")
        return

    opponent_index = 1 - player_index

    # 두 명 모두 WS 연결됐을 때 → 전투 상태 초기화 + GAME_START 전송
    if (
        len(room["players"]) == 2
        and room["players"][opponent_index]["ws"] is not None
    ):
        # 전투 상태 초기화
        room["combat"] = init_combat_state(room["players"])
        room["combat"]["start_time"] = time.time()

        for idx in range(2):
            opp_idx = 1 - idx
            combat_me = room["combat"]["players"][idx]
            combat_opp = room["combat"]["players"][opp_idx]
            msg = WSGameStart(
                type=WSType.GAME_START,
                player_index=idx,
                me=_to_player_state(room["players"][idx], combat_me),
                opponent=_to_player_state(room["players"][opp_idx], combat_opp),
            )
            await room["players"][idx]["ws"].send_json(msg.model_dump())
        room["status"] = "playing"

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue

            msg_type = message.get("type")
            action = message.get("action")

            # 전투 액션 처리
            if msg_type == "player_action" and action and "combat" in room:
                result = process_action(room["combat"], player_index, action)

                # 공격자에게: 내가 가한 데미지 + 양쪽 상태
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

                # 수비자에게: 상대가 나를 때림 + 양쪽 상태
                if (
                    len(room["players"]) > opponent_index
                    and room["players"][opponent_index]["ws"]
                ):
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
                    await room["players"][opponent_index]["ws"].send_json(defender_msg)

                # KO 판정
                if result["ko"]:
                    winner_idx = result["ko_winner"]
                    loser_idx = 1 - winner_idx
                    duration = int(time.time() - room["combat"]["start_time"])

                    game_end_msg = {
                        "type": "game_end",
                        "winner_index": winner_idx,
                        "winner_name": room["players"][winner_idx]["name"],
                        "loser_name": room["players"][loser_idx]["name"],
                        "duration_seconds": duration,
                    }

                    for idx in range(2):
                        if room["players"][idx]["ws"]:
                            await room["players"][idx]["ws"].send_json(game_end_msg)

                    room["status"] = "finished"

            else:
                # 기타 메시지는 그대로 relay
                if (
                    len(room["players"]) > opponent_index
                    and room["players"][opponent_index]["ws"]
                ):
                    await room["players"][opponent_index]["ws"].send_json(message)

    except WebSocketDisconnect:
        room["players"][player_index]["ws"] = None
        room["status"] = "finished"

        if (
            len(room["players"]) > opponent_index
            and room["players"][opponent_index]["ws"]
        ):
            msg = WSOpponentLeft(type=WSType.OPPONENT_LEFT)
            await room["players"][opponent_index]["ws"].send_json(msg.model_dump())

        if all(p["ws"] is None for p in room["players"]):
            del rooms[room_code]
