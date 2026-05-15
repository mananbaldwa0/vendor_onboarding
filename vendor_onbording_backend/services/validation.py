import re
from datetime import date, datetime

# ── Allowed values ────────────────────────────────────────────────────────────

COMPANY_TYPES = {
    "Private Limited", "Public Limited", "LLP",
    "Partnership Firm", "Sole Proprietorship"
}

TURNOVER_OPTIONS = {"<1 Cr", "1-10 Cr", "10-100 Cr", ">100 Cr"}

ACCOUNT_TYPES = {"Current", "Savings"}

SERVICE_TYPES = {
    "Core Banking Software", "Cybersecurity Tool", "Cloud Infrastructure",
    "SaaS Platform", "Data Analytics", "HR/ERP Software",
    "Network/Hardware", "Other"
}

CLOUD_PROVIDERS = {
    "AWS", "Azure", "GCP", "Private Cloud",
    "On-Premise", "Hybrid", "Not Applicable"
}

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "rediffmail.com", "yahoo.in", "ymail.com"
}

# PAN 4th char → company types it applies to
PAN_ENTITY = {
    "C": {"Private Limited", "Public Limited"},
    "F": {"LLP", "Partnership Firm"},
    "P": {"Sole Proprietorship"},
}

# Indian state → GST 2-digit state code
STATE_GST_CODES = {
    "Jammu & Kashmir": "01", "Himachal Pradesh": "02", "Punjab": "03",
    "Chandigarh": "04", "Uttarakhand": "05", "Haryana": "06",
    "Delhi": "07", "Rajasthan": "08", "Uttar Pradesh": "09",
    "Bihar": "10", "Sikkim": "11", "Arunachal Pradesh": "12",
    "Nagaland": "13", "Manipur": "14", "Mizoram": "15",
    "Tripura": "16", "Meghalaya": "17", "Assam": "18",
    "West Bengal": "19", "Jharkhand": "20", "Odisha": "21",
    "Chhattisgarh": "22", "Madhya Pradesh": "23", "Gujarat": "24",
    "Daman & Diu": "25", "Dadra & Nagar Haveli": "26", "Maharashtra": "27",
    "Andhra Pradesh": "37", "Karnataka": "29", "Goa": "30",
    "Lakshadweep": "31", "Kerala": "32", "Tamil Nadu": "33",
    "Puducherry": "34", "Andaman & Nicobar": "35", "Telangana": "36",
    "Ladakh": "38",
}


# ── Regex patterns ────────────────────────────────────────────────────────────

RE_PAN       = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$')
RE_GST       = re.compile(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$')
RE_CIN       = re.compile(r'^[UL][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$')
RE_LLP       = re.compile(r'^[A-Z]{3}-[0-9]{4}$')
RE_DIN       = re.compile(r'^[0-9]{8}$')
RE_ACCOUNT   = re.compile(r'^[0-9]{9,18}$')
RE_IFSC      = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')
RE_PHONE     = re.compile(r'^\+[0-9]{1,3}[0-9]{7,12}$')
RE_MSME      = re.compile(r'^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$')
RE_URL       = re.compile(r'^https?://[^\s]+\.[^\s]+$')


# ── Required documents per submission ────────────────────────────────────────

def required_doc_types(data: dict) -> list[str]:
    docs = ["pan_card", "cancelled_cheque"]
    if data.get("gst_registered"):
        docs.append("gst_cert")
    ctype = data.get("company_type", "")
    if ctype in ("Private Limited", "Public Limited"):
        docs.append("incorporation")
    if ctype == "LLP":
        docs.append("llp_agreement")
    if ctype == "Partnership Firm":
        docs.append("partnership_deed")
    if data.get("iso_certified"):
        docs.append("iso_cert")
    if data.get("processes_data"):
        docs.append("dpa")
    if data.get("msme_number"):
        docs.append("msme_cert")
    return docs


# ── Main validator ────────────────────────────────────────────────────────────

def validate_application(data: dict, uploaded_doc_types: list[str]) -> list[str]:
    """
    Returns list of error strings.
    Empty list = valid submission.
    """
    errors = []
    ctype = data.get("company_type", "")
    today = date.today()

    # ── Group 1: Company Identity ──────────────────────────────────────────

    if not data.get("company_name") or len(data["company_name"].strip()) < 3:
        errors.append("Company name is required (min 3 characters)")

    if not data.get("company_type") or data["company_type"] not in COMPANY_TYPES:
        errors.append(f"Company type must be one of: {', '.join(sorted(COMPANY_TYPES))}")

    if not data.get("incorporation_date"):
        errors.append("Incorporation date is required")
    else:
        inc_date = data["incorporation_date"]
        if isinstance(inc_date, str):
            inc_date = date.fromisoformat(inc_date)
        if inc_date >= today:
            errors.append("Incorporation date must be in the past")
        if inc_date.year < 1900:
            errors.append("Incorporation date cannot be before 1900")

    if not data.get("registered_address") or len(data["registered_address"].strip()) < 10:
        errors.append("Registered address is required (min 10 characters)")

    if not data.get("city") or len(data["city"].strip()) < 2:
        errors.append("City is required")

    if not data.get("state") or data["state"] not in STATE_GST_CODES:
        errors.append("Select a valid Indian state")

    if data.get("employee_count") is None or data["employee_count"] < 1:
        errors.append("Employee count must be at least 1")

    if not data.get("annual_turnover") or data["annual_turnover"] not in TURNOVER_OPTIONS:
        errors.append(f"Annual turnover must be one of: {', '.join(sorted(TURNOVER_OPTIONS))}")

    if data.get("website") and not RE_URL.match(data["website"]):
        errors.append("Website must be a valid URL (e.g. https://company.com)")

    # ── Group 2: PAN ──────────────────────────────────────────────────────

    pan = data.get("pan_number", "")
    if not pan:
        errors.append("PAN number is required")
    elif not RE_PAN.match(pan):
        errors.append("Invalid PAN format — must be AAAAA0000A (e.g. ABCDE1234F)")
    elif ctype:
        fourth_char = pan[3]
        valid_types = PAN_ENTITY.get(fourth_char, set())
        if valid_types and ctype not in valid_types:
            errors.append(f"PAN 4th character '{fourth_char}' does not match company type '{ctype}'")

    # ── Group 3: GST ──────────────────────────────────────────────────────

    if data.get("gst_registered") is None:
        errors.append("Specify if GST registered (Yes/No)")

    if data.get("gst_registered"):
        gst = data.get("gst_number", "")
        if not gst:
            errors.append("GST number is required when GST registered")
        elif not RE_GST.match(gst):
            errors.append("Invalid GST number format (e.g. 27ABCDE1234F1Z5)")
        else:
            # state code check
            state_code = STATE_GST_CODES.get(data.get("state", ""))
            if state_code and gst[:2] != state_code:
                errors.append(f"GST state code '{gst[:2]}' does not match state '{data.get('state')}' (expected '{state_code}')")
            # PAN embed check
            if pan and RE_PAN.match(pan) and gst[2:12] != pan:
                errors.append(f"PAN embedded in GST (chars 3-12) does not match PAN field")

    # ── Group 4: Director / Company IDs ───────────────────────────────────

    if not data.get("signatory_name") or len(data["signatory_name"].strip()) < 3:
        errors.append("Authorized signatory name is required")

    if ctype in ("Private Limited", "Public Limited"):
        din = data.get("din", "")
        if not din:
            errors.append("DIN is required for Private/Public Limited companies")
        elif not RE_DIN.match(din):
            errors.append("DIN must be exactly 8 digits")

        cin = data.get("cin_number", "")
        if not cin:
            errors.append("CIN is required for Private/Public Limited companies")
        elif not RE_CIN.match(cin):
            errors.append("Invalid CIN format (e.g. U72900MH2015PTC123456)")
        else:
            # CIN year must match incorporation year
            if data.get("incorporation_date"):
                inc_date = data["incorporation_date"]
                if isinstance(inc_date, str):
                    inc_date = date.fromisoformat(inc_date)
                cin_year = cin[8:12]
                if cin_year != str(inc_date.year):
                    errors.append(f"CIN year '{cin_year}' does not match incorporation year '{inc_date.year}'")

    if ctype == "LLP":
        if not data.get("dpin"):
            errors.append("DPIN is required for LLP")
        elif not RE_DIN.match(data["dpin"]):
            errors.append("DPIN must be exactly 8 digits")

        if not data.get("llp_number"):
            errors.append("LLP Identification Number is required for LLP")
        elif not RE_LLP.match(data["llp_number"]):
            errors.append("Invalid LLP number format (e.g. AAA-1234)")

    if data.get("msme_number"):
        if not RE_MSME.match(data["msme_number"]):
            errors.append("Invalid MSME number format (e.g. UDYAM-MH-00-0000000)")

    # ── Group 5: Banking ──────────────────────────────────────────────────

    if not data.get("account_holder_name") or len(data["account_holder_name"].strip()) < 3:
        errors.append("Account holder name is required")

    if not data.get("bank_name") or len(data["bank_name"].strip()) < 3:
        errors.append("Bank name is required")

    if not data.get("account_number"):
        errors.append("Account number is required")
    elif not RE_ACCOUNT.match(str(data["account_number"])):
        errors.append("Account number must be 9–18 digits, numeric only")

    if not data.get("ifsc_code"):
        errors.append("IFSC code is required")
    elif not RE_IFSC.match(data["ifsc_code"]):
        errors.append("Invalid IFSC format — must be AAAA0XXXXXX (5th character always 0)")

    if not data.get("account_type") or data["account_type"] not in ACCOUNT_TYPES:
        errors.append("Account type must be Current or Savings")

    # ── Group 6: ISO ──────────────────────────────────────────────────────

    if data.get("iso_certified") is None:
        errors.append("Specify ISO 27001 certification status")

    if data.get("iso_certified"):
        if not data.get("iso_cert_number") or len(data["iso_cert_number"].strip()) < 3:
            errors.append("ISO certificate number is required")

        if not data.get("iso_expiry_date"):
            errors.append("ISO certificate expiry date is required")
        else:
            expiry = data["iso_expiry_date"]
            if isinstance(expiry, str):
                expiry = date.fromisoformat(expiry)
            if expiry <= today:
                errors.append("ISO certificate is expired — expiry date must be in the future")

    # ── Group 7: Data & Compliance ────────────────────────────────────────

    if not data.get("service_nature") or data["service_nature"] not in SERVICE_TYPES:
        errors.append(f"Nature of IT service must be one of: {', '.join(sorted(SERVICE_TYPES))}")

    if data.get("processes_data") is None:
        errors.append("Specify if service processes bank/customer data")

    if data.get("data_in_india") is None:
        errors.append("Specify if data is stored within India")

    if not data.get("cloud_provider") or data["cloud_provider"] not in CLOUD_PROVIDERS:
        errors.append(f"Cloud provider must be one of: {', '.join(sorted(CLOUD_PROVIDERS))}")

    if data.get("processes_data") and not data.get("cyber_insurance"):
        errors.append("Cyber insurance is mandatory when service processes bank/customer data")

    if data.get("cyber_insurance"):
        if data.get("cyber_coverage_crores") is None or float(data["cyber_coverage_crores"]) <= 0:
            errors.append("Cyber insurance coverage amount is required and must be greater than 0")

    # ── Group 8: Contact ──────────────────────────────────────────────────

    if not data.get("contact_name") or len(data["contact_name"].strip()) < 3:
        errors.append("Contact name is required")

    email = data.get("contact_email", "")
    if not email:
        errors.append("Contact email is required")
    elif "@" not in email:
        errors.append("Invalid email format")
    else:
        domain = email.split("@")[-1].lower()
        if domain in FREE_EMAIL_DOMAINS:
            errors.append(f"Free email domain '{domain}' not allowed — use official company email")

    if not data.get("contact_phone"):
        errors.append("Contact phone number is required")
    elif not RE_PHONE.match(data["contact_phone"]):
        errors.append("Phone must include country code (e.g. +919876543210)")

    # ── Documents ─────────────────────────────────────────────────────────

    required = required_doc_types(data)
    uploaded = set(uploaded_doc_types)
    missing = [d for d in required if d not in uploaded]
    if missing:
        doc_labels = {
            "pan_card": "PAN Card",
            "cancelled_cheque": "Cancelled Cheque",
            "gst_cert": "GST Certificate",
            "incorporation": "Certificate of Incorporation",
            "llp_agreement": "LLP Agreement",
            "partnership_deed": "Partnership Deed",
            "iso_cert": "ISO 27001 Certificate",
            "dpa": "Data Processing Agreement (DPA)",
            "msme_cert": "MSME Certificate",
        }
        for d in missing:
            errors.append(f"Missing required document: {doc_labels.get(d, d)}")

    return errors
