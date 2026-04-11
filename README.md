# Ghostdiedie Club Backend

격투 게임 백엔드 서버 (FastAPI + Supabase + WebSocket)

## 기술 스택
- **서버:** FastAPI (Python)
- **DB:** Supabase (PostgreSQL)
- **실시간:** WebSocket (방 시스템 + 대전)
- **프론트:** React Native (별도 레포)
- **배포:** Railway
- **도메인:** `api.ghostdiedie.club` (Porkbun → CNAME → Railway)

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
SUPABASE_URL=https://pdbhbsfnfcjmyrrsixqo.supabase.co
SUPABASE_KEY=민수에게 문의
API_KEY=민수에게 문의
```

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
| `characters` | 캐릭터 정보 (이름, HP, 공격력) |
| `matches` | 매치 결과 기록 |

### 샘플 캐릭터
| ID | 이름 | HP | 공격력 |
|---|---|---|---|
| 1 | Jin | 100 | 15 |
| 2 | Kazuya | 110 | 13 |
| 3 | Heihachi | 95 | 17 |
| 4 | Paul | 105 | 14 |
| 5 | King | 115 | 12 |

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

1. 플레이어1 → `POST /api/rooms` → 방 코드 받음 (예: `ABCD`)
2. 플레이어2 → `POST /api/rooms/ABCD/join` → 입장
3. 둘 다 → `wss://api.ghostdiedie.club/ws/ABCD` WebSocket 연결
4. 공격/이동 JSON 주고받기 → 상대에게 자동 전달
5. 연결 끊기면 상대에게 `opponent_left` 알림

### 요청 예시

**방 생성:**
```json
POST /api/rooms
{ "player_name": "민수", "character_id": 1 }
→ { "room_code": "ABCD", "status": "waiting" }
```

**방 참가:**
```json
POST /api/rooms/ABCD/join
{ "player_name": "철수", "character_id": 2 }
→ { "room_code": "ABCD", "status": "playing" }
```

**WebSocket 메시지 예시:**
```json
{ "type": "move", "x": 100, "y": 50 }
{ "type": "attack", "damage": 15 }
{ "type": "block" }
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
  body: JSON.stringify({ player_name: "민수", character_id: 1 }),
}).then(r => r.json());

// WebSocket 연결
const ws = new WebSocket(`wss://api.ghostdiedie.club/ws/${room.room_code}`);
ws.onmessage = (e) => {
  const data = JSON.parse(e.data);
  // data.type: "move", "attack", "block", "opponent_joined", "opponent_left"
};

// 공격 보내기
ws.send(JSON.stringify({ type: "attack", damage: 15 }));
```