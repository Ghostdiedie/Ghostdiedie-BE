"""
Ghostdiedie Club Backend
FastAPI + Supabase + WebSocket
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from routers import characters, face, matches, rooms, users, websocket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="Ghostdiedie Club API",
    version="0.2.0",
    description="""
Ghostdiedie Club — motion-based fighting game backend

---

## Full Client Flow (FE → BE)

```
[Lobby Page]
  1. 사진 촬영/선택
     POST /api/face (file) → { face_id, face_url }
     → 프론트에 face_id, face_url 저장

  2. 이름 입력 후 Create/Join 클릭
     GET /api/user/register?name=...&face_id=... → { user_id, name, profile_image_url }
     → 프론트에 user_id 저장

[Create Room Page]
  3. 방 생성
     GET /api/room/create?user_id=...&character_id=... → { code, owner, expires_in }
     → 8자리 코드 화면에 표시

  4. 상대 대기 (1.5초 간격 폴링)
     GET /api/room/status?code=... → { status, owner, guest, both_confirmed }
     → guest가 null이 아니면 상대 입장 완료

  5. Confirm 버튼 클릭
     GET /api/room/confirm?code=...&user_id=... → { confirmed, both_confirmed }
     → both_confirmed가 false면 계속 room/status 폴링

  6. 양쪽 confirm 완료 → WebSocket 연결
     wss://{host}/ws/{code}
     → 양쪽 연결 시 서버가 game_start 전송 → 게임 화면으로 이동

[Join Room Page]
  3. 8자리 코드 입력 후 Join
     GET /api/room/join?code=...&user_id=...&character_id=...
     → { success, code, owner, guest }
     → owner 정보(이름, 사진) 화면에 표시

  4. Confirm 버튼 클릭
     GET /api/room/confirm?code=...&user_id=... → { confirmed, both_confirmed }
     → both_confirmed false면 room/status 폴링

  5. 양쪽 confirm 완료 → WebSocket 연결
     → game_start → 게임 화면

[Game Page]
  WebSocket 메시지로 실시간 전투
  Client → Server: { type: "player_action", action: "..." }
  Server → Client: action_result / hit_received / game_end / opponent_left
```

---

## HTTP API

### Face

| Method | Endpoint | Params | Response |
|--------|----------|--------|----------|
| `POST` | `/api/face` | `file` (multipart image) | `{ face_id, face_url }` — 256x256 원형 크롭 PNG (base64) |

### User

| Method | Endpoint | Params | Response |
|--------|----------|--------|----------|
| `GET` | `/api/user/register` | `name`, `face_id` | `{ status, user_id, name, profile_image_url }` |

### Room

| Method | Endpoint | Params | Response |
|--------|----------|--------|----------|
| `GET` | `/api/room/create` | `user_id`, `character_id` | `{ code, owner, expires_in }` |
| `GET` | `/api/room/join` | `code`, `user_id`, `character_id` | `{ success, code, owner, guest }` |
| `GET` | `/api/room/confirm` | `code`, `user_id` | `{ confirmed, both_confirmed }` |
| `GET` | `/api/room/status` | `code` | `{ code, status, owner, guest, both_confirmed, expires_in }` |

**Room status flow**: `waiting` → `ready` → `confirmed` → `playing` → `finished`

**owner/guest 응답 형식**:
```json
{ "user_id": "abc123", "name": "홍길동", "profile_image_url": "data:image/png;base64,...", "role": "owner" }
```

### Characters

| Method | Endpoint | Params | Response |
|--------|----------|--------|----------|
| `GET` | `/api/characters` | — | `[{ id, name, max_hp, max_special_gauge, image_url }]` |
| `GET` | `/api/characters/{id}` | — | `{ id, name, max_hp, attack, max_special_gauge, image_url }` |
| `POST` | `/api/characters/{id}/image` | `file` (WebP) | `{ character_id, image_url }` |
| `GET` | `/api/characters/{id}/image` | — | WebP image binary (no auth) |

### Matches

| Method | Endpoint | Params | Response |
|--------|----------|--------|----------|
| `POST` | `/api/matches` | JSON body: `room_code, winner_name, loser_name, winner_character_id, loser_character_id, duration_seconds` | `{ match_id, created_at }` |
| `GET` | `/api/leaderboard` | `limit?` (default 10) | `[{ player_name, wins }]` |

---

## WebSocket

### `wss://{host}/ws/{room_code}`

**연결 조건**: 양쪽 모두 HTTP `/api/room/confirm` 완료 후에만 연결 가능 (미확인 시 4001 close)

### Server → Client

| Type | When | Payload |
|------|------|---------|
| `game_start` | 양쪽 WS 연결 완료 | `{ player_index, me: PlayerState, opponent: PlayerState }` |
| `action_result` | 내가 공격 | `{ action, damage, first_hit, blocked, is_special, my_hp, opponent_hp, my_gauge, opponent_gauge }` |
| `hit_received` | 상대가 공격 | `{ action, damage, first_hit, blocked, is_special, my_hp, opponent_hp, my_gauge, opponent_gauge }` |
| `game_end` | KO 발생 | `{ winner_index, winner_name, loser_name, duration_seconds }` |
| `opponent_left` | 상대 연결 끊김 | `{}` |

### Client → Server

| Type | Payload |
|------|---------|
| `player_action` | `{ type: "player_action", action: "right punch" \\| "left punch" \\| "kick" \\| "block" \\| "special" }` |

### PlayerState (game_start에 포함)

```json
{ "name": "홍길동", "character_id": 1, "profile_image_url": "data:...", "hp": 100, "special_gauge": 0 }
```

### Combat System

| Action | Effect |
|--------|--------|
| `right punch` / `left punch` | Base damage (캐릭터 attack) |
| `kick` | 1.2x damage |
| `block` | 방어 (피해 50% 감소, 게이지 +5) |
| `special` | 필살기 (게이지 100 소모, 3x damage) |
| `jump` / `walk` | 이동 (피해 없음) |

- **First-hit bonus**: 상대가 0.3초 내 공격 안 했으면 1.5x
- **Gauge charge**: 공격 시 +15, 방어 시 +5

---

## Auth

모든 HTTP 엔드포인트는 `X-API-Key` 헤더 필요 (`POST /api/face` 포함, WebSocket 제외)
""",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "service": "ghostdiedie-club"}

@app.get("/test")
def test_page():
    return FileResponse("test_ws.html")


app.include_router(users.router)
app.include_router(characters.router)
app.include_router(face.router)
app.include_router(matches.router)
app.include_router(rooms.router)
app.include_router(websocket.router)
