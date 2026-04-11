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

## Game Flow (HTTP → WebSocket)
1. `GET /api/room/create?player_name=...&character_id=...` → 8-digit room code
2. `GET /api/room/join?code=...&player_name=...&character_id=...` → join room
3. `GET /api/room/confirm?code=...&player_index=0` → both players confirm
4. `GET /api/room/status?code=...` → poll confirm/game state
5. `WebSocket /ws/{code}` → both connect after confirm → `game_start` sent
6. CV motion detection sends `player_action` → server calculates damage
7. When HP reaches 0, `game_end` is sent

## HTTP Endpoints (query parameters, low overhead)
- **room/create** — create room, get 8-digit code
- **room/join** — join by code
- **room/confirm** — each player confirms readiness
- **room/status** — poll room state

## WebSocket (real-time combat only)
- Connect after both players confirmed
- `game_start`, `action_result`, `hit_received`, `game_end`, `opponent_left`
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
