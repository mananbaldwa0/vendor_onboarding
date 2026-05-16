import re
import pytesseract
from PIL import Image
import io

RE_PAN     = re.compile(r'[A-Z]{5}[0-9]{4}[A-Z]')
RE_IFSC    = re.compile(r'[A-Z]{4}[0O][A-Z0-9]{6}')
RE_IFSC_LABEL = re.compile(r'IFSC[:\s]+([A-Z]{4}[0O][A-Z0-9]{6})', re.IGNORECASE)
RE_ACCOUNT = re.compile(r'\b[0-9]{9,18}\b')


def _extract_text(file_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(file_bytes)).convert("L")
    return pytesseract.image_to_string(img)


def _first_match(pattern: re.Pattern, text: str) -> str | None:
    m = pattern.search(text)
    return m.group(0) if m else None


def _label_value(text: str, label_pattern: str) -> str | None:
    """Extract value from 'Label: Value' on same line. Returns first line only."""
    m = re.search(r'(?:' + label_pattern + r')[:\s]+([^\n]+)', text, re.IGNORECASE)
    val = m.group(1) if m else None
    return val.strip() if val else None


def _normalize_ifsc(raw: str) -> str:
    if len(raw) == 11 and raw[4] == 'O':
        return raw[:4] + '0' + raw[5:]
    return raw


# ── Per-doc-type extractors ────────────────────────────────────────────────────

def extract_pan_card(file_bytes: bytes) -> dict:
    text = _extract_text(file_bytes)
    pan_number = _first_match(RE_PAN, text)
    # Use explicit "Name:" label, take first line only
    name_on_card = _label_value(text, r'name')
    return {
        "pan_number":   pan_number,
        "name_on_card": name_on_card,
        "raw_text":     text,
    }


def extract_cancelled_cheque(file_bytes: bytes) -> dict:
    text = _extract_text(file_bytes)

    # IFSC: label-based first, then bare pattern
    label_m = RE_IFSC_LABEL.search(text)
    raw_ifsc = label_m.group(1) if label_m else _first_match(RE_IFSC, text)
    ifsc_code = _normalize_ifsc(raw_ifsc) if raw_ifsc else None

    # Account number: label "A/C No:" or "Account No:" → same-line value
    account_number = _label_value(text, r'a/?c\s*no|account\s*no|account\s*number')
    if not account_number:
        # fallback: longest bare numeric sequence
        all_nums = RE_ACCOUNT.findall(text)
        account_number = max(all_nums, key=len) if all_nums else None

    # Account holder name: label-based first, then line before IFSC
    account_holder_name = _label_value(text, r'account\s*holder')
    if not account_holder_name:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for i, line in enumerate(lines):
            if ifsc_code and ifsc_code in line:
                if i > 0:
                    account_holder_name = lines[i - 1]
                break
            if label_m and 'IFSC' in line.upper():
                if i > 0:
                    account_holder_name = lines[i - 1]
                break

    # Skip if name looks like bank boilerplate
    if account_holder_name and re.search(r'cancel(led)?|bank\s+of|CANCELLED', account_holder_name, re.IGNORECASE):
        account_holder_name = None

    cancelled_watermark = bool(re.search(r'cancel(led)?', text, re.IGNORECASE))
    return {
        "ifsc_code":            ifsc_code,
        "account_number":       account_number,
        "account_holder_name":  account_holder_name,
        "cancelled_watermark":  cancelled_watermark,
        "raw_text":             text,
    }


EXTRACTORS = {
    "pan_card":         extract_pan_card,
    "cancelled_cheque": extract_cancelled_cheque,
}


def extract_image(doc_type: str, file_bytes: bytes) -> dict:
    fn = EXTRACTORS.get(doc_type)
    if fn is None:
        return {"error": f"No image extractor for doc_type: {doc_type}"}
    return fn(file_bytes)
