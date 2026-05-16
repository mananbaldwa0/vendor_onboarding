import re
import pdfplumber
import io

RE_PAN    = re.compile(r'[A-Z]{5}[0-9]{4}[A-Z]')
RE_GST    = re.compile(r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]')
RE_CIN    = re.compile(r'[UL][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}')
RE_LLP    = re.compile(r'[A-Z]{3}-[0-9]{4}')
RE_MSME   = re.compile(r'UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}')
RE_DATE   = re.compile(r'\d{4}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]\d{4}')


def _extract_text(file_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _first_match(pattern: re.Pattern, text: str) -> str | None:
    m = pattern.search(text)
    return m.group(0) if m else None


def _label_value(text: str, label_pattern: str) -> str | None:
    """Extract value from 'Label: Value' on same line."""
    m = re.search(r'(?:' + label_pattern + r')[:\s]+([^\n]+)', text, re.IGNORECASE)
    val = m.group(1) if m else None
    return val.strip() if val else None


def _all_dates(text: str) -> list[str]:
    return RE_DATE.findall(text)


# ── Per-doc-type extractors ────────────────────────────────────────────────────

def extract_gst_cert(file_bytes: bytes) -> dict:
    text = _extract_text(file_bytes)
    return {
        "gstin":             _first_match(RE_GST, text),
        "legal_name":        _label_value(text, r'legal\s*name\s*of\s*business'),
        "registration_date": _all_dates(text)[0] if _all_dates(text) else None,
        "raw_text":          text,
    }


def extract_incorporation(file_bytes: bytes) -> dict:
    text = _extract_text(file_bytes)
    dates = _all_dates(text)
    return {
        "cin_number":        _first_match(RE_CIN, text),
        "company_name":      _label_value(text, r'company\s*name'),
        "incorporation_date": dates[0] if dates else None,
        "raw_text":          text,
    }


def extract_llp_agreement(file_bytes: bytes) -> dict:
    text = _extract_text(file_bytes)
    return {
        "llp_number":    _first_match(RE_LLP, text),
        "company_name":  _label_value(text, r'name\s*of\s*llp'),
        "raw_text":      text,
    }


def extract_partnership_deed(file_bytes: bytes) -> dict:
    text = _extract_text(file_bytes)
    return {
        "firm_name":   _label_value(text, r'firm\s*name'),
        "raw_text":    text,
    }


def extract_iso_cert(file_bytes: bytes) -> dict:
    text = _extract_text(file_bytes)
    dates = _all_dates(text)
    return {
        "cert_number":   _label_value(text, r'certificate\s*number'),
        "company_name":  _label_value(text, r'awarded\s*to|issued\s*to|certified\s*to'),
        "expiry_date":   _label_value(text, r'expiry\s*date') or (dates[-1] if dates else None),
        "standard_text": "ISO/IEC 27001" if "27001" in text else None,
        "raw_text":      text,
    }


def extract_dpa(file_bytes: bytes) -> dict:
    text = _extract_text(file_bytes)
    dates = _all_dates(text)
    is_signed = bool(re.search(r'signature|signed\s*by|authorised\s*signatory', text, re.IGNORECASE))
    return {
        "company_name": _label_value(text, r'data\s*processor|between|party'),
        "is_signed":    is_signed,
        "signing_date": _label_value(text, r'date') or (dates[0] if dates else None),
        "raw_text":     text,
    }


def extract_msme_cert(file_bytes: bytes) -> dict:
    text = _extract_text(file_bytes)
    # category: Micro/Small/Medium but NOT inside "Ministry of Micro..."
    category = None
    for line in text.splitlines():
        if re.search(r'\b(Micro|Small|Medium)\b', line, re.IGNORECASE):
            if not re.search(r'ministry|government', line, re.IGNORECASE):
                m = re.search(r'\b(Micro|Small|Medium)\b', line, re.IGNORECASE)
                if m:
                    category = m.group(0).capitalize()
                    break
    return {
        "udyam_number":    _first_match(RE_MSME, text),
        "enterprise_name": _label_value(text, r'name\s*of\s*enterprise|enterprise\s*name'),
        "category":        category,
        "raw_text":        text,
    }


EXTRACTORS = {
    "gst_cert":         extract_gst_cert,
    "incorporation":    extract_incorporation,
    "llp_agreement":    extract_llp_agreement,
    "partnership_deed": extract_partnership_deed,
    "iso_cert":         extract_iso_cert,
    "dpa":              extract_dpa,
    "msme_cert":        extract_msme_cert,
}


def extract_pdf(doc_type: str, file_bytes: bytes) -> dict:
    fn = EXTRACTORS.get(doc_type)
    if fn is None:
        return {"error": f"No PDF extractor for doc_type: {doc_type}"}
    return fn(file_bytes)
