# Ghostdiedie Club Backend

격투 게임 백엔드 서버 (FastAPI + Supabase + WebSocket)

## 기술 스택
- **서버:** FastAPI (Python)
- **DB:** Supabase (PostgreSQL)
- **실시간:** WebSocket (방 시스템 + 대전)
- **CV 클라이언트:** OpenCV + MediaPipe (별도 레포: `Ghostdiedie-CV`)
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

## CV 클라이언트 연결

`Ghostdiedie-CV` 레포에서 카메라로 펀치 모션을 감지하고, 이 서버로 WebSocket을 통해 전송합니다.

### 연결 구조
```
[카메라] → MediaPipe 모션 감지 → action_queue → WebSocket → [이 서버] → 데미지 계산 → 양쪽에 결과 전송
```

### CV 클라이언트 실행
```bash
cd Ghostdiedie-CV
pip install -r requirements.txt
python3 main.py
```

CV `.env` 설정:
```
SERVER_URL=https://api.ghostdiedie.club
WS_URL=wss://api.ghostdiedie.club
API_KEY=<API 키>
```

## 게임 흐름

### 방 상태
`waiting` → `ready` → `playing` → `finished`

### 전체 흐름
1. 플레이어1 → `POST /api/rooms` → 방 코드 받음 (예: `ABCD`) → 상태: `waiting`
2. 플레이어2 → `POST /api/rooms/ABCD/join` → 입장 → 상태: `ready`
3. 둘 다 → `wss://api.ghostdiedie.club/ws/ABCD` WebSocket 연결
4. 둘 다 연결되면 → `game_start` 메시지 자동 전송 → 상태: `playing`
5. CV 모션 감지 → `player_action` 전송 → **서버가 데미지 계산** → 양쪽에 결과 전송
6. HP 0 이하 → `game_end` 자동 전송 → 상태: `finished`

### 전투 시스템
서버가 데미지를 계산합니다. 클라이언트는 액션만 전송하면 됩니다.

| 액션 | 데미지 | 설명 |
|---|---|---|
| `right punch` | 캐릭터 attack | 오른쪽 주먹 |
| `left punch` | 캐릭터 attack | 왼쪽 주먹 |
| `kick` | attack x 1.2 | 발차기 (펀치보다 강함) |
| `block` | - | 방어 (받는 데미지 50% 감소, 게이지 +5) |
| `special` | attack x 3.0 | 필살기 (게이지 100 소모) |
| `jump` | - | 점프 (이동) |
| `walk` | - | 걷기 (이동) |
| `idle` | - | 대기 |

**선빵 보너스:** 상대가 0.3초 내 공격하지 않았으면 데미지 **1.5배**
**게이지 충전:** 공격 시 +15, 방어 시 +5

### WebSocket 메시지 타입

**클라 → 서버:**
| 타입 | 설명 |
|---|---|
| `player_action` | 플레이어 동작 전송 (`action` 필드 필수) |

**서버 → 클라:**
| 타입 | 대상 | 설명 |
|---|---|---|
| `game_start` | 양쪽 | 게임 시작 (플레이어 정보, HP, 게이지) |
| `action_result` | 공격자 | 내 공격 결과 (데미지, 선빵, 방어 여부, 양쪽 HP/게이지) |
| `hit_received` | 수비자 | 맞은 결과 (데미지, 선빵, 방어 여부, 양쪽 HP/게이지) |
| `game_end` | 양쪽 | KO — 승자/패자/소요시간 |
| `opponent_left` | 남은 쪽 | 상대 퇴장 |

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

**WebSocket 송신 (클라 → 서버):**
```json
{ "type": "player_action", "action": "right punch" }
```

**WebSocket 수신 — action_result (공격자에게):**
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

**WebSocket 수신 — hit_received (수비자에게):**
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

**WebSocket 수신 — game_end (양쪽에게):**
```json
{
  "type": "game_end",
  "winner_index": 0,
  "winner_name": "민수",
  "loser_name": "철수",
  "duration_seconds": 87
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
      // data.me.hp, data.me.special_gauge 등
      break;
    case "action_result":
      // 내 공격 결과: data.damage, data.first_hit, data.blocked, data.is_special
      // data.my_hp, data.opponent_hp, data.my_gauge, data.opponent_gauge
      break;
    case "hit_received":
      // 맞은 결과: data.damage, data.first_hit, data.blocked, data.is_special
      // data.my_hp, data.opponent_hp, data.my_gauge, data.opponent_gauge
      break;
    case "game_end":
      // data.winner_index, data.winner_name, data.loser_name, data.duration_seconds
      break;
    case "opponent_left":
      // 상대 퇴장
      break;
  }
};

// 공격 보내기 (데미지는 서버가 계산)
ws.send(JSON.stringify({ type: "player_action", action: "right punch" }));
```
