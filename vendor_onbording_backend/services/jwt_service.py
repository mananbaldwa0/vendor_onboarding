import os
import jwt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

SECRET = os.environ.get("JWT_SECRET", "dev_secret")
ALGORITHM = "HS256"
EXPIRY_DAYS = 7


def create_token(vendor_id: str, email: str) -> str:
    payload = {
        "vendor_id": vendor_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=EXPIRY_DAYS),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
