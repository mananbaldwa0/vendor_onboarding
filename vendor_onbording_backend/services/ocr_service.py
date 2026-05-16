import logging
from services.supabase_client import get_supabase
from services.ocr_extractors.pdf_extractor import extract_pdf
from services.ocr_extractors.image_extractor import extract_image
from services.ai_service import run_ai_pipeline

logger = logging.getLogger(__name__)

BUCKET = "vendor-docs"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
SKIP_DOC_TYPES: set[str] = set()


def _download_file(sb, vendor_id: str, doc_type: str, file_name: str) -> bytes:
    path = f"{vendor_id}/{doc_type}/{file_name}"
    return sb.storage.from_(BUCKET).download(path)


def _set_ocr_status(sb, doc_id: str, status: str, ocr_json: dict | None = None):
    payload: dict = {"ocr_status": status}
    if ocr_json is not None:
        payload["ocr_json"] = ocr_json
    sb.table("documents").update(payload).eq("id", doc_id).execute()


def _extract(doc_type: str, file_name: str, file_bytes: bytes) -> dict:
    ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext in IMAGE_EXTENSIONS:
        return extract_image(doc_type, file_bytes)
    return extract_pdf(doc_type, file_bytes)


def run_ocr_pipeline(app_id: str, vendor_id: str):
    """
    Background task: OCR all docs linked to this application.
    Called after a clean submit — runs entirely in the background.
    """
    sb = get_supabase()

    docs = (
        sb.table("documents")
        .select("id, doc_type, file_name, vendor_id")
        .eq("application_id", app_id)
        .execute()
    ).data

    if not docs:
        logger.warning(f"ocr_pipeline: no docs found for app_id={app_id}")
        return

    for doc in docs:
        doc_id = doc["id"]
        doc_type = doc["doc_type"]
        file_name = doc["file_name"]

        if doc_type in SKIP_DOC_TYPES:
            _set_ocr_status(sb, doc_id, "skipped")
            continue

        try:
            _set_ocr_status(sb, doc_id, "processing")
            file_bytes = _download_file(sb, vendor_id, doc_type, file_name)
            result = _extract(doc_type, file_name, file_bytes)
            all_null = result and all(v is None for v in result.values())
            final_status = "failed" if all_null else "done"
            _set_ocr_status(sb, doc_id, final_status, result)
            logger.info(f"ocr_pipeline: done doc_id={doc_id} doc_type={doc_type}")
        except Exception as e:
            logger.error(f"ocr_pipeline: failed doc_id={doc_id} doc_type={doc_type} err={e}")
            _set_ocr_status(sb, doc_id, "failed", {"error": str(e)})

    run_ai_pipeline(app_id, vendor_id)
