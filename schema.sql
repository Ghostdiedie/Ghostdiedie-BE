-- Run this directly in Supabase Dashboard > SQL Editor

-- Character table
create table if not exists characters (
  id                bigserial primary key,
  name              text not null,
  max_hp            int  not null default 100,
  attack            int  not null default 10,
  max_special_gauge int  not null default 100,
  description       text
);

-- Match results table
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

-- Sample character data
insert into characters (name, max_hp, attack, max_special_gauge, description) values
  ('Jin',      100, 15, 100, 'Mishima Jin'),
  ('Kazuya',   110, 13, 120, 'Mishima Kazuya'),
  ('Heihachi',  95, 17,  80, 'Mishima Heihachi'),
  ('Paul',     105, 14, 100, 'Paul Phoenix'),
  ('King',     115, 12,  90, 'King')
on conflict do nothing;

-- Hackathon setup: allow read/write with anon key (disable RLS)
alter table characters disable row level security;
alter table matches    disable row level security;
