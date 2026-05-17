import json
import logging
import os
import re
from datetime import date, datetime, timezone

from groq import Groq
# import httpx  # Ollama local fallback — uncomment when switching
from services.email_service import send_vendor_flags_email
from services.supabase_client import get_supabase

STATE_GST_CODES = {
    "Andhra Pradesh": "37", "Arunachal Pradesh": "12", "Assam": "18",
    "Bihar": "10", "Chhattisgarh": "22", "Goa": "30", "Gujarat": "24",
    "Haryana": "06", "Himachal Pradesh": "02", "Jharkhand": "20",
    "Karnataka": "29", "Kerala": "32", "Madhya Pradesh": "23",
    "Maharashtra": "27", "Manipur": "14", "Meghalaya": "17",
    "Mizoram": "15", "Nagaland": "13", "Odisha": "21", "Punjab": "03",
    "Rajasthan": "08", "Sikkim": "11", "Tamil Nadu": "33",
    "Telangana": "36", "Tripura": "16", "Uttar Pradesh": "09",
    "Uttarakhand": "05", "West Bengal": "19", "Delhi": "07",
    "Jammu and Kashmir": "01", "Ladakh": "38", "Chandigarh": "04",
    "Dadra and Nagar Haveli and Daman and Diu": "26",
    "Lakshadweep": "31", "Puducherry": "34",
    "Andaman and Nicobar Islands": "35", "Andaman & Nicobar": "35",
}

PAN_CHAR_COMPANY_TYPE = {
    "C": {"Private Limited", "Public Limited"},
    "F": {"LLP", "Partnership Firm"},
    "P": {"Sole Proprietorship"},
}

logger = logging.getLogger(__name__)


def _normalize_date(raw: str | None) -> str | None:
    """Normalize to YYYY-MM-DD. Handles YYYY-MM-DD and DD-MM-YYYY / DD/MM/YYYY."""
    if not raw:
        return None
    raw = str(raw).strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', raw):
        return raw
    m = re.match(r'^(\d{2})[/-](\d{2})[/-](\d{4})$', raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


# ── Model config ────────────────────────────────────────────────────────────
# Switch: comment one block, uncomment the other

# Groq (active)
GROQ_MODEL = "llama-3.3-70b-versatile"
def _get_groq_client():
    return Groq(api_key=os.environ["GROQ_API_KEY"])

# Ollama local fallback (llama3.1:8b) — uncomment when switching
# OLLAMA_URL = "http://localhost:11434/api/chat"
# OLLAMA_MODEL = "llama3.1:8b"


def _upsert_review(sb, application_id: str, vendor_id: str, status: str, payload: dict | None = None):
    data: dict = {"application_id": application_id, "vendor_id": vendor_id, "ai_status": status}
    if payload:
        data.update(payload)
    existing = sb.table("reviews").select("id").eq("application_id", application_id).execute()
    if existing.data:
        sb.table("reviews").update(data).eq("application_id", application_id).execute()
    else:
        sb.table("reviews").insert(data).execute()


def _compute_exact_matches(form: dict, ocr: dict) -> dict:
    def _fetch(doc_type: str, field: str) -> tuple[str, str | None]:
        """
        Returns (state, value) where state is:
          "no_doc"  — doc not in ocr at all (not required for this vendor)
          "failed"  — doc OCR status != done (whole doc unreadable)
          "partial" — doc OCR done but this specific field is null (partial read)
          "ok"      — field extracted successfully
        """
        doc = ocr.get(doc_type)
        if doc is None:
            return ("no_doc", None)
        if doc.get("status") != "done":
            return ("failed", None)
        val = doc.get(field)
        if val is None or val == "":
            return ("partial", None)
        return ("ok", str(val).strip().upper())

    def _match(form_val, doc_type: str, ocr_field: str) -> bool | str | None:
        """
        Returns:
          True      — confirmed match
          False     — confirmed mismatch
          "partial" — doc OCR done but field missing (possible obscured/morphed doc)
          null      — whole doc failed OCR or doc not applicable for this vendor
        """
        state, ocr_val = _fetch(doc_type, ocr_field)
        if state in ("no_doc", "failed"):
            return None
        if state == "partial":
            return "partial"
        if form_val is None:
            return None
        return str(form_val).strip().upper() == ocr_val

    def _match_date(form_val, doc_type: str, ocr_field: str) -> bool | str | None:
        """Like _match but normalizes date formats before comparison."""
        state, ocr_val = _fetch(doc_type, ocr_field)
        if state in ("no_doc", "failed"):
            return None
        if state == "partial":
            return "partial"
        if form_val is None:
            return None
        norm_form = _normalize_date(str(form_val))
        norm_ocr = _normalize_date(ocr_val) if ocr_val else None
        if norm_form is None or norm_ocr is None:
            return None
        return norm_form == norm_ocr

    def _match_dpa_signed() -> bool | str | None:
        """Presence check for dpa.is_signed — True=present, "partial"=missing, None=failed/not uploaded.
        Actual is_signed=false flagging is handled by LLM from ocr directly."""
        doc = ocr.get("dpa")
        if doc is None:
            return None
        if doc.get("status") != "done":
            return None
        val = doc.get("is_signed")
        if val is None:
            return "partial"
        return True

    def _match_partnership_firm() -> bool | str | None:
        """Presence check for partnership_deed.firm_name — gets OCR status into exact_match_context.
        Fuzzy name comparison is handled by LLM from ocr directly."""
        doc = ocr.get("partnership_deed")
        if doc is None:
            return None
        if doc.get("status") != "done":
            return None
        val = doc.get("firm_name")
        if val is None:
            return "partial"
        return True

    # Fetch OCR values for cross-checks
    gstin_state, ocr_gstin = _fetch("gst_cert", "gstin")
    pan_state,   ocr_pan   = _fetch("pan_card", "pan_number")

    # GST cert state code (chars 0-1) vs form state
    ocr_gstin_state_match: bool | str | None = None
    if gstin_state == "partial":
        ocr_gstin_state_match = "partial"
    elif gstin_state == "ok" and ocr_gstin and form.get("state"):
        expected = STATE_GST_CODES.get(form["state"])
        ocr_gstin_state_match = (ocr_gstin[:2] == expected) if expected else None

    # GST cert embedded PAN (chars 2-11) vs form pan_number
    ocr_gstin_pan_match: bool | str | None = None
    if gstin_state == "partial":
        ocr_gstin_pan_match = "partial"
    elif gstin_state == "ok" and ocr_gstin and len(ocr_gstin) >= 12 and form.get("pan_number"):
        ocr_gstin_pan_match = ocr_gstin[2:12] == str(form["pan_number"]).strip().upper()

    # PAN card 4th char vs company_type
    ocr_pan_type_match: bool | str | None = None
    if pan_state == "partial":
        ocr_pan_type_match = "partial"
    elif pan_state == "ok" and ocr_pan and len(ocr_pan) >= 4 and form.get("company_type"):
        pan_char = ocr_pan[3]
        allowed = PAN_CHAR_COMPANY_TYPE.get(pan_char, set())
        ocr_pan_type_match = form["company_type"] in allowed

    return {
        # Form field vs OCR extracted value
        # true = match | false = mismatch | "partial" = doc read but field missing | null = whole doc failed or not applicable
        "pan_number":          _match(form.get("pan_number"),          "pan_card",         "pan_number"),
        "ifsc_code":           _match(form.get("ifsc_code"),           "cancelled_cheque", "ifsc_code"),
        "account_number":      _match(form.get("account_number"),      "cancelled_cheque", "account_number"),
        "gst_number":          _match(form.get("gst_number"),          "gst_cert",         "gstin"),
        "cin_number":          _match(form.get("cin_number"),          "incorporation",    "cin_number"),
        "incorporation_date":  _match_date(form.get("incorporation_date"), "incorporation", "incorporation_date"),
        "llp_number":          _match(form.get("llp_number"),          "llp_agreement",    "llp_number"),
        "msme_number":         _match(form.get("msme_number"),         "msme_cert",        "udyam_number"),
        "iso_cert_number":     _match(form.get("iso_cert_number"),     "iso_cert",         "cert_number"),
        "iso_expiry_date":     _match_date(form.get("iso_expiry_date"), "iso_cert",         "expiry_date"),
        # Presence-only checks — get OCR status into context for docs with no numeric exact match
        "dpa_is_signed":        _match_dpa_signed(),
        "partnership_firm_name": _match_partnership_firm(),
        # OCR cross-checks — derived from doc content
        "ocr_gstin_state_matches_form_state":   ocr_gstin_state_match,
        "ocr_gstin_pan_matches_form_pan":        ocr_gstin_pan_match,
        "ocr_pan_4th_char_matches_company_type": ocr_pan_type_match,
    }


# Maps each exact_match key to its source doc_type — used to look up OCR status for context
FIELD_TO_DOC: dict[str, str] = {
    "pan_number":                            "pan_card",
    "ifsc_code":                             "cancelled_cheque",
    "account_number":                        "cancelled_cheque",
    "gst_number":                            "gst_cert",
    "cin_number":                            "incorporation",
    "incorporation_date":                    "incorporation",
    "llp_number":                            "llp_agreement",
    "msme_number":                           "msme_cert",
    "iso_cert_number":                       "iso_cert",
    "ocr_gstin_state_matches_form_state":    "gst_cert",
    "ocr_gstin_pan_matches_form_pan":        "gst_cert",
    "ocr_pan_4th_char_matches_company_type": "pan_card",
    "iso_expiry_date":                       "iso_cert",
    "dpa_is_signed":                         "dpa",
    "partnership_firm_name":                 "partnership_deed",
}


def _compute_exact_match_context(exact_matches: dict, ocr_summary: dict) -> dict[str, str]:
    """
    Converts raw true/false/"partial"/null values into plain-English labels
    so the LLM knows exactly WHY each value is what it is.

    Labels:
      verified          — extracted and matches form value
      mismatch          — extracted but does not match form value
      partial_read      — doc OCR done but this specific field is null (possible obscured/edited doc)
      doc_ocr_failed    — whole doc could not be read at all
      not_applicable    — doc was not required for this vendor and was not uploaded
    """
    context = {}
    for field, value in exact_matches.items():
        doc_type = FIELD_TO_DOC.get(field, "unknown")
        if value is True:
            context[field] = "verified"
        elif value is False:
            context[field] = f"mismatch — value extracted from {doc_type} does not match form"
        elif value == "partial":
            context[field] = f"partial_read — {doc_type} OCR succeeded but this field is null; possible obscured or edited document"
        elif value is None:
            doc = ocr_summary.get(doc_type)
            if doc is None:
                context[field] = f"not_applicable — {doc_type} was not required for this vendor"
            elif doc.get("status") == "failed":
                context[field] = f"doc_ocr_failed — {doc_type} could not be read at all"
            elif doc.get("status") == "done":
                context[field] = f"not_applicable — form field not provided, cannot compare against {doc_type}"
            else:
                context[field] = f"not_applicable — {doc_type} OCR status is {doc.get('status')}"
    return context


ALLOWED_OCR_FIELDS: dict[str, set[str]] = {
    "pan_card":         {"pan_number", "name_on_card"},
    "cancelled_cheque": {"ifsc_code", "account_number", "account_holder_name", "cancelled_watermark"},
    "gst_cert":         {"gstin", "legal_name", "registration_date"},
    "incorporation":    {"cin_number", "company_name", "incorporation_date"},
    "llp_agreement":    {"llp_number", "company_name"},
    "partnership_deed": {"firm_name"},
    "iso_cert":         {"cert_number", "company_name", "expiry_date", "standard_text"},
    "dpa":              {"company_name", "is_signed", "signing_date"},
    "msme_cert":        {"udyam_number", "enterprise_name", "category"},
}


def _build_ocr_summary(docs: list[dict]) -> dict:
    summary = {}
    for doc in docs:
        doc_type = doc["doc_type"]
        ocr_json = doc.get("ocr_json") or {}
        status = doc.get("ocr_status", "not_started")
        entry = {"status": status}
        if status == "done":
            allowed = ALLOWED_OCR_FIELDS.get(doc_type, set())
            entry.update({k: v for k, v in ocr_json.items() if k in allowed})
        summary[doc_type] = entry
    return summary


SYSTEM_PROMPT = """You are a vendor onboarding risk analyst for a fintech company.

You receive:
- form: all vendor-submitted fields
- ocr: fields extracted from uploaded documents
- exact_match_context: pre-computed labels explaining what each field check found

Return a JSON object with EXACTLY these three keys (always present, use [] if empty):

{
  "user_flags":      [{ "field": str, "severity": "high|medium|low", "message": str }],
  "risk_factors":    [{ "factor": str (snake_case), "severity": "high|medium|low", "note": str }],
  "unreadable_docs": [{ "doc_type": str, "message": str }]
}

━━━ EXACT MATCH CONTEXT LABELS — what each value means and what to do ━━━

"verified"
  → field confirmed correct. Skip. Do not add any flag.

"mismatch — ..."
  → extracted value does not match form. Do BOTH:
    (1) user_flags: severity:high, tell vendor exactly which value is wrong and ask to correct
    (2) risk_factors: factor="<field_name>_mismatch", severity:high
  Exception: incorporation_date mismatch → severity:medium for both (date format differences are common)
  Exception: iso_expiry_date mismatch → severity:medium for both (date format differences are common)

"partial_read — ..."
  → doc was read but this specific field is missing. Possible obscured/edited document.
  → DO BOTH: (1) user_flags severity:medium asking vendor to re-upload clear unedited copy
             (2) risk_factors factor="partial_ocr_<doc_type>" severity:medium noting possible tampering

"doc_ocr_failed — ..."
  → whole doc could not be read. Do ALL THREE:
    (1) unreadable_docs: add entry with doc_type and message asking vendor to re-upload
    (2) user_flags: ONE entry per doc (even if multiple keys reference same doc), field=doc_type (e.g. "pan_card", "gst_cert"), severity:medium asking vendor to re-upload
    (3) risk_factors: factor="ocr_failed_<doc_type>" severity:low
  IMPORTANT: one user_flag per failed doc regardless of how many exact_match_context keys reference it

"not_applicable — ..."
  → doc was not required for this vendor. Skip entirely. Do not flag.

━━━ FUZZY NAME CHECKS (from ocr fields) ━━━

For each name check below, compare the extracted name against form.company_name and judge similarity:

  no_issue → same entity (abbreviations, "Pvt Ltd"="Private Limited", "Ltd"="Limited", etc.) → SKIP entirely, no entry
  low      → minor variation (slight word order, extra word, minor formatting) → risk_factor ONLY (severity:low), NO user_flag
  medium   → different name but possibly related (trading name, subsidiary, group entity) → BOTH user_flag + risk_factor (severity:medium)
  high     → completely unrelated entity → BOTH user_flag + risk_factor (severity:high)

Skip any name check where the OCR field is null or missing.

Name checks (only if doc was uploaded and OCR field is present):
- ocr.pan_card.name_on_card vs form.company_name → factor="pan_name_mismatch", user_flag field="pan_name"
- ocr.cancelled_cheque.account_holder_name vs form.company_name → factor="account_holder_name_mismatch", user_flag field="account_holder_name"
- ocr.gst_cert.legal_name vs form.company_name → factor="gst_legal_name_mismatch", user_flag field="gst_legal_name"
- ocr.incorporation.company_name vs form.company_name → factor="incorporation_name_mismatch", user_flag field="incorporation_company_name"
- ocr.llp_agreement.company_name vs form.company_name → factor="llp_name_mismatch", user_flag field="llp_company_name"
- ocr.iso_cert.company_name vs form.company_name → factor="iso_name_mismatch", user_flag field="iso_company_name"
- ocr.msme_cert.enterprise_name vs form.company_name → factor="msme_name_mismatch", user_flag field="msme_enterprise_name"
- ocr.partnership_deed.firm_name vs form.company_name → factor="partnership_name_mismatch", user_flag field="partnership_firm_name"
- ocr.dpa.is_signed = false → BOTH: user_flags field="dpa" severity:medium (ask vendor to upload signed DPA) + risk_factors factor="dpa_not_signed" severity:medium
- ocr.cancelled_cheque.cancelled_watermark = false → BOTH: user_flags field="cancelled_cheque" severity:low (inform vendor cheque does not appear cancelled — re-upload a properly cancelled cheque) + risk_factors factor="cancelled_cheque_no_watermark" severity:low
Note: exact_match_context keys "dpa_is_signed" and "partnership_firm_name" indicate OCR status only (partial/failed/done). "verified" means field was extracted — still check ocr.dpa.is_signed value above.

━━━ RISK FACTOR CHECKS (from form fields only) ━━━

CRITICAL: Only create risk_factors for conditions in the list below. Do NOT invent new risk factor names. Do NOT add a risk factor just because a field exists — only when the specific condition listed is true.

CRITICAL: For user_flags — each form field gets at most ONE entry even if multiple checks relate to it. Example: if both gst_number and ocr_gstin_pan both flag the same GST issue, merge into one user_flag for "gst_number".

Only flag these when the condition is EXPLICITLY AND EXACTLY true. Do NOT flag if condition is not met or unclear.

IMPORTANT — processes_data conditions:
- ONLY fire processes_data_no_soc2 if form.processes_data IS EXACTLY true (boolean true). If false, null, or missing → DO NOT fire.
- ONLY fire processes_data_no_iso if form.processes_data IS EXACTLY true (boolean true). If false, null, or missing → DO NOT fire.

IMPORTANT — ISO cert conditions:
- You receive "today" in the JSON. Use it to compare dates.
- ONLY fire iso_cert_expired if form.iso_expiry_date exists AND form.iso_expiry_date < today AND exact_match_context.iso_cert_number is NOT "not_applicable". If iso_cert_number is "not_applicable", the doc was never uploaded — do not fire any ISO flags at all.
- processes_data_no_iso checks form.iso_certified field ONLY. If form.iso_certified=true, do NOT fire processes_data_no_iso — even if the cert is expired. Expiry is a separate check (iso_cert_expired).

IMPORTANT — DPA conditions:
- ONLY flag DPA (not signed) if exact_match_context has a dpa-related key that is NOT "not_applicable" AND ocr.dpa.is_signed = false explicitly. If dpa is not_applicable, skip entirely.

IMPORTANT — no duplicates:
- For each doc_type, add at most ONE risk factor of a given type. If multiple exact_match_context keys point to the same doc_type with the same issue, create only one risk_factor entry.

Full condition list (form-based risk factors):
- form.iso_expiry_date exists AND form.iso_expiry_date < today AND iso_cert_number NOT not_applicable → BOTH: user_flags field="iso_cert" severity:high + risk_factors factor:iso_cert_expired severity:high
- form.processes_data=true AND form.soc2_audited=false → risk_factors factor:processes_data_no_soc2 severity:medium
- form.processes_data=true AND form.iso_certified=false → risk_factors factor:processes_data_no_iso severity:medium
- form.data_in_india=false (boolean false) → risk_factors factor:data_offshore severity:high
- form.employee_count vs form.annual_turnover implausible (e.g. 400 employees, <1 Cr) → risk_factors factor:employee_turnover_mismatch severity:high
- form.processes_data=true AND form.cyber_coverage_crores low relative to turnover → risk_factors factor:low_cyber_coverage severity:medium
- form.company_age_years < 2 → risk_factors factor:new_company severity:low
- form.service_nature vs form.annual_turnover implausible → risk_factors factor:service_turnover_mismatch severity:medium

━━━ OCR CROSS-CHECK CONTEXT MEANINGS ━━━

CRITICAL: Only act on a cross-check key if its exact_match_context label is "mismatch". If the label is "verified" or "not_applicable", skip entirely — no flag of any kind.

When exact_match_context label for these keys is "mismatch":
- ocr_gstin_state_matches_form_state: GST cert state code doesn't match declared state.
    → BOTH: user_flags field="gst_cert_state_mismatch" severity:high + risk_factors factor="gst_cert_state_mismatch" severity:high
- ocr_gstin_pan_matches_form_pan: PAN inside GST cert doesn't match vendor PAN.
    → risk_factors factor="gst_cert_entity_mismatch" severity:high always
    → If gst_number is ALSO mismatch, do NOT create a separate user_flag — the gst_number user_flag already covers it
    → If gst_number is NOT mismatch, also add user_flags field="gst_number" severity:high noting PAN-GSTIN mismatch
- ocr_pan_4th_char_matches_company_type: PAN entity type char doesn't match declared company type.
    → BOTH: user_flags field="pan_entity_type_mismatch" severity:high + risk_factors factor="pan_entity_type_mismatch" severity:high

━━━ FEW-SHOT EXAMPLES ━━━

Example 1 — verified field (skip it):
  exact_match_context: { "pan_number": "verified" }
  Output: no entry in any array for pan_number

Example 2 — mismatch on pan_number → BOTH user_flag AND risk_factor:
  exact_match_context: { "pan_number": "mismatch — value extracted from pan_card does not match form" }
  form.pan_number: "AABCX1234C", ocr.pan_card.pan_number: "AABCZ9999C"
  Output:
  user_flags: [{ "field": "pan_number", "severity": "high", "message": "The PAN number on your PAN card (AABCZ9999C) does not match the PAN number you submitted (AABCX1234C). Please upload the correct PAN card." }]
  risk_factors: [{ "factor": "pan_number_mismatch", "severity": "high", "note": "PAN on card (AABCZ9999C) does not match form PAN (AABCX1234C)." }]

Example 3 — partial_read on gst_cert:
  exact_match_context: { "gst_number": "partial_read — gst_cert OCR succeeded but this field is null; possible obscured or edited document" }
  Output:
  user_flags: [{ "field": "gst_number", "severity": "medium", "message": "Your GST certificate could not be fully read — the GSTIN field is missing. Please re-upload a clear, unedited copy." }]
  risk_factors: [{ "factor": "partial_ocr_gst_cert", "severity": "medium", "note": "GST cert OCR partial — GSTIN field missing. Possible obscured or edited document." }]

Example 4 — doc_ocr_failed on incorporation:
  exact_match_context: { "cin_number": "doc_ocr_failed — incorporation could not be read at all", "incorporation_date": "doc_ocr_failed — incorporation could not be read at all" }
  Output:
  unreadable_docs: [{ "doc_type": "incorporation", "message": "Your Certificate of Incorporation could not be read. Please re-upload a clear copy." }]
  user_flags: [{ "field": "incorporation", "severity": "medium", "message": "Your Certificate of Incorporation could not be read. Please re-upload a clear copy." }]
  risk_factors: [{ "factor": "ocr_failed_incorporation", "severity": "low", "note": "Incorporation cert OCR failed completely." }]
  NOTE: one user_flag even though both cin_number and incorporation_date reference the same doc.

Example 5 — not_applicable (skip entirely):
  exact_match_context: { "llp_number": "not_applicable — llp_agreement was not required for this vendor" }
  Output: no entry in any array for llp_number

Example 6 — fuzzy name: abbreviation (no_issue → skip entirely):
  form.company_name: "Silverline IT Solutions Private Limited"
  ocr.pan_card.name_on_card: "SILVERLINE IT SOLUTIONS PVT LTD"
  Output: no pan_name_mismatch entry. "Pvt Ltd" = "Private Limited" — same entity.

Example 7 — fuzzy name: completely different entity (high → both):
  form.company_name: "Silverline IT Solutions Pvt Ltd"
  ocr.cancelled_cheque.account_holder_name: "Rajesh Kumar Mehta"
  Output:
  user_flags: [{ "field": "account_holder_name", "severity": "high", "message": "The account holder on your cancelled cheque ('Rajesh Kumar Mehta') is a personal name and does not match your company. Please upload a cheque from your company's bank account." }]
  risk_factors: [{ "factor": "account_holder_name_mismatch", "severity": "high", "note": "Cheque account holder 'Rajesh Kumar Mehta' is a personal name unrelated to company 'Silverline IT Solutions Pvt Ltd'." }]

Example 8 — fuzzy name: minor variation (low → risk_factor only, no user_flag):
  form.company_name: "Silverline IT Solutions Pvt Ltd"
  ocr.incorporation.company_name: "Silverline Information Technology Solutions Pvt Ltd"
  Output:
  risk_factors: [{ "factor": "incorporation_name_mismatch", "severity": "low", "note": "Incorporation cert name is a minor variation — likely same entity with abbreviated trade name." }]
  (no user_flag — minor variation, vendor need not act)

Example 9 — incorporation_date mismatch → medium severity:
  exact_match_context: { "incorporation_date": "mismatch — value extracted from incorporation does not match form" }
  form.incorporation_date: "2018-03-15", ocr extracted: "2019-03-15"
  Output:
  user_flags: [{ "field": "incorporation_date", "severity": "medium", "message": "The incorporation date on your Certificate of Incorporation does not match what you submitted. Please verify and correct." }]
  risk_factors: [{ "factor": "incorporation_date_mismatch", "severity": "medium", "note": "Incorporation cert date does not match form-declared date." }]

Example 10 — gst_cert_state_mismatch → both user_flag AND risk_factor:
  exact_match_context: { "ocr_gstin_state_matches_form_state": "mismatch — value extracted from gst_cert does not match form" }
  Output:
  user_flags: [{ "field": "gst_cert_state_mismatch", "severity": "high", "message": "The state code in your GST certificate does not match your declared state. Please verify your GST number and state." }]
  risk_factors: [{ "factor": "gst_cert_state_mismatch", "severity": "high", "note": "GST cert state code does not match declared state." }]

Example 11 — not_applicable must NOT be flagged:
  form.iso_certified: false, exact_match_context: { "iso_cert_number": "not_applicable — iso_cert was not required for this vendor" }
  form.processes_data: false
  Output: no iso or dpa flags of any kind

Example 12 — not_applicable overrides form fields:
  form.iso_certified: true, form.iso_expiry_date: "2024-01-01" (past date)
  exact_match_context: { "iso_cert_number": "not_applicable — iso_cert was not required for this vendor" }
  Output: no iso flags. iso_cert_number is not_applicable — doc was not uploaded.

Example 13 — processes_data=false blocks soc2/iso risk factors:
  form.processes_data: false, form.soc2_audited: false, form.iso_certified: false
  Output: no processes_data_no_soc2, no processes_data_no_iso.

Example 14 — data_in_india=true means no risk:
  form.data_in_india: true
  Output: no data_offshore risk factor.

Example 15 — iso_cert_expired fires both user_flag AND risk_factor:
  form.iso_expiry_date: "2025-01-01" (before today), exact_match_context.iso_cert_number: "verified"
  Output:
  user_flags: [{ "field": "iso_cert", "severity": "high", "message": "Your ISO certificate expired on 2025-01-01. Please upload the renewed certificate." }]
  risk_factors: [{ "factor": "iso_cert_expired", "severity": "high", "note": "ISO cert expired January 2025." }]

Return only the JSON object. No explanation, no markdown, no text outside the JSON."""


def _compute_company_age_years(incorporation_date_str: str | None) -> int | None:
    if not incorporation_date_str:
        return None
    try:
        inc = date.fromisoformat(str(incorporation_date_str)[:10])
        today = date.today()
        return (today - inc).days // 365
    except Exception:
        return None


def _call_llm(form: dict, ocr_summary: dict, exact_matches: dict) -> dict:
    enriched_form = dict(form)
    if "company_age_years" not in enriched_form:
        enriched_form["company_age_years"] = _compute_company_age_years(form.get("incorporation_date"))
    enriched_form.pop("incorporation_date", None)

    exact_match_context = _compute_exact_match_context(exact_matches, ocr_summary)

    user_content = json.dumps({
        "today": date.today().isoformat(),
        "form": enriched_form,
        "ocr": ocr_summary,
        "exact_match_context": exact_match_context,
    }, default=str)

    # ── Groq ──────────────────────────────────────────────────────────────────
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    usage = response.usage
    logger.info(f"groq_tokens prompt={usage.prompt_tokens} completion={usage.completion_tokens} total={usage.total_tokens}")
    raw = response.choices[0].message.content

    # ── Ollama local fallback ─────────────────────────────────────────────────
    # payload = {
    #     "model": OLLAMA_MODEL,
    #     "messages": [
    #         {"role": "system", "content": SYSTEM_PROMPT},
    #         {"role": "user", "content": user_content},
    #     ],
    #     "stream": False,
    #     "format": "json",
    #     "options": {"temperature": 0.0, "num_ctx": 8192},
    # }
    # resp = httpx.post(OLLAMA_URL, json=payload, timeout=120.0)
    # resp.raise_for_status()
    # raw = resp.json()["message"]["content"]
    # logger.info(f"ollama_response model={OLLAMA_MODEL}")

    return json.loads(raw)


# ── Risk Scoring ──────────────────────────────────────────────────────────────

SEVERITY_WEIGHT = {"high": 10, "medium": 5, "low": 2}

# risk_factor name → user_flag field it corresponds to (if any)
# factors NOT in this map are internal-only — never escalated cross-version
RISK_FACTOR_TO_FLAG_FIELD: dict[str, str] = {
    # Partial OCR (field missing in doc)
    "partial_ocr_pan_card":              "pan_number",
    "partial_ocr_cancelled_cheque":      "cancelled_cheque",
    "partial_ocr_gst_cert":              "gst_number",
    "partial_ocr_incorporation":         "cin_number",
    "partial_ocr_llp_agreement":         "llp_number",
    "partial_ocr_msme_cert":             "msme_number",
    "partial_ocr_iso_cert":              "iso_cert_number",
    "partial_ocr_dpa":                   "dpa",
    "partial_ocr_partnership_deed":      "partnership_firm_name",
    # OCR failed (whole doc unreadable) — notified via unreadable_docs + DOC_TYPE_TO_NOTIFIED_FIELD
    "ocr_failed_pan_card":               "pan_number",
    "ocr_failed_cancelled_cheque":       "cancelled_cheque",
    "ocr_failed_gst_cert":               "gst_number",
    "ocr_failed_incorporation":          "cin_number",
    "ocr_failed_llp_agreement":          "llp_number",
    "ocr_failed_msme_cert":              "msme_number",
    "ocr_failed_iso_cert":               "iso_cert_number",
    "ocr_failed_dpa":                    "dpa",
    "ocr_failed_partnership_deed":       "partnership_firm_name",
    # Exact number/date mismatches
    "pan_number_mismatch":               "pan_number",
    "ifsc_code_mismatch":                "ifsc_code",
    "account_number_mismatch":           "account_number",
    "gst_number_mismatch":               "gst_number",
    "cin_number_mismatch":               "cin_number",
    "incorporation_date_mismatch":       "incorporation_date",
    "llp_number_mismatch":               "llp_number",
    "msme_number_mismatch":              "msme_number",
    "iso_cert_number_mismatch":          "iso_cert_number",
    "iso_expiry_date_mismatch":          "iso_expiry_date",
    # OCR cross-check mismatches
    "gst_cert_state_mismatch":           "gst_cert_state_mismatch",
    "gst_cert_entity_mismatch":          "gst_number",
    "pan_entity_type_mismatch":          "pan_entity_type_mismatch",
    # ISO expiry
    "iso_cert_expired":                  "iso_cert",
    # DPA not signed
    "dpa_not_signed":                    "dpa",
    # Cancelled cheque without watermark
    "cancelled_cheque_no_watermark":     "cancelled_cheque",
    # Name mismatches — medium/high only; low severity are internal-only (not in this map)
    "account_holder_name_mismatch":      "account_holder_name",
    "pan_name_mismatch":                 "pan_name",
    "gst_legal_name_mismatch":           "gst_legal_name",
    "incorporation_name_mismatch":       "incorporation_company_name",
    "llp_name_mismatch":                 "llp_company_name",
    "iso_name_mismatch":                 "iso_company_name",
    "msme_name_mismatch":                "msme_enterprise_name",
    "partnership_name_mismatch":         "partnership_firm_name",
    # Internal-only (no user_flag, no cross-version escalation):
    # data_offshore, processes_data_no_soc2, processes_data_no_iso,
    # employee_turnover_mismatch, low_cyber_coverage, new_company, service_turnover_mismatch
    # Low-severity name mismatches — not in map (scored but vendor not notified)
}

# doc_type → notified field for unreadable_docs cross-version escalation tracking
DOC_TYPE_TO_NOTIFIED_FIELD: dict[str, str] = {
    "pan_card":         "pan_number",
    "cancelled_cheque": "cancelled_cheque",
    "gst_cert":         "gst_number",
    "incorporation":    "cin_number",
    "llp_agreement":    "llp_number",
    "msme_cert":        "msme_number",
    "iso_cert":         "iso_cert_number",
    "dpa":              "dpa",
    "partnership_deed": "partnership_firm_name",
}


def _base_score(risk_factors: list[dict]) -> int:
    return min(sum(SEVERITY_WEIGHT.get(f.get("severity", "low"), 2) for f in risk_factors), 100)


def _compute_notified_factors(
    risk_factors: list[dict],
    user_flags: list[dict],
    unreadable_docs: list[dict] | None = None,
) -> list[str]:
    """Returns factor names that had a corresponding user notification in this version.
    Notifications come from user_flags (most factors) and unreadable_docs (ocr_failed_* factors).
    """
    notified_fields = {uf["field"] for uf in user_flags}
    if unreadable_docs:
        for ud in unreadable_docs:
            field = DOC_TYPE_TO_NOTIFIED_FIELD.get(ud.get("doc_type", ""))
            if field:
                notified_fields.add(field)
    return [
        f["factor"] for f in risk_factors
        if RISK_FACTOR_TO_FLAG_FIELD.get(f["factor"]) in notified_fields
    ]


def _decision(score: int, user_flags: list[dict]) -> str:
    if score >= 90:
        return "rejected"
    if score >= 76:
        return "high_risk_review"
    if score >= 51:
        return "human_review"
    if score >= 6:
        return "waiting_for_response" if user_flags else "human_review"
    return "approved"


def _cross_version_delta(prior_reviews: list[dict], curr_factors: list[dict]) -> int:
    """
    prior_reviews: list of { "version": int, "risk_factors": [...], "notified_factors": [...] }
                   sorted oldest first.
    Escalation/resolution only on factors that were in prior version's notified_factors.
    Decay: weight = 0.5 ^ (distance - 1). Most recent prior = distance 1 = weight 1.0.
    Repeated notified flag → +5 × weight. Resolved notified flag → -3 × weight.
    """
    curr_keys = {f["factor"] for f in curr_factors}
    delta = 0.0

    for distance, review in enumerate(reversed(prior_reviews), start=1):
        weight = 0.5 ** (distance - 1)
        notified = set(review.get("notified_factors") or [])
        repeated = notified & curr_keys
        resolved = notified - curr_keys
        delta += len(repeated) * 5 * weight
        delta -= len(resolved) * 3 * weight

    return round(delta)


def build_reasoning_input(vendor_id: str, all_reviews: list[dict]) -> dict:
    """
    Builds JSON for reasoning LLM. Never stored in DB.
    all_reviews: list of { "version": int, "risk_factors": [...], "notified_factors": [...], "risk_score": int, "decision": str }
    sorted oldest first.
    """
    return {
        "vendor_id": vendor_id,
        "versions": [
            {
                "version":          r["version"],
                "risk_factors":     r.get("risk_factors") or [],
                "notified_factors": r.get("notified_factors") or [],
                "risk_score":       r.get("risk_score"),
                "decision":         r.get("decision"),
            }
            for r in all_reviews
        ],
    }


REASONING_SYSTEM_PROMPT = """You are a vendor risk analyst writing a brief internal note for a human reviewer.

You receive a vendor's risk assessment across one or more submission versions.
Each version has: risk_factors (what was found), notified_factors (what the vendor was told to fix), risk_score (0-100), decision.

Write 3-5 sentences covering:
1. What the main risks are in the latest version and why they matter
2. If multiple versions exist — whether vendor is improving, escalating, or unchanged
3. Which unresolved notified issues are most concerning (vendor was told but didn't fix)
4. A clear recommendation for the reviewer

Rules:
- Plain English only. No bullet points, no headers, no JSON.
- Be direct and specific — name the actual risk factors.
- Do not repeat the score or decision — reviewer already sees those.
- Focus on what the reviewer needs to decide next."""


def _call_reasoning_llm(reasoning_input: dict) -> str:
    # ── Groq ──────────────────────────────────────────────────────────────────
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": REASONING_SYSTEM_PROMPT},
            {"role": "user",   "content": json.dumps(reasoning_input, default=str)},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()

    # ── Ollama local fallback ─────────────────────────────────────────────────
    # payload = {
    #     "model": OLLAMA_MODEL,
    #     "messages": [
    #         {"role": "system", "content": REASONING_SYSTEM_PROMPT},
    #         {"role": "user",   "content": json.dumps(reasoning_input, default=str)},
    #     ],
    #     "stream": False,
    #     "options": {"temperature": 0.3, "num_ctx": 8192},
    # }
    # resp = httpx.post(OLLAMA_URL, json=payload, timeout=120.0)
    # resp.raise_for_status()
    # return resp.json()["message"]["content"].strip()


def compute_risk_score_and_store(sb, app_id: str, vendor_id: str, risk_factors: list[dict], user_flags: list[dict], unreadable_docs: list[dict] | None = None):
    # Fetch all prior reviews for this vendor (not current app), with version numbers
    prior_rows = (
        sb.table("reviews")
        .select("risk_factors, notified_factors, application_id")
        .eq("vendor_id", vendor_id)
        .neq("application_id", app_id)
        .execute()
        .data
    )

    prior_reviews = []
    for row in prior_rows:
        app = sb.table("applications").select("version").eq("id", row["application_id"]).execute().data
        if app:
            prior_reviews.append({
                "version":           app[0]["version"],
                "risk_factors":      row.get("risk_factors") or [],
                "notified_factors":  row.get("notified_factors") or [],
            })
    prior_reviews.sort(key=lambda x: x["version"])

    notified_factors = _compute_notified_factors(risk_factors, user_flags, unreadable_docs)
    base = _base_score(risk_factors)
    delta = _cross_version_delta(prior_reviews, risk_factors)
    final = max(0, min(100, base + delta))
    decision = _decision(final, user_flags)

    # Build reasoning input with all versions including current
    current_app = sb.table("applications").select("version").eq("id", app_id).execute().data
    current_version = current_app[0]["version"] if current_app else None
    all_reviews_for_reasoning = prior_reviews + [{
        "version":          current_version,
        "risk_factors":     risk_factors,
        "notified_factors": notified_factors,
        "risk_score":       final,
        "decision":         decision,
    }]
    reasoning_input = build_reasoning_input(vendor_id, all_reviews_for_reasoning)

    try:
        risk_reasoning = _call_reasoning_llm(reasoning_input)
    except Exception as e:
        risk_reasoning = f"Reasoning unavailable: {e}"
        logger.warning(f"reasoning_llm failed app_id={app_id}: {e}")

    sb.table("reviews").update({
        "risk_score":       final,
        "decision":         decision,
        "notified_factors": notified_factors,
        "risk_reasoning":   risk_reasoning,
    }).eq("application_id", app_id).execute()

    if decision == "rejected":
        sb.table("applications").update({"status": "rejected"}).eq("id", app_id).execute()
        logger.info(f"auto_rejected: app_id={app_id}")

    logger.info(f"risk_score: app_id={app_id} base={base} delta={delta} final={final} decision={decision} notified={notified_factors}")
    return decision


def run_ai_pipeline(app_id: str, vendor_id: str):
    sb = get_supabase()
    _upsert_review(sb, app_id, vendor_id, "processing")

    try:
        app_row = sb.table("applications").select("*").eq("id", app_id).execute()
        if not app_row.data:
            raise ValueError(f"application {app_id} not found")
        form = app_row.data[0]

        # Fetch latest OCR per doc_type across ALL vendor versions.
        # If vendor re-uploaded a doc in v2, it has a newer uploaded_at → picked.
        # If not re-uploaded, v1's OCR result is used — ensures cross-version doc carry-forward.
        all_docs = (
            sb.table("documents")
            .select("doc_type, ocr_json, ocr_status, uploaded_at")
            .eq("vendor_id", vendor_id)
            .order("uploaded_at", desc=True)
            .execute()
            .data
        )
        seen: dict = {}
        # Pass 1: prefer newest doc with successful OCR per doc_type
        for d in all_docs:
            if d.get("ocr_json") is not None and d["doc_type"] not in seen:
                seen[d["doc_type"]] = d
        # Pass 2: for doc_types with no successful OCR, include newest failed doc
        # so ocr_summary shows "failed" status instead of silently treating as not_applicable
        for d in all_docs:
            dt = d["doc_type"]
            if dt not in seen and d.get("ocr_status") == "failed":
                seen[dt] = d
        docs = list(seen.values())
        ocr_summary = _build_ocr_summary(docs)
        exact_matches = _compute_exact_matches(form, ocr_summary)

        result = _call_llm(form, ocr_summary, exact_matches)
        risk_factors    = result.get("risk_factors", [])
        user_flags      = result.get("user_flags", [])
        unreadable_docs = result.get("unreadable_docs", [])

        _upsert_review(sb, app_id, vendor_id, "done", {
            "user_flags":      user_flags,
            "risk_factors":    risk_factors,
            "unreadable_docs": unreadable_docs,
        })

        decision = compute_risk_score_and_store(sb, app_id, vendor_id, risk_factors, user_flags, unreadable_docs)
        logger.info(f"ai_pipeline: done app_id={app_id}")

        # Email vendor if there are flags to fix (any decision except approved/rejected).
        # Idempotency: claim email_sent_at atomically — skip if another process already sent.
        if user_flags and decision != "rejected":
            now = datetime.now(timezone.utc).isoformat()
            claimed = (
                sb.table("reviews")
                .update({"email_sent_at": now})
                .eq("application_id", app_id)
                .is_("email_sent_at", "null")
                .execute()
            )
            if claimed.data:
                try:
                    send_vendor_flags_email(
                        contact_email=form.get("contact_email", ""),
                        company_name=form.get("company_name", "Vendor"),
                        version=form.get("version", 1),
                        user_flags=user_flags,
                        unreadable_docs=unreadable_docs,
                    )
                except Exception as e:
                    logger.error(f"email_send_failed app_id={app_id} err={e}")
            else:
                logger.info(f"email_skip already_claimed app_id={app_id}")

    except Exception as e:
        logger.error(f"ai_pipeline: failed app_id={app_id} err={e}")
        _upsert_review(sb, app_id, vendor_id, "failed", {
            "user_flags": [],
            "risk_factors": [{"factor": "ai_check_failed", "severity": "low", "note": str(e)}],
            "unreadable_docs": [],
        })
