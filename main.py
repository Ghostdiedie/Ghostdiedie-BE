"""
Ghostdiedie Club Backend
FastAPI + Supabase + WebSocket
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from routers import characters, matches, rooms, websocket

app = FastAPI(
    title="Ghostdiedie Club API",
    version="0.2.0",
    description="""
Fighting game backend server with motion-based real-time battles

## Game Flow
1. `POST /api/rooms` -> create a room and receive a 4-character code
2. `POST /api/rooms/{code}/join` -> the opponent joins the room
3. `WebSocket /ws/{code}` -> `game_start` is sent when both players connect
4. CV motion detection sends `player_action` -> the server calculates damage
5. When HP reaches 0, `game_end` is sent

## Combat System
| Action | Effect |
|---|---|
| `right punch` / `left punch` | Base damage (character attack stat) |
| `kick` | 1.2x damage |
| `block` | Defend (50% reduced incoming damage, +5 gauge) |
| `special` | Special move (costs 100 gauge, deals 3x damage) |
| `jump` / `walk` | Movement (no damage) |

- **First-hit bonus**: damage is multiplied by 1.5 if the opponent has not attacked within 0.3 seconds
- **Gauge charge**: +15 on attack, +5 on defense

## WebSocket Message Types
| Type | Direction | Description |
|---|---|---|
| `game_start` | server -> client | Game start (both players' info) |
| `action_result` | server -> attacker | Your attack result (damage, HP, gauge) |
| `hit_received` | server -> defender | Result of getting hit (damage, HP, gauge) |
| `game_end` | server -> both | KO -> winner, loser, duration |
| `opponent_left` | server -> client | Opponent disconnected |
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


app.include_router(characters.router)
app.include_router(matches.router)
app.include_router(rooms.router)
app.include_router(websocket.router)
