# Ghostdiedie Club Backend

Fighting game backend server (FastAPI + Supabase + WebSocket)

## Tech Stack
- **Server:** FastAPI (Python)
- **DB:** Supabase (PostgreSQL)
- **Real-time:** WebSocket (room system + matches)
- **CV client:** OpenCV + MediaPipe (separate repo: `Ghostdiedie-CV`)
- **Frontend:** React Native (separate repo)
- **Deployment:** Railway
- **Domain:** `api.ghostdiedie.club` (Porkbun -> CNAME -> Railway)

## Project Structure
```
├── main.py                 # FastAPI app entry point
├── core/
│   ├── config.py           # Supabase client, environment variables
│   └── auth.py             # API key authentication
├── routers/
│   ├── characters.py       # Character API
│   ├── matches.py          # Match result API
│   ├── rooms.py            # Room create/join API
│   └── websocket.py        # WebSocket battle logic
├── models/
│   └── schemas.py          # Pydantic models (request/response/WS messages)
├── services/
│   └── room_manager.py     # Room management (in-memory)
├── schema.sql              # DB schema
├── test_ws.html            # WebSocket test page
└── requirements.txt
```

## Local Setup

### 1. Environment Setup
```bash
git clone git@github.com:Ghostdiedie/Ghostdiedie-BE.git
cd Ghostdiedie-BE
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
Ask Minsu for the actual values.

### 3. Run the Server
```bash
uvicorn main:app --reload --port 8000
```

### 4. Verify
- http://localhost:8000 — server status
- http://localhost:8000/docs — Swagger API docs
- http://localhost:8000/test — WebSocket test page

## Deployment URLs
- **API:** `https://api.ghostdiedie.club`
- **API docs:** `https://api.ghostdiedie.club/docs`
- **WebSocket test:** `https://api.ghostdiedie.club/test`

## Authentication
All `/api/*` endpoints require API key authentication. Include this header in requests:
```
X-API-Key: (ask Minsu)
```

## DB Schema
Run `schema.sql` in the Supabase SQL Editor to create the tables.

| Table | Description |
|---|---|
| `characters` | Character data (name, HP, attack power, special gauge) |
| `matches` | Match result records (room code, winner/loser, duration) |

### Characters
| ID | Name | HP | Attack | Special Gauge |
|---|---|---|---|---|
| 1 | Jin | 100 | 15 | 100 |
| 2 | Kazuya | 110 | 13 | 120 |
| 3 | Heihachi | 95 | 17 | 80 |
| 4 | Paul | 105 | 14 | 100 |
| 5 | King | 115 | 12 | 90 |

## API Spec

### REST API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/characters` | List all characters |
| GET | `/api/characters/{id}` | Get character details |
| POST | `/api/matches` | Save a match result |
| GET | `/api/leaderboard?limit=10` | Player win ranking |
| POST | `/api/rooms` | Create a room (returns a 4-character code) |
| POST | `/api/rooms/{code}/join` | Join a room |
| GET | `/api/rooms/{code}` | Get room details |

### WebSocket

| Endpoint | Description |
|---|---|
| `wss://api.ghostdiedie.club/ws/{room_code}` | Real-time match connection |

## CV Client Integration

The `Ghostdiedie-CV` repo detects punch motions from a camera and sends them to this server through WebSocket.

### Connection Flow
```
[Camera] -> MediaPipe motion detection -> action_queue -> WebSocket -> [This server] -> damage calculation -> result broadcast to both players
```

### Run the CV Client
```bash
cd Ghostdiedie-CV
pip install -r requirements.txt
python3 main.py
```

CV `.env` configuration:
```
SERVER_URL=https://api.ghostdiedie.club
WS_URL=wss://api.ghostdiedie.club
API_KEY=<API key>
```

## Game Flow

### Room States
`waiting` -> `ready` -> `playing` -> `finished`

### Full Flow
1. Player 1 -> `POST /api/rooms` -> receives room code (for example, `ABCD`) -> status: `waiting`
2. Player 2 -> `POST /api/rooms/ABCD/join` -> joins room -> status: `ready`
3. Both players -> connect to `wss://api.ghostdiedie.club/ws/ABCD`
4. Once both are connected -> `game_start` is sent automatically -> status: `playing`
5. CV detects a motion -> sends `player_action` -> **server calculates damage** -> results are sent to both players
6. HP reaches 0 or below -> `game_end` is sent automatically -> status: `finished`

### Combat System
The server calculates damage. Clients only need to send actions.

| Action | Damage | Description |
|---|---|---|
| `right punch` | character attack | Right punch |
| `left punch` | character attack | Left punch |
| `kick` | attack x 1.2 | Kick (stronger than a punch) |
| `block` | - | Defend (reduces incoming damage by 50%, gauge +5) |
| `special` | attack x 3.0 | Special move (costs 100 gauge) |
| `jump` | - | Jump (movement) |
| `walk` | - | Walk (movement) |
| `idle` | - | Idle |

**First-hit bonus:** If the opponent does not attack within 0.3 seconds, damage is multiplied by **1.5**
**Gauge charge:** +15 on attack, +5 on defense

### WebSocket Message Types

**Client -> Server:**
| Type | Description |
|---|---|
| `player_action` | Send a player action (`action` field required) |

**Server -> Client:**
| Type | Target | Description |
|---|---|---|
| `game_start` | Both | Game start (player info, HP, gauge) |
| `action_result` | Attacker | Your attack result (damage, first hit, block status, both HP/gauges) |
| `hit_received` | Defender | Result of getting hit (damage, first hit, block status, both HP/gauges) |
| `game_end` | Both | KO -> winner, loser, duration |
| `opponent_left` | Remaining player | Opponent disconnected |

### Request Examples

**Create room:**
```json
POST /api/rooms
{
  "player_name": "Minsu",
  "character_id": 1,
  "profile_image_url": "https://example.com/face.jpg"
}
-> { "room_code": "ABCD", "status": "waiting", "players": [...] }
```

**Join room:**
```json
POST /api/rooms/ABCD/join
{
  "player_name": "Cheolsu",
  "character_id": 2,
  "profile_image_url": "https://example.com/face2.jpg"
}
-> { "room_code": "ABCD", "status": "ready", "players": [...] }
```

**Save match result:**
```json
POST /api/matches
{
  "room_code": "ABCD",
  "winner_name": "Minsu",
  "loser_name": "Cheolsu",
  "winner_character_id": 1,
  "loser_character_id": 2,
  "duration_seconds": 87
}
```

**WebSocket send (client -> server):**
```json
{ "type": "player_action", "action": "right punch" }
```

**WebSocket receive - `action_result` (to attacker):**
```json
{
  "type": "action_result",
  "action": "right punch",
  "damage": 22,
  "first_hit": true,
  "blocked": false,
  "is_special": false,
  "my_hp": 100,
  "opponent_hp": 88,
  "my_gauge": 15,
  "opponent_gauge": 0
}
```

**WebSocket receive - `hit_received` (to defender):**
```json
{
  "type": "hit_received",
  "action": "right punch",
  "damage": 22,
  "first_hit": true,
  "blocked": false,
  "is_special": false,
  "my_hp": 88,
  "opponent_hp": 100,
  "my_gauge": 0,
  "opponent_gauge": 15
}
```

**WebSocket receive - `game_end` (to both players):**
```json
{
  "type": "game_end",
  "winner_index": 0,
  "winner_name": "Minsu",
  "loser_name": "Cheolsu",
  "duration_seconds": 87
}
```

### React Native Example
```js
const API = "https://api.ghostdiedie.club";
const HEADERS = {
  "Content-Type": "application/json",
  "X-API-Key": "YOUR_API_KEY",
};

// Character list
const res = await fetch(`${API}/api/characters`, { headers: HEADERS });
const characters = await res.json();

// Create room
const room = await fetch(`${API}/api/rooms`, {
  method: "POST",
  headers: HEADERS,
  body: JSON.stringify({
    player_name: "Minsu",
    character_id: 1,
    profile_image_url: "https://example.com/face.jpg",
  }),
}).then(r => r.json());

// Connect WebSocket
const ws = new WebSocket(`wss://api.ghostdiedie.club/ws/${room.room_code}`);

ws.onmessage = (e) => {
  const data = JSON.parse(e.data);
  switch (data.type) {
    case "game_start":
      // data.player_index (0=P1, 1=P2), data.me, data.opponent
      // data.me.hp, data.me.special_gauge, etc.
      break;
    case "action_result":
      // My attack result: data.damage, data.first_hit, data.blocked, data.is_special
      // data.my_hp, data.opponent_hp, data.my_gauge, data.opponent_gauge
      break;
    case "hit_received":
      // Hit result: data.damage, data.first_hit, data.blocked, data.is_special
      // data.my_hp, data.opponent_hp, data.my_gauge, data.opponent_gauge
      break;
    case "game_end":
      // data.winner_index, data.winner_name, data.loser_name, data.duration_seconds
      break;
    case "opponent_left":
      // Opponent left the match
      break;
  }
};

// Send attack action (damage is calculated by the server)
ws.send(JSON.stringify({ type: "player_action", action: "right punch" }));
```
