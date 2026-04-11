import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.room_manager import rooms
from models.schemas import WSGameStart, WSOpponentLeft, WSType, PlayerState

router = APIRouter()


def _to_player_state(p: dict) -> PlayerState:
    """room 딕셔너리의 플레이어 항목 → PlayerState"""
    return PlayerState(
        name=p["name"],
        character_id=p["character_id"],
        profile_image_url=p.get("profile_image_url"),
        hp=p.get("hp", 100),
        special_gauge=p.get("special_gauge", 0),
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

    # 두 명 모두 WS 연결됐을 때 → 양쪽에 GAME_START 전송
    if (
        len(room["players"]) == 2
        and room["players"][opponent_index]["ws"] is not None
    ):
        for idx in range(2):
            opp_idx = 1 - idx
            msg = WSGameStart(
                type=WSType.GAME_START,
                player_index=idx,                    # 0 = 좌측 P1, 1 = 우측 P2
                me=_to_player_state(room["players"][idx]),
                opponent=_to_player_state(room["players"][opp_idx]),
            )
            await room["players"][idx]["ws"].send_json(msg.model_dump())
        room["status"] = "playing"

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue  # 잘못된 JSON은 무시하고 계속

            # 상대에게 메시지 relay
            if (
                len(room["players"]) > opponent_index
                and room["players"][opponent_index]["ws"]
            ):
                await room["players"][opponent_index]["ws"].send_json(message)

    except WebSocketDisconnect:
        room["players"][player_index]["ws"] = None
        room["status"] = "finished"

        # 상대에게 퇴장 알림
        if (
            len(room["players"]) > opponent_index
            and room["players"][opponent_index]["ws"]
        ):
            msg = WSOpponentLeft(type=WSType.OPPONENT_LEFT)
            await room["players"][opponent_index]["ws"].send_json(msg.model_dump())

        # 둘 다 나가면 방 삭제
        if all(p["ws"] is None for p in room["players"]):
            del rooms[room_code]
