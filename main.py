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
  1. Capture or choose a photo
     POST /api/face (file) → { face_id, face_url }
     → Store face_id and face_url on the frontend

  2. Enter a name and click Create or Join
     GET /api/user/register?name=...&face_id=... → { user_id, name, profile_image_url }
     → Store user_id on the frontend

[Create Room Page]
  3. Create a room
     GET /api/room/create?user_id=...&character_id=... → { code, owner, expires_in }
     → Show the 8-digit code on screen

  4. Wait for the opponent (poll every 1.5 seconds)
     GET /api/room/status?code=... → { status, owner, guest, both_confirmed }
     → If guest is not null, the opponent has joined

  5. Click the Confirm button
     GET /api/room/confirm?code=...&user_id=... → { confirmed, both_confirmed }
     → If both_confirmed is false, keep polling room/status

  6. Both players confirm → connect WebSocket
     wss://{host}/ws/{code}
     → Once both sides connect, the server sends game_start → move to the game screen

[Join Room Page]
  3. Enter the 8-digit code and join
     GET /api/room/join?code=...&user_id=...&character_id=...
     → { success, code, owner, guest }
     → Show the owner's information (name, photo) on screen

  4. Click the Confirm button
     GET /api/room/confirm?code=...&user_id=... → { confirmed, both_confirmed }
     → If both_confirmed is false, keep polling room/status

  5. Both players confirm → connect WebSocket
     → game_start → game screen

[Game Page]
  Real-time combat over WebSocket messages
  Client → Server: { type: "player_action", action: "..." }
  Server → Client: action_result / hit_received / game_end / opponent_left
```

---

## HTTP API

### Face

| Method | Endpoint | Params | Response |
|--------|----------|--------|----------|
| `POST` | `/api/face` | `file` (multipart image) | `{ face_id, face_url }` — 256x256 circular crop PNG (base64) |

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

**owner/guest response format**:
```json
{ "user_id": "abc123", "name": "John Doe", "profile_image_url": "data:image/png;base64,...", "role": "owner" }
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

**Connection rule**: both players must complete HTTP `/api/room/confirm` before connecting (otherwise close 4001)

### Server → Client

| Type | When | Payload |
|------|------|---------|
| `game_start` | Both WS connections are established | `{ player_index, me: PlayerState, opponent: PlayerState }` |
| `action_result` | I attack | `{ action, damage, first_hit, blocked, is_special, my_hp, opponent_hp, my_gauge, opponent_gauge }` |
| `hit_received` | The opponent attacks | `{ action, damage, first_hit, blocked, is_special, my_hp, opponent_hp, my_gauge, opponent_gauge }` |
| `game_end` | KO occurs | `{ winner_index, winner_name, loser_name, duration_seconds }` |
| `opponent_left` | Opponent disconnects | `{}` |

### Client → Server

| Type | Payload |
|------|---------|
| `player_action` | `{ type: "player_action", action: "right punch" \\| "left punch" \\| "kick" \\| "block" \\| "special" }` |

### PlayerState (included in game_start)

```json
{ "name": "John Doe", "character_id": 1, "profile_image_url": "data:...", "hp": 100, "special_gauge": 0 }
```

### Combat System

| Action | Effect |
|--------|--------|
| `right punch` / `left punch` | Base damage (character attack) |
| `kick` | 1.2x damage |
| `block` | Guard (50% damage reduction, gauge +5) |
| `special` | Special move (costs 100 gauge, 3x damage) |
| `jump` / `walk` | Movement (no damage) |

- **First-hit bonus**: 1.5x if the opponent has not attacked within 0.3 seconds
- **Gauge charge**: +15 on attack, +5 on guard

---

## Auth

All HTTP endpoints require the `X-API-Key` header (`POST /api/face` included, WebSocket excluded)
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
