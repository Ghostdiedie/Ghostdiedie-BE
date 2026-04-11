"""
Ghostdiedie Club Backend
FastAPI + Supabase + WebSocket
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from routers import characters, matches, rooms, websocket

app = FastAPI(title="Ghostdiedie Club API", version="0.1.0")

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
