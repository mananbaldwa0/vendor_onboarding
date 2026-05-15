from fastapi import APIRouter, UploadFile, Form, Depends, HTTPException
from typing import Optional
from models.schemas import DocumentResponse
from services.supabase_client import get_supabase
from services.jwt_service import decode_token
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

router = APIRouter(prefix="/api/documents", tags=["documents"])
bearer = HTTPBearer()

BUCKET = "vendor-docs"
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/jpg", "image/png"}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MIN_SIZE_BYTES = 10 * 1024        # 10 KB
MAX_SIZE_BYTES = 10 * 1024 * 1024 # 10 MB


def get_vendor_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    try:
        payload = decode_token(credentials.credentials)
        return payload["vendor_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile,
    doc_type: str = Form(...),
    application_id: Optional[str] = Form(None),
    vendor_id: str = Depends(get_vendor_id),
):
    # Format check
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Upload PDF, JPG, or PNG only.")

    contents = await file.read()

    # Size check
    size = len(contents)
    if size < MIN_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too small (minimum 10 KB). Ensure file is not empty.")
    if size > MAX_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large (maximum 10 MB).")

    sb = get_supabase()
    path = f"{vendor_id}/{doc_type}/{file.filename}"

    # Overwrite if same path exists (re-upload of same doc type)
    try:
        sb.storage.from_(BUCKET).upload(path, contents, {"content-type": file.content_type, "upsert": "true"})
    except Exception:
        sb.storage.from_(BUCKET).update(path, contents, {"content-type": file.content_type})

    file_url = sb.storage.from_(BUCKET).get_public_url(path)

    # Upsert doc row: if floating (NULL application_id) row of same type exists → update in-place
    # Same logic as application table: draft-in-place until linked
    existing = (
        sb.table("documents")
        .select("id")
        .eq("vendor_id", vendor_id)
        .eq("doc_type", doc_type)
        .is_("application_id", "null")
        .execute()
    )

    if existing.data:
        doc_id = existing.data[0]["id"]
        sb.table("documents").update({
            "file_name": file.filename,
            "file_url": file_url,
        }).eq("id", doc_id).execute()
    else:
        doc_row = {
            "doc_type": doc_type,
            "file_name": file.filename,
            "file_url": file_url,
            "vendor_id": vendor_id,
        }
        if application_id:
            doc_row["application_id"] = application_id
        result = sb.table("documents").insert(doc_row).execute()
        doc_id = result.data[0]["id"]

    return DocumentResponse(doc_id=doc_id, file_url=file_url, doc_type=doc_type)


@router.get("/")
def list_documents(vendor_id: str = Depends(get_vendor_id)):
    """Return all floating + linked docs for this vendor."""
    sb = get_supabase()
    rows = (
        sb.table("documents")
        .select("doc_type, file_name, file_url")
        .eq("vendor_id", vendor_id)
        .execute()
    )
    return rows.data


@router.delete("/all")
def delete_all_documents(vendor_id: str = Depends(get_vendor_id)):
    """Delete all documents for this vendor. Used by test runner to reset state."""
    sb = get_supabase()
    sb.table("documents").delete().eq("vendor_id", vendor_id).execute()
    return {"deleted": True, "vendor_id": vendor_id}
