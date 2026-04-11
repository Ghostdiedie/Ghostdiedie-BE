# Ghostdiedie Club Backend

모션 인식 격투 게임 **Ghostdiedie**의 백엔드 서버입니다.
FastAPI + Supabase + WebSocket 기반으로 방 매칭, 실시간 전투, 전적 관리를 처리합니다.

---

## 기술 스택

| 영역 | 기술 |
|---|---|
| 서버 프레임워크 | FastAPI (Python) |
| 데이터베이스 | Supabase (PostgreSQL) |
| 실시간 통신 | WebSocket (전투) |
| 얼굴 처리 | OpenCV + Pillow (256×256 원형 크롭) |
| 배포 | Railway |
| 도메인 | `api.ghostdiedie.club` (Porkbun → CNAME → Railway) |

---

## 프로젝트 구조

```
files/
├── main.py                 # FastAPI 앱 엔트리포인트
├── core/
│   ├── config.py           # Supabase 클라이언트, 환경 변수
│   └── auth.py             # API 키 인증
├── routers/
│   ├── face.py             # 얼굴 업로드 / 크롭 API
│   ├── users.py            # 유저 등록 API
│   ├── rooms.py            # 방 생성 / 참가 / 확인 API
│   ├── characters.py       # 캐릭터 조회 / 이미지 API
│   ├── matches.py          # 전적 저장 / 리더보드 API
│   └── websocket.py        # WebSocket 전투 로직
├── models/
│   └── schemas.py          # Pydantic 모델 (요청/응답/WS 메시지)
├── services/
│   ├── room_manager.py     # 방 관리 (인메모리)
│   ├── user_manager.py     # 유저 관리
│   └── combat.py           # 데미지 계산 / 전투 로직
├── schema.sql              # DB 스키마 (Supabase SQL Editor용)
├── test_ws.html            # WebSocket 테스트 페이지
├── Procfile                # Railway 배포 설정
└── requirements.txt
```

---

## 로컬 셋업

### 1. 환경 구성

```bash
cd files
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 환경 변수

프로젝트 루트에 `.env` 파일 생성:

```
SUPABASE_URL=https://xxxxxxxxxxxxxxxxxxxx.supabase.co
SUPABASE_KEY=your-anon-key-here
API_KEY=your-api-key-here
```

실제 값은 민수에게 문의하세요.

### 3. 서버 실행

```bash
uvicorn main:app --reload --port 8000
```

### 4. 확인

- http://localhost:8000 — 서버 상태
- http://localhost:8000/docs — Swagger API 문서
- http://localhost:8000/test — WebSocket 테스트 페이지

---

## 배포 URL

| 용도 | URL |
|---|---|
| API | `https://api.ghostdiedie.club` |
| API 문서 | `https://api.ghostdiedie.club/docs` |
| WS 테스트 | `https://api.ghostdiedie.club/test` |

---

## 인증

모든 `/api/*` HTTP 엔드포인트는 `X-API-Key` 헤더가 필요합니다 (WebSocket 제외).

```
X-API-Key: (민수에게 문의)
```

---

## 클라이언트 전체 플로우

```
[로비 페이지]
  1. 사진 촬영/선택
     POST /api/face (file) → { face_id, face_url }

  2. 이름 입력 후 Create/Join 클릭
     GET /api/user/register?name=...&face_id=... → { user_id, name, profile_image_url }

[방 생성 페이지]
  3. 방 생성
     GET /api/room/create?user_id=...&character_id=... → { code, owner, expires_in }

  4. 상대 대기 (1.5초 간격 폴링)
     GET /api/room/status?code=... → { status, owner, guest, both_confirmed }

  5. Confirm → GET /api/room/confirm?code=...&user_id=...
     → both_confirmed가 true가 될 때까지 폴링

  6. 양쪽 confirm 완료 → WebSocket 연결
     wss://{host}/ws/{code}
     → 양쪽 연결 시 game_start 전송 → 게임 시작

[방 참가 페이지]
  3. 코드 입력 후 Join
     GET /api/room/join?code=...&user_id=...&character_id=...

  4. Confirm → 폴링 → WebSocket 연결 (위와 동일)

[게임 페이지]
  WebSocket 메시지로 실시간 전투
  Client → Server: { type: "player_action", action: "..." }
  Server → Client: action_result / hit_received / game_end / opponent_left
```

---

## HTTP API

### Face

| Method | Endpoint | Params | Response |
|---|---|---|---|
| `POST` | `/api/face` | `file` (multipart image) | `{ face_id, face_url }` — 256×256 원형 크롭 PNG (base64) |

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

**owner/guest 응답 형식**:
```json
{ "user_id": "abc123", "name": "홍길동", "profile_image_url": "data:image/png;base64,...", "role": "owner" }
```

### Characters

| Method | Endpoint | Params | Response |
|---|---|---|---|
| `GET` | `/api/characters` | — | `[{ id, name, max_hp, max_special_gauge, image_url }]` |
| `GET` | `/api/characters/{id}` | — | `{ id, name, max_hp, attack, max_special_gauge, image_url }` |
| `POST` | `/api/characters/{id}/image` | `file` (WebP) | `{ character_id, image_url }` |
| `GET` | `/api/characters/{id}/image` | — | WebP image binary (인증 불필요) |

### Matches

| Method | Endpoint | Params | Response |
|---|---|---|---|
| `POST` | `/api/matches` | JSON body | `{ match_id, created_at }` |
| `GET` | `/api/leaderboard` | `limit?` (기본 10) | `[{ player_name, wins }]` |

---

## WebSocket

### `wss://{host}/ws/{room_code}`

**연결 조건**: 양쪽 모두 `/api/room/confirm` 완료 후에만 연결 가능 (미확인 시 4001 close)

### Server → Client

| Type | 시점 | Payload |
|---|---|---|
| `game_start` | 양쪽 WS 연결 완료 | `{ player_index, me: PlayerState, opponent: PlayerState }` |
| `action_result` | 내가 공격 | `{ action, damage, first_hit, blocked, is_special, my_hp, opponent_hp, my_gauge, opponent_gauge }` |
| `hit_received` | 상대가 공격 | `{ action, damage, first_hit, blocked, is_special, my_hp, opponent_hp, my_gauge, opponent_gauge }` |
| `game_end` | KO 발생 | `{ winner_index, winner_name, loser_name, duration_seconds }` |
| `opponent_left` | 상대 연결 끊김 | `{}` |

### Client → Server

| Type | Payload |
|---|---|
| `player_action` | `{ type: "player_action", action: "right punch" \| "left punch" \| "kick" \| "block" \| "special" }` |

### PlayerState

```json
{ "name": "홍길동", "character_id": 1, "profile_image_url": "data:...", "hp": 100, "special_gauge": 0 }
```

---

## 전투 시스템

서버에서 데미지를 계산합니다. 클라이언트는 액션만 전송하면 됩니다.

| Action | 효과 |
|---|---|
| `right punch` / `left punch` | 기본 데미지 (캐릭터 attack) |
| `kick` | 1.2× 데미지 |
| `block` | 방어 (피해 50% 감소, 게이지 +5) |
| `special` | 필살기 (게이지 100 소모, 3× 데미지) |
| `jump` / `walk` | 이동 (피해 없음) |

- **First-hit bonus**: 상대가 0.3초 내 공격 안 했으면 1.5×
- **Gauge charge**: 공격 시 +15, 방어 시 +5

---

## DB 스키마

`schema.sql`을 Supabase SQL Editor에서 실행하세요.

| 테이블 | 설명 |
|---|---|
| `characters` | 캐릭터 데이터 (이름, HP, 공격력, 필살기 게이지) |
| `users` | 유저 데이터 (이름, 프로필 이미지) |
| `matches` | 전적 기록 (방 코드, 승자/패자, 소요 시간) |

### 기본 캐릭터

| ID | Name | HP | Attack | Special Gauge |
|---|---|---|---|---|
| 1 | Jin | 100 | 15 | 100 |
| 2 | Kazuya | 110 | 13 | 120 |
| 3 | Heihachi | 95 | 17 | 80 |
| 4 | Paul | 105 | 14 | 100 |
| 5 | King | 115 | 12 | 90 |

---

## 관련 저장소

- **Ghostdiedie-FE** — React + Three.js 프론트엔드 (3D 대전 씬)
- **Ghostdiedie-CV** — 로컬 Python CV 브리지 (웹캠 동작 감지)