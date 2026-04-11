-- Supabase 대시보드 > SQL Editor 에서 그대로 실행하세요

-- 캐릭터 테이블
create table if not exists characters (
  id                bigserial primary key,
  name              text not null,
  max_hp            int  not null default 100,
  attack            int  not null default 10,
  max_special_gauge int  not null default 100,
  description       text
);

-- 매치 결과 테이블
create table if not exists matches (
  id                  uuid primary key default gen_random_uuid(),
  room_code           text not null,
  winner_name         text not null,
  loser_name          text not null,
  winner_character_id bigint references characters(id),
  loser_character_id  bigint references characters(id),
  duration_seconds    int  not null,
  created_at          timestamptz not null default now()
);

-- 샘플 캐릭터 데이터
insert into characters (name, max_hp, attack, max_special_gauge, description) values
  ('Jin',      100, 15, 100, '미시마 진'),
  ('Kazuya',   110, 13, 120, '미시마 카즈야'),
  ('Heihachi',  95, 17,  80, '미시마 헤이하치'),
  ('Paul',     105, 14, 100, '폴 피닉스'),
  ('King',     115, 12,  90, '킹')
on conflict do nothing;

-- 해커톤용: anon key로 읽기/쓰기 허용 (RLS 끄기)
alter table characters disable row level security;
alter table matches    disable row level security;
