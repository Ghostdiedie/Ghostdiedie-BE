# Ghostdiedie Club Backend

Backend server for **Ghostdiedie**, a motion-based fighting game.
Built with FastAPI + Supabase + WebSocket for room matching, real-time combat, and match history.

---

## Tech Stack

| Area | Technology |
|---|---|
| Server Framework | FastAPI (Python) |
| Database | Supabase (PostgreSQL) |
| Real-time | WebSocket (combat) |
| Face Processing | OpenCV + Pillow (256×256 circular crop) |
| Deployment | Railway |
| Domain | `api.ghostdiedie.club` (Porkbun → CNAME → Railway) |

---

## Project Structure

```
files/
├── main.py                 # FastAPI app entry point
├── core/
│   ├── config.py           # Supabase client, environment variables
│   └── auth.py             # API key authentication
├── routers/
│   ├── face.py             # Face upload / crop API
│   ├── users.py            # User registration API
│   ├── rooms.py            # Room create / join / confirm API
│   ├── characters.py       # Character query / image API
│   ├── matches.py          # Match result / leaderboard API
│   └── websocket.py        # WebSocket battle logic
├── models/
│   └── schemas.py          # Pydantic models (request/response/WS messages)
├── services/
│   ├── room_manager.py     # Room management (in-memory)
│   ├── user_manager.py     # User management
│   └── combat.py           # Damage calculation / combat logic
├── schema.sql              # DB schema (for Supabase SQL Editor)
├── test_ws.html            # WebSocket test page
├── Procfile                # Railway deployment config
└── requirements.txt
```

---

## Local Setup

### 1. Environment Setup

```bash
cd files
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the project root:

```
SUPABASE_URL=https://xxxxxxxxxxxxxxxxxxxx.supabase.co
SUPABASE_KEY=your-anon-key-here
API_KEY=your-api-key-here
```

Ask Minsoo for the actual values.

### 3. Run the Server

```bash
uvicorn main:app --reload --port 8000
```

### 4. Verify

- http://localhost:8000 — server status
- http://localhost:8000/docs — Swagger API docs
- http://localhost:8000/test — WebSocket test page

---

## Deployment URLs

| Purpose | URL |
|---|---|
| API | `https://api.ghostdiedie.club` |
| API Docs | `https://api.ghostdiedie.club/docs` |
| WS Test | `https://api.ghostdiedie.club/test` |

---

## Authentication

All `/api/*` HTTP endpoints require the `X-API-Key` header (WebSocket excluded).

```
X-API-Key: (ask Minsu)
```

---

## Full Client Flow

```
[Lobby Page]
  1. Take/select photo
     POST /api/face (file) → { face_id, face_url }

  2. Enter name, click Create/Join
     GET /api/user/register?name=...&face_id=... → { user_id, name, profile_image_url }

[Create Room Page]
  3. Create room
     GET /api/room/create?user_id=...&character_id=... → { code, owner, expires_in }

  4. Wait for opponent (poll every 1.5s)
     GET /api/room/status?code=... → { status, owner, guest, both_confirmed }

  5. Click Confirm
     GET /api/room/confirm?code=...&user_id=...
     → keep polling room/status until both_confirmed is true

  6. Both confirmed → connect WebSocket
     wss://{host}/ws/{code}
     → server sends game_start when both connected → game begins

[Join Room Page]
  3. Enter code, click Join
     GET /api/room/join?code=...&user_id=...&character_id=...

  4. Confirm → poll → WebSocket connect (same as above)

[Game Page]
  Real-time combat via WebSocket messages
  Client → Server: { type: "player_action", action: "..." }
  Server → Client: action_result / hit_received / game_end / opponent_left
```

---

## HTTP API

### Face

| Method | Endpoint | Params | Response |
|---|---|---|---|
| `POST` | `/api/face` | `file` (multipart image) | `{ face_id, face_url }` — 256×256 circular crop PNG (base64) |

### User

| Method | Endpoint | Params | Response |
|---|---|---|---|
| `GET` | `/api/user/register` | `name`, `face_id` | `{ status, user_id, name, profile_image_url }` |

### Room

| Method | Endpoint | Params | Response |
|---|---|---|---|
| `GET` | `/api/room/create` | `user_id`, `character_id` | `{ code, owner, expires_in }` |
| `GET` | `/api/room/join` | `code`, `user_id`, `character_id` | `{ success, code, owner, guest }` |
| `GET` | `/api/room/confirm` | `code`, `user_id` | `{ confirmed, both_confirmed }` |
| `GET` | `/api/room/status` | `code` | `{ code, status, owner, guest, both_confirmed, expires_in }` |
| `GET` | `/api/room/character` | `code`, `user_id`, `character_id` | `{ updated, character_id }` |

**Room status flow**: `waiting` → `ready` → `confirmed` → `playing` → `finished`

**owner/guest response format**:
```json
{ "user_id": "abc123", "name": "Player1", "profile_image_url": "data:image/png;base64,...", "role": "owner" }
```

### Characters

| Method | Endpoint | Params | Response |
|---|---|---|---|
| `GET` | `/api/characters` | — | `[{ id, name, max_hp, max_special_gauge, image_url }]` |
| `GET` | `/api/characters/{id}` | — | `{ id, name, max_hp, attack, max_special_gauge, image_url }` |
| `POST` | `/api/characters/{id}/image` | `file` (WebP) | `{ character_id, image_url }` |
| `GET` | `/api/characters/{id}/image` | — | WebP image binary (no auth required) |

### Matches

| Method | Endpoint | Params | Response |
|---|---|---|---|
| `POST` | `/api/matches` | JSON body | `{ match_id, created_at }` |
| `GET` | `/api/leaderboard` | `limit?` (default 10) | `[{ player_name, wins }]` |

---

## WebSocket

### `wss://{host}/ws/{room_code}`

**Connection requirement**: Both players must complete `/api/room/confirm` before connecting (otherwise closed with 4001)

### Server → Client

| Type | When | Payload |
|---|---|---|
| `game_start` | Both WS connected | `{ player_index, me: PlayerState, opponent: PlayerState }` |
| `action_result` | You attacked | `{ action, damage, first_hit, blocked, is_special, my_hp, opponent_hp, my_gauge, opponent_gauge }` |
| `hit_received` | Opponent attacked | `{ action, damage, first_hit, blocked, is_special, my_hp, opponent_hp, my_gauge, opponent_gauge }` |
| `game_end` | KO occurs | `{ winner_index, winner_name, loser_name, duration_seconds }` |
| `opponent_left` | Opponent disconnected | `{}` |

### Client → Server

| Type | Payload |
|---|---|
| `player_action` | `{ type: "player_action", action: "right punch" \| "left punch" \| "kick" \| "block" \| "special" }` |

### PlayerState

```json
{ "name": "Player1", "character_id": 1, "profile_image_url": "data:...", "hp": 100, "special_gauge": 0 }
```

---

## Combat System

The server calculates all damage. Clients only send actions.

| Action | Effect |
|---|---|
| `right punch` / `left punch` | Base damage (character attack stat) |
| `kick` | 1.2× damage |
| `block` | Defend (50% damage reduction, gauge +5) |
| `special` | Ultimate (costs 100 gauge, 3× damage) |
| `jump` / `walk` | Movement (no damage) |

- **First-hit bonus**: If opponent hasn't attacked within 0.3s, damage × 1.5
- **Gauge charge**: +15 on attack, +5 on defend

---

## DB Schema

Run `schema.sql` in the Supabase SQL Editor.

| Table | Description |
|---|---|
| `characters` | Character data (name, HP, attack power, special gauge) |
| `users` | User data (name, profile image) |
| `matches` | Match records (room code, winner/loser, duration) |

### Default Characters

| ID | Name | HP | Attack | Special Gauge |
|---|---|---|---|---|
| 1 | Jin | 100 | 15 | 100 |
| 2 | Kazuya | 110 | 13 | 120 |
| 3 | Heihachi | 95 | 17 | 80 |
| 4 | Paul | 105 | 14 | 100 |
| 5 | King | 115 | 12 | 90 |

---

## Related Repositories

- **Ghostdiedie-FE** — React + Three.js frontend (3D arena battle scene)
- **Ghostdiedie-CV** — Local Python CV bridge (webcam motion detection)