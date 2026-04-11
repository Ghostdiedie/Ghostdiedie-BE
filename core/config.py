import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_KEY = os.getenv("API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL / SUPABASE_KEY environment variables are required (check .env)")
if not API_KEY:
    raise RuntimeError("API_KEY environment variable is required (check .env)")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
