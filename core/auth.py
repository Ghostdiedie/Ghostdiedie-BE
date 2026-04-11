from fastapi import HTTPException, Depends
from fastapi.security import APIKeyHeader
from core.config import API_KEY

api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(key: str = Depends(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
