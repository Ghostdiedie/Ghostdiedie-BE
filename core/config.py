import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_KEY = os.getenv("API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL / SUPABASE_KEY 환경변수가 필요합니다 (.env 확인)")
if not API_KEY:
    raise RuntimeError("API_KEY 환경변수가 필요합니다 (.env 확인)")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
