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
격투 게임 백엔드 서버 — 모션 인식 기반 실시간 대전

## 게임 흐름
1. `POST /api/rooms` → 방 생성 (4자리 코드 반환)
2. `POST /api/rooms/{code}/join` → 상대방 참가
3. `WebSocket /ws/{code}` → 양쪽 연결 시 `game_start` 전송
4. CV 모션 감지 → `player_action` 전송 → 서버가 데미지 계산
5. HP 0 → `game_end` 전송

## 전투 시스템
| 액션 | 효과 |
|---|---|
| `right punch` / `left punch` | 기본 데미지 (캐릭터 attack 값) |
| `kick` | 데미지 1.2배 |
| `block` | 방어 (받는 데미지 50% 감소, 게이지 +5) |
| `special` | 필살기 (게이지 100 소모, 데미지 3배) |
| `jump` / `walk` | 이동 (데미지 없음) |

- **선빵 보너스**: 상대가 0.3초 내 공격 안 했으면 데미지 1.5배
- **게이지 충전**: 공격 시 +15, 방어 시 +5

## WebSocket 메시지 타입
| 타입 | 방향 | 설명 |
|---|---|---|
| `game_start` | 서버 → 클라 | 게임 시작 (양쪽 플레이어 정보) |
| `action_result` | 서버 → 공격자 | 내 공격 결과 (데미지, HP, 게이지) |
| `hit_received` | 서버 → 수비자 | 맞은 결과 (데미지, HP, 게이지) |
| `game_end` | 서버 → 양쪽 | KO — 승자/패자/소요시간 |
| `opponent_left` | 서버 → 클라 | 상대 퇴장 |
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
