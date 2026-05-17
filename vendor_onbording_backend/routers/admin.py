from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt

from services.jwt_service import create_admin_token, decode_token, is_admin_email
from services.supabase_client import get_supabase

router = APIRouter(prefix="/api/admin", tags=["admin"])
bearer = HTTPBearer()


class AdminLoginRequest(BaseModel):
    email: str


def get_admin(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/login")
def admin_login(body: AdminLoginRequest):
    if not is_admin_email(body.email):
        raise HTTPException(status_code=403, detail="Not an admin email")
    token = create_admin_token(body.email)
    return {"token": token, "email": body.email}


@router.get("/vendors")
def get_vendors(admin=Depends(get_admin)):
    sb = get_supabase()

    vendors = (
        sb.table("vendors")
        .select("id, email, created_at")
        .order("created_at", desc=True)
        .execute()
        .data
    )

    result = []
    for vendor in vendors:
        vid = vendor["id"]

        apps = (
            sb.table("applications")
            .select("*")
            .eq("vendor_id", vid)
            .order("version", desc=True)
            .limit(1)
            .execute()
            .data
        )
        app = apps[0] if apps else None

        review = None
        if app:
            reviews = (
                sb.table("reviews")
                .select("*")
                .eq("application_id", app["id"])
                .execute()
                .data
            )
            review = reviews[0] if reviews else None

        result.append({
            "vendor_id": vid,
            "email": vendor["email"],
            "created_at": vendor["created_at"],
            "latest_application": app,
            "review": review,
        })

    return result
