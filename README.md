# Ghostdiedie Club Backend

격투 게임 백엔드 서버 (FastAPI + Supabase + WebSocket)

## 기술 스택
- **서버:** FastAPI (Python)
- **DB:** Supabase (PostgreSQL)
- **실시간:** WebSocket (방 시스템 + 대전)
- **프론트:** React Native (별도 레포)
- **배포:** Railway
- **도메인:** `api.ghostdiedie.club` (Porkbun → CNAME → Railway)

## 프로젝트 구조
```
├── main.py                 # FastAPI 앱 진입점
├── core/
│   ├── config.py           # Supabase 클라이언트, 환경변수
│   └── auth.py             # API Key 인증
├── routers/
│   ├── characters.py       # 캐릭터 API
│   ├── matches.py          # 매치 결과 API
│   ├── rooms.py            # 방 생성/참가 API
│   └── websocket.py        # WebSocket 대전
├── models/
│   └── schemas.py          # Pydantic 모델 (요청/응답/WS 메시지)
├── services/
│   └── room_manager.py     # 방 관리 (인메모리)
├── schema.sql              # DB 스키마
├── test_ws.html            # WebSocket 테스트 페이지
└── requirements.txt
```

## 로컬 실행 방법

### 1. 환경 설정
```bash
git clone git@github.com:Ghostdiedie/Ghostdiedie-BE.git
cd Ghostdiedie-BE
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 환경변수 설정
`.env` 파일을 루트에 생성:
```
SUPABASE_URL=https://xxxxxxxxxxxxxxxxxxxx.supabase.co
SUPABASE_KEY=your-anon-key-here
API_KEY=your-api-key-here
```
값은 민수에게 문의

### 3. 서버 실행
```bash
uvicorn main:app --reload --port 8000
```

### 4. 확인
- http://localhost:8000 — 서버 상태
- http://localhost:8000/docs — Swagger API 문서
- http://localhost:8000/test — WebSocket 테스트 페이지

## 배포 URL
- **API:** `https://api.ghostdiedie.club`
- **API 문서:** `https://api.ghostdiedie.club/docs`
- **WebSocket 테스트:** `https://api.ghostdiedie.club/test`

## 인증
모든 `/api/*` 엔드포인트는 API Key 인증 필요. 요청 시 헤더에 추가:
```
X-API-Key: (민수에게 문의)
```

## DB 스키마
Supabase SQL Editor에서 `schema.sql` 실행하면 테이블 생성됨.

| 테이블 | 설명 |
|---|---|
| `characters` | 캐릭터 정보 (이름, 체력, 공격력, 필살기 게이지) |
| `matches` | 매치 결과 기록 (방 코드, 승자/패자, 소요시간) |

### 캐릭터
| ID | 이름 | 체력 | 공격력 | 필살기 게이지 |
|---|---|---|---|---|
| 1 | Jin | 100 | 15 | 100 |
| 2 | Kazuya | 110 | 13 | 120 |
| 3 | Heihachi | 95 | 17 | 80 |
| 4 | Paul | 105 | 14 | 100 |
| 5 | King | 115 | 12 | 90 |

## API 스펙

### REST API

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/characters` | 전체 캐릭터 목록 |
| GET | `/api/characters/{id}` | 캐릭터 상세 |
| POST | `/api/matches` | 매치 결과 저장 |
| GET | `/api/leaderboard?limit=10` | 플레이어 승수 랭킹 |
| POST | `/api/rooms` | 방 생성 (4자리 코드 반환) |
| POST | `/api/rooms/{code}/join` | 방 참가 |
| GET | `/api/rooms/{code}` | 방 정보 조회 |

### WebSocket

| Endpoint | 설명 |
|---|---|
| `wss://api.ghostdiedie.club/ws/{room_code}` | 실시간 대전 연결 |

## 게임 흐름

### 방 상태
`waiting` → `ready` → `playing` → `finished`

### 전체 흐름
1. 플레이어1 → `POST /api/rooms` → 방 코드 받음 (예: `ABCD`) → 상태: `waiting`
2. 플레이어2 → `POST /api/rooms/ABCD/join` → 입장 → 상태: `ready`
3. 둘 다 → `wss://api.ghostdiedie.club/ws/ABCD` WebSocket 연결
4. 둘 다 연결되면 → `game_start` 메시지 자동 전송 → 상태: `playing`
5. 공격/이동 JSON 주고받기 → 상대에게 자동 전달
6. 게임 종료 → `POST /api/matches`로 결과 저장 → 상태: `finished`

### 액션 타입
| 액션 | 설명 |
|---|---|
| `right punch` | 오른쪽 주먹 |
| `left punch` | 왼쪽 주먹 |
| `kick` | 발차기 |
| `jump` | 점프 |
| `block` | 방어 |
| `special` | 필살기 (게이지 소모) |

### WebSocket 메시지 타입
| 타입 | 방향 | 설명 |
|---|---|---|
| `game_start` | 서버 → 클라 | 두 플레이어 연결 완료, 게임 시작 |
| `player_action` | 클라 → 서버 → 상대 | 플레이어 동작 전달 |
| `state_update` | 클라 → 서버 → 상대 | HP/게이지 동기화 |
| `round_start` | 서버 → 클라 | 라운드 시작 |
| `round_end` | 서버 → 클라 | 라운드 종료 |
| `game_end` | 서버 → 클라 | 게임 종료, 최종 승자 |
| `opponent_left` | 서버 → 클라 | 상대 퇴장 |

### 요청 예시

**방 생성:**
```json
POST /api/rooms
{
  "player_name": "민수",
  "character_id": 1,
  "profile_image_url": "https://example.com/face.jpg"
}
→ { "room_code": "ABCD", "status": "waiting", "players": [...] }
```

**방 참가:**
```json
POST /api/rooms/ABCD/join
{
  "player_name": "철수",
  "character_id": 2,
  "profile_image_url": "https://example.com/face2.jpg"
}
→ { "room_code": "ABCD", "status": "ready", "players": [...] }
```

**매치 결과 저장:**
```json
POST /api/matches
{
  "room_code": "ABCD",
  "winner_name": "민수",
  "loser_name": "철수",
  "winner_character_id": 1,
  "loser_character_id": 2,
  "duration_seconds": 87
}
```

**WebSocket 메시지 (player_action):**
```json
{ "type": "player_action", "action": "right punch", "damage": 15 }
```

**WebSocket 메시지 (state_update):**
```json
{
  "type": "state_update",
  "player_hp": 85,
  "opponent_hp": 70,
  "player_gauge": 30,
  "opponent_gauge": 20
}
```

### React Native에서 호출 예시
```js
const API = "https://api.ghostdiedie.club";
const HEADERS = {
  "Content-Type": "application/json",
  "X-API-Key": "YOUR_API_KEY",
};

// 캐릭터 목록
const res = await fetch(`${API}/api/characters`, { headers: HEADERS });
const characters = await res.json();

// 방 생성
const room = await fetch(`${API}/api/rooms`, {
  method: "POST",
  headers: HEADERS,
  body: JSON.stringify({
    player_name: "민수",
    character_id: 1,
    profile_image_url: "https://example.com/face.jpg",
  }),
}).then(r => r.json());

// WebSocket 연결
const ws = new WebSocket(`wss://api.ghostdiedie.club/ws/${room.room_code}`);

ws.onmessage = (e) => {
  const data = JSON.parse(e.data);
  switch (data.type) {
    case "game_start":
      // data.player_index (0=P1, 1=P2), data.me, data.opponent
      break;
    case "player_action":
      // data.action ("right punch", "kick", ...), data.damage
      break;
    case "state_update":
      // data.player_hp, data.opponent_hp, data.player_gauge, data.opponent_gauge
      break;
    case "opponent_left":
      // 상대 퇴장
      break;
  }
};

// 공격 보내기
ws.send(JSON.stringify({ type: "player_action", action: "right punch", damage: 15 }));
```
