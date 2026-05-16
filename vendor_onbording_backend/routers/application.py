from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from datetime import datetime, timezone
from models.schemas import ApplicationSubmit, ApplicationResponse, StatusResponse
from services.supabase_client import get_supabase
from services.jwt_service import decode_token
from services.validation import validate_application
from services.ocr_service import run_ocr_pipeline
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

router = APIRouter(prefix="/api/application", tags=["application"])
bearer = HTTPBearer()


def get_vendor_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    try:
        payload = decode_token(credentials.credentials)
        return payload["vendor_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _upsert_application(sb, vendor_id: str, data: dict) -> tuple[str, int]:
    """
    Upsert logic:
    - Existing draft → update in-place, return same (id, version)
    - No draft + existing submitted → new row, version = latest + 1  (resubmit cycle)
    - Nothing exists → new row, version = 1
    """
    existing_draft = (
        sb.table("applications")
        .select("id,version")
        .eq("vendor_id", vendor_id)
        .eq("status", "draft")
        .order("version", desc=True)
        .limit(1)
        .execute()
    )

    if existing_draft.data:
        app_id = existing_draft.data[0]["id"]
        version = existing_draft.data[0]["version"]
        sb.table("applications").update(data).eq("id", app_id).execute()
        return app_id, version

    latest = (
        sb.table("applications")
        .select("version")
        .eq("vendor_id", vendor_id)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    version = (latest.data[0]["version"] + 1) if latest.data else 1
    data["vendor_id"] = vendor_id
    data["version"] = version
    result = sb.table("applications").insert(data).execute()
    return result.data[0]["id"], version


def _link_docs(sb, vendor_id: str, app_id: str):
    """Link all floating (NULL application_id) docs to this application."""
    sb.table("documents").update({"application_id": app_id}).eq("vendor_id", vendor_id).is_("application_id", "null").execute()


def _get_uploaded_doc_types(sb, vendor_id: str) -> list[str]:
    """Return all doc_types ever uploaded for this vendor across all versions."""
    uploaded = (
        sb.table("documents")
        .select("doc_type")
        .eq("vendor_id", vendor_id)
        .execute()
    )
    return list({row["doc_type"] for row in uploaded.data})


@router.post("/submit", response_model=ApplicationResponse)
def submit_application(
    body: ApplicationSubmit,
    background_tasks: BackgroundTasks,
    vendor_id: str = Depends(get_vendor_id),
):
    sb = get_supabase()

    uploaded_doc_types = _get_uploaded_doc_types(sb, vendor_id)

    data = body.model_dump(mode="json", exclude_none=True)
    errors = validate_application(data, uploaded_doc_types)

    if errors:
        data["status"] = "draft"
        app_id, version = _upsert_application(sb, vendor_id, data)
        _link_docs(sb, vendor_id, app_id)
        return ApplicationResponse(
            application_id=app_id,
            status="draft",
            version=version,
            errors=errors,
        )

    data["status"] = "submitted"
    data["submitted_at"] = datetime.now(timezone.utc).isoformat()
    app_id, version = _upsert_application(sb, vendor_id, data)
    _link_docs(sb, vendor_id, app_id)

    # Trigger OCR in background — non-blocking
    background_tasks.add_task(run_ocr_pipeline, app_id, vendor_id)

    return ApplicationResponse(application_id=app_id, status="submitted", version=version)


@router.post("/draft")
def save_draft(body: ApplicationSubmit, vendor_id: str = Depends(get_vendor_id)):
    sb = get_supabase()

    data = body.model_dump(mode="json", exclude_none=True)
    data["status"] = "draft"
    app_id, version = _upsert_application(sb, vendor_id, data)
    _link_docs(sb, vendor_id, app_id)
    return {"application_id": app_id, "status": "draft", "version": version}


@router.delete("/reset")
def reset_vendor_applications(vendor_id: str = Depends(get_vendor_id)):
    """Delete all applications for this vendor. Used by test runner to reset state."""
    sb = get_supabase()
    sb.table("applications").delete().eq("vendor_id", vendor_id).execute()
    return {"deleted": True, "vendor_id": vendor_id}


@router.get("/status", response_model=StatusResponse)
def get_status(vendor_id: str = Depends(get_vendor_id)):
    sb = get_supabase()
    result = (
        sb.table("applications")
        .select("id,status,submitted_at,version")
        .eq("vendor_id", vendor_id)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return StatusResponse(application=None)

    app = result.data[0]
    return StatusResponse(
        application_id=app["id"],
        status=app["status"],
        submitted_at=app.get("submitted_at"),
        version=app["version"],
    )


@router.get("/{app_id}")
def get_application(app_id: str, vendor_id: str = Depends(get_vendor_id)):
    sb = get_supabase()
    result = sb.table("applications").select("*").eq("id", app_id).eq("vendor_id", vendor_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Application not found")

    return result.data[0]
