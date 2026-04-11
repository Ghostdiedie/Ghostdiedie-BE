# Tekken Backend (FastAPI + Supabase)

3D 텍켄 게임의 백엔드 서버입니다.

## 기술 스택
- **서버:** FastAPI (Python)
- **DB:** Supabase (PostgreSQL)
- **프론트:** React Native (별도 레포)

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
SUPABASE_KEY=팀 노션 또는 민수에게 문의
```

### 3. 서버 실행
```bash
uvicorn main:app --reload --port 8000
```

### 4. 확인
- http://localhost:8000 - 서버 상태 확인
- http://localhost:8000/docs - Swagger API 문서 (프론트 개발 시 여기 참고)

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

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/characters` | 전체 캐릭터 목록 |
| GET | `/api/characters/{id}` | 캐릭터 상세 |
| POST | `/api/matches` | 매치 결과 저장 |
| GET | `/api/leaderboard?limit=10` | 플레이어 승수 랭킹 |

### POST /api/matches 요청 예시
```json
{
  "player_name": "민수",
  "winner_character_id": 1,
  "loser_character_id": 2,
  "duration_seconds": 87
}
```

### React Native에서 호출 예시
```js
const API = "https://api.ghostdiedie.club";

// 캐릭터 목록
const res = await fetch(`${API}/api/characters`);
const characters = await res.json();

// 매치 저장
await fetch(`${API}/api/matches`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    player_name: "민수",
    winner_character_id: 1,
    loser_character_id: 2,
    duration_seconds: 87,
  }),
});
```

## 배포
- **플랫폼:** Railway
- **도메인:** `api.ghostdiedie.club` (GoDaddy → CNAME으로 Railway 연결)