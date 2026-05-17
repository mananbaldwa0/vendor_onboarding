import os
import jwt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

SECRET = os.environ.get("JWT_SECRET", "dev_secret")
ALGORITHM = "HS256"
EXPIRY_DAYS = 7

ADMIN_EMAILS: set[str] = {
    e.strip() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()
}


def create_token(vendor_id: str, email: str) -> str:
    payload = {
        "vendor_id": vendor_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=EXPIRY_DAYS),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def create_admin_token(email: str) -> str:
    payload = {
        "email": email,
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(days=EXPIRY_DAYS),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=[ALGORITHM])


def is_admin_email(email: str) -> bool:
    return email in ADMIN_EMAILS
