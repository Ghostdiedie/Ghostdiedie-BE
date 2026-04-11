# Tekken Backend (FastAPI + Supabase)

## 1. Supabase 세팅
1. https://app.supabase.com 에서 본인 프로젝트 열기
2. 좌측 메뉴 **SQL Editor** → `schema.sql` 내용 복붙 후 Run
3. 좌측 메뉴 **Project Settings → API** → `Project URL`과 `anon public` 키 복사

## 2. 로컬 실행
```bash
cd tekken-backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env 파일 열어서 SUPABASE_KEY 채우기

uvicorn main:app --reload --port 8000
```

브라우저에서 확인:
- http://localhost:8000/api/characters
- http://localhost:8000/docs  ← Swagger 자동 문서 (프론트한테 이거 보여주면 됨!)

## 3. API 스펙 (프론트에 공유할 내용)

| Method | Endpoint | 설명 |
|---|---|---|
| GET  | `/api/characters` | 전체 캐릭터 목록 |
| GET  | `/api/characters/{id}` | 캐릭터 상세 |
| POST | `/api/matches` | 매치 결과 저장 |
| GET  | `/api/leaderboard?limit=10` | 랭킹 |

### POST /api/matches Body
```json
{
  "player_name": "민수",
  "winner_character_id": 1,
  "loser_character_id": 2,
  "duration_seconds": 87
}
```

## 4. 배포 (Railway 추천 - 5분이면 끝)
1. 코드 GitHub에 push
2. https://railway.app → New Project → Deploy from GitHub
3. Variables 탭에 `SUPABASE_URL`, `SUPABASE_KEY` 추가
4. Settings → Networking → Generate Domain (임시 주소 나옴)
5. **GoDaddy 도메인 연결:** Railway가 준 도메인을 GoDaddy DNS에서 CNAME으로 등록
   - GoDaddy → My Products → DNS → Add Record
   - Type: `CNAME`, Name: `api`, Value: `xxx.up.railway.app`
   - 그러면 `api.본인도메인.com` 으로 접속 가능

## 5. React Native에서 호출 예시
```js
const API = "https://api.본인도메인.com";

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
