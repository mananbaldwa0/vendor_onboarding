from fastapi import APIRouter, HTTPException
from models.schemas import LoginRequest, LoginResponse
from services.supabase_client import get_supabase
from services.jwt_service import create_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    sb = get_supabase()

    result = sb.table("vendors").select("*").eq("email", body.email).execute()

    if result.data:
        vendor = result.data[0]
    else:
        insert = sb.table("vendors").insert({"email": body.email}).execute()
        vendor = insert.data[0]

    token = create_token(vendor_id=vendor["id"], email=vendor["email"])
    return LoginResponse(token=token, vendor_id=vendor["id"])
