#!/usr/bin/env python3
"""
Generates 3 multi-version escalation test cases for end-to-end testing.

Run from vendor_onboarding_data_generator/:
  python generate_escalation_cases.py

Output structure:
  output/
    escalation_case_01_error_then_approved/
      v1/  payload.json + meta.json + docs/  ← wrong PAN card, personal cheque
      v2/  payload.json + meta.json + docs/  ← fixed docs → approved

    escalation_case_02_human_high_approved/
      v1/  payload.json + meta.json + docs/  ← bad compliance + partial OCR + personal cheque → human_review
      v2/  payload.json + meta.json + docs/  ← same, no fix → high_risk_review (escalation)
      v3/  payload.json + meta.json + docs/  ← fixes everything → approved

    escalation_case_03_scammer_rejected/
      v1/  payload.json + meta.json + docs/  ← bad compliance + partial OCR + personal cheque → human_review
      v2/  payload.json + meta.json + docs/  ← same, no fix → high_risk_review
      v3/  payload.json + meta.json + docs/  ← same again → rejected (score ≥ 90 via escalation)

Manual testing flow (per case):
  1. Start backend + frontend
  2. For V1: login with case email, upload V1 docs, submit V1 payload
  3. Wait ~30s for OCR + AI pipeline
  4. Check admin dashboard — verify decision matches meta.json expected_decision
  5. For V2+: same login, upload V2 docs (they REPLACE V1 docs via the upsert), submit V2 payload
  6. Repeat for V3

Score math (from ai_service.py):
  Severity weights: high=10, medium=5, low=2
  Cross-version delta: repeated notified factor = +5×weight, resolved = -3×weight
  Weight = 0.5^(distance-1): most recent prior = 1.0, one before = 0.5, etc.
  Decision thresholds: <6=approved, 6-50=waiting_for_response, 51-75=human_review,
                       76-89=high_risk_review, ≥90=rejected
"""
import json
import os
import sys
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from generators.documents import (
    _make_jpg, _make_pdf, _ensure_dir,
    generate_gst_cert, generate_incorporation_cert,
    generate_iso_cert, generate_dpa,
)

OUT = ROOT / "output"


# ── Helpers ───────────────────────────────────────────────────────────────────

def save_version(version_dir: Path, form_data: dict, meta: dict):
    version_dir.mkdir(parents=True, exist_ok=True)
    with open(version_dir / "payload.json", "w") as f:
        json.dump(form_data, f, indent=2, default=str)
    with open(version_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)
    print(f"  {version_dir.parent.name}/{version_dir.name}: {meta['expected_decision']}")


def gen_pan_card(vendor_dir: str, pan_number: str, company_name: str) -> str:
    path = os.path.join(vendor_dir, "pan_card.jpg")
    _make_jpg(path, [
        "INCOME TAX DEPARTMENT",
        "PERMANENT ACCOUNT NUMBER CARD",
        f"PAN: {pan_number}",
        f"Name: {company_name}",
        "Government of India",
    ])
    return path


def gen_pan_card_partial(vendor_dir: str, company_name: str) -> str:
    """PAN card with no PAN number line — forces partial_read in OCR."""
    path = os.path.join(vendor_dir, "pan_card.jpg")
    _make_jpg(path, [
        "INCOME TAX DEPARTMENT",
        "PERMANENT ACCOUNT NUMBER CARD",
        f"Name: {company_name}",
        "Government of India",
        "Please refer to original card for number",
    ])
    return path


def gen_gst_cert_partial(vendor_dir: str, company_name: str, registration_date: str) -> str:
    """GST cert with no GSTIN line — forces partial_read in OCR."""
    path = os.path.join(vendor_dir, "gst_cert.pdf")
    _make_pdf(path, [
        "GOODS AND SERVICES TAX REGISTRATION CERTIFICATE",
        f"Legal Name of Business: {company_name}",
        f"Date of Registration: {registration_date}",
        "Registration Type: Regular",
        "Issued by: GST Council of India",
        "Note: GSTIN redacted in this copy — contact GST office for full details",
    ])
    return path


def gen_cancelled_cheque(vendor_dir: str, ifsc: str, account_number: str,
                         bank_name: str, account_holder: str) -> str:
    path = os.path.join(vendor_dir, "cancelled_cheque.jpg")
    _make_jpg(path, [
        "CANCELLED",
        bank_name,
        f"Account Holder: {account_holder}",
        f"IFSC: {ifsc}",
        f"A/C No: {account_number}",
        "Pay _______________",
    ])
    return path


# ── Case 1 — Error in V1, Fixed in V2, Approved ──────────────────────────────
# "Crescendo Tech Private Limited" — Maharashtra
#
# V1: Form correct. PAN card has wrong PAN (last char flipped).
#     Cancelled cheque has personal name "Rahul Narayan Patel".
#     → AI: pan_number mismatch (user_flag) + account_holder_name_mismatch (user_flag + risk_factor high=10)
#     → base_score = 10 (account_holder_name_mismatch only; pan mismatch alone has no risk_factor)
#     → decision = waiting_for_response (score 6-50 with user_flags)
#     → email fires to vendor listing both flags
#
# V2: Same form. Fixed docs: correct PAN card, company name on cheque.
#     → AI: no flags, no risk_factors
#     → base_score = 0, delta = -3 (account_holder_name_mismatch resolved, weight=1.0)
#     → final = max(0, 0-3) = 0 → decision = approved

def case_01():
    case_dir = OUT / "escalation_case_01_error_then_approved"
    print(f"\n[Case 1] Error V1 → Approved V2")

    # Fixed form data — all values correct
    pan = "AABCC1429B"         # C = Private Limited ✓
    gst = "27AABCC1429B1Z5"    # 27=Maharashtra, pan embedded ✓
    cin = "U72200MH2019PTC312345"

    form = {
        "company_name": "Crescendo Tech Private Limited",
        "company_type": "Private Limited",
        "incorporation_date": "2019-06-15",
        "registered_address": "Plot 14, MIDC Andheri East",
        "city": "Mumbai",
        "state": "Maharashtra",
        "employee_count": 85,
        "annual_turnover": "10-100 Cr",
        "website": "https://crescendotech.in",
        "signatory_name": "Anita Ramesh Kulkarni",
        "pan_number": pan,
        "gst_registered": True,
        "gst_number": gst,
        "din": "07654321",
        "cin_number": cin,
        "account_holder_name": "Crescendo Tech Pvt Ltd",
        "bank_name": "HDFC Bank",
        "account_number": "50100123456789",
        "ifsc_code": "HDFC0001234",
        "account_type": "Current",
        "iso_certified": False,
        "soc2_audited": False,
        "service_nature": "SaaS Platform",
        "processes_data": False,
        "data_in_india": True,
        "cloud_provider": "AWS",
        "cyber_insurance": False,
        "contact_name": "Anita Kulkarni",
        "contact_email": "anita@crescendotech.in",
        "contact_phone": "+919876501234",
    }

    # ── V1 ────────────────────────────────────────────────────────────────────
    v1_dir = case_dir / "v1"
    docs_dir = str(v1_dir / "docs" / "crescendo_v1")
    _ensure_dir(docs_dir)

    wrong_pan = pan[:9] + ("Z" if pan[9] != "Z" else "A")   # flip last char

    gen_pan_card(docs_dir, wrong_pan, "Crescendo Tech Private Limited")
    gen_cancelled_cheque(docs_dir, form["ifsc_code"], form["account_number"],
                         form["bank_name"], "Rahul Narayan Patel")   # personal name
    generate_gst_cert(docs_dir, gst, "Crescendo Tech Private Limited",
                      form["incorporation_date"])
    generate_incorporation_cert(docs_dir, cin, "Crescendo Tech Private Limited",
                                form["incorporation_date"])

    save_version(v1_dir, form, {
        "case": "escalation_case_01",
        "version": 1,
        "login_email": "vendor.crescendo@crescendotech.in",
        "description": (
            "Form has correct PAN and account holder. "
            f"PAN card doc shows wrong PAN '{wrong_pan}' (form says '{pan}'). "
            "Cancelled cheque shows 'Rahul Narayan Patel' — personal name."
        ),
        "docs_to_upload": [
            {"file": f"docs/crescendo_v1/pan_card.jpg", "doc_type": "pan_card"},
            {"file": f"docs/crescendo_v1/cancelled_cheque.jpg", "doc_type": "cancelled_cheque"},
            {"file": f"docs/crescendo_v1/gst_cert.pdf", "doc_type": "gst_cert"},
            {"file": f"docs/crescendo_v1/incorporation.pdf", "doc_type": "incorporation"},
        ],
        "expected_layer1": "submitted",
        "expected_risk_factors": ["account_holder_name_mismatch (high=10)"],
        "expected_user_flags": [
            "pan_number — mismatch (high)",
            "account_holder_name — personal name on cheque (high)",
        ],
        "expected_base_score": 10,
        "expected_delta": 0,
        "expected_final_score": 10,
        "expected_decision": "waiting_for_response",
        "expected_email": "fires — both flags sent to vendor",
        "notified_factors_for_next_version": ["account_holder_name_mismatch"],
    })

    # ── V2 ────────────────────────────────────────────────────────────────────
    v2_dir = case_dir / "v2"
    docs_dir = str(v2_dir / "docs" / "crescendo_v2")
    _ensure_dir(docs_dir)

    gen_pan_card(docs_dir, pan, "Crescendo Tech Private Limited")           # correct PAN ✓
    gen_cancelled_cheque(docs_dir, form["ifsc_code"], form["account_number"],
                         form["bank_name"], "Crescendo Tech Pvt Ltd")       # company name ✓
    generate_gst_cert(docs_dir, gst, "Crescendo Tech Private Limited",
                      form["incorporation_date"])
    generate_incorporation_cert(docs_dir, cin, "Crescendo Tech Private Limited",
                                form["incorporation_date"])

    save_version(v2_dir, form, {
        "case": "escalation_case_01",
        "version": 2,
        "login_email": "vendor.crescendo@crescendotech.in",
        "description": "Vendor fixed both docs. Correct PAN card. Company name on cheque.",
        "docs_to_upload": [
            {"file": "docs/crescendo_v2/pan_card.jpg", "doc_type": "pan_card"},
            {"file": "docs/crescendo_v2/cancelled_cheque.jpg", "doc_type": "cancelled_cheque"},
            {"file": "docs/crescendo_v2/gst_cert.pdf", "doc_type": "gst_cert"},
            {"file": "docs/crescendo_v2/incorporation.pdf", "doc_type": "incorporation"},
        ],
        "expected_layer1": "submitted",
        "expected_risk_factors": [],
        "expected_user_flags": [],
        "expected_base_score": 0,
        "expected_delta": -3,
        "expected_final_score": 0,
        "expected_decision": "approved",
        "expected_email": "no email — no flags",
        "note": "account_holder_name_mismatch was notified in V1, now resolved → -3 delta. Final max(0,-3)=0.",
    })


# ── Case 2 — Human Review → High Risk → Accepted ─────────────────────────────
# "Nexaflow Systems Private Limited" — Karnataka
#
# V1 risk_factors (all fire):
#   data_offshore          high  10  (not notified — no user_flag field)
#   iso_cert_expired       high  10  notified ✓ (user_flag iso_cert)
#   employee_turnover      high  10  (not notified)
#   processes_data_no_soc2 med    5  (not notified)
#   low_cyber_coverage     med    5  (not notified)
#   new_company            low    2  (not notified)
#   partial_ocr_pan_card   med    5  notified ✓ (user_flag pan_number)
#   partial_ocr_gst_cert   med    5  notified ✓ (user_flag gst_number)
#   account_holder_mismatch high  10  notified ✓ (user_flag account_holder_name)
#   base_score = 62  →  human_review (51-75) ✓
#   notified = [iso_cert_expired, partial_ocr_pan_card, partial_ocr_gst_cert, account_holder_name_mismatch]
#
# V2: same, no fix
#   base = 62, delta = 4 notified_repeated × 5 × 1.0 = +20, final = 82 → high_risk_review ✓
#
# V3: vendor fixes everything
#   data_in_india=true, soc2=true, iso renewed, cyber=15Cr, employee=25, service=SaaS
#   fixed docs: correct PAN, correct GST, company cheque
#   base = 2 (only new_company left)
#   delta = 4 resolved from V2 × -3 × 1.0 = -12
#          + 4 resolved from V1 × -3 × 0.5 = -6
#   final = max(0, 2-18) = 0 → approved ✓

def case_02():
    case_dir = OUT / "escalation_case_02_human_high_approved"
    print(f"\n[Case 2] Human Review V1 → High Risk V2 → Approved V3")

    pan = "AABCN2211K"                  # C = Private Limited ✓
    gst = "29AABCN2211K1Z3"             # 29=Karnataka ✓
    cin = "U62010KA2023PTC098765"
    iso_cert_number = "IS 847291"
    expired_iso = (date.today() - timedelta(days=400)).isoformat()  # ~13 months ago

    # V1 and V2 form — bad compliance posture
    form_v1 = {
        "company_name": "Nexaflow Systems Private Limited",
        "company_type": "Private Limited",
        "incorporation_date": (date.today() - timedelta(days=540)).isoformat(),  # ~1.5 years ago
        "registered_address": "47, Koramangala 4th Block",
        "city": "Bengaluru",
        "state": "Karnataka",
        "employee_count": 400,          # implausible for <1 Cr
        "annual_turnover": "<1 Cr",
        "website": "https://nexaflow.io",
        "signatory_name": "Deepak Krishnaswamy",
        "pan_number": pan,
        "gst_registered": True,
        "gst_number": gst,
        "din": "09812345",
        "cin_number": cin,
        "account_holder_name": "Nexaflow Systems Pvt Ltd",
        "bank_name": "ICICI Bank",
        "account_number": "002901234567",
        "ifsc_code": "ICIC0000029",
        "account_type": "Current",
        "iso_certified": True,
        "iso_cert_number": iso_cert_number,
        "iso_expiry_date": expired_iso,  # expired ← iso_cert_expired fires
        "soc2_audited": False,           # ← processes_data_no_soc2 fires
        "service_nature": "Core Banking Software",
        "processes_data": True,
        "data_in_india": False,          # ← data_offshore fires
        "cloud_provider": "AWS",
        "cyber_insurance": True,
        "cyber_coverage_crores": 1.0,    # ← low_cyber_coverage fires
        "contact_name": "Deepak K",
        "contact_email": "deepak@nexaflow.io",
        "contact_phone": "+918765432109",
    }

    # V3 form — vendor fixes compliance
    form_v3 = deepcopy(form_v1)
    form_v3["data_in_india"] = True
    form_v3["soc2_audited"] = True
    form_v3["iso_expiry_date"] = (date.today() + timedelta(days=900)).isoformat()  # renewed
    form_v3["cyber_coverage_crores"] = 15.0
    form_v3["employee_count"] = 25           # plausible for <1Cr
    form_v3["service_nature"] = "SaaS Platform"   # plausible for <1Cr

    # ── V1 ────────────────────────────────────────────────────────────────────
    v1_dir = case_dir / "v1"
    docs_dir = str(v1_dir / "docs" / "nexaflow_v1")
    _ensure_dir(docs_dir)

    gen_pan_card_partial(docs_dir, "Nexaflow Systems Private Limited")      # no PAN line → partial_read
    gen_gst_cert_partial(docs_dir, "Nexaflow Systems Private Limited",
                         form_v1["incorporation_date"])                      # no GSTIN line → partial_read
    gen_cancelled_cheque(docs_dir, form_v1["ifsc_code"], form_v1["account_number"],
                         form_v1["bank_name"], "Vikram Malhotra Singh")     # personal name
    generate_incorporation_cert(docs_dir, cin, "Nexaflow Systems Private Limited",
                                form_v1["incorporation_date"])
    generate_iso_cert(docs_dir, iso_cert_number, "Nexaflow Systems Private Limited",
                      expired_iso)                                           # expired ISO
    generate_dpa(docs_dir, "Nexaflow Systems Private Limited", "Deepak Krishnaswamy")

    save_version(v1_dir, form_v1, {
        "case": "escalation_case_02",
        "version": 1,
        "login_email": "vendor.nexaflow@nexaflow.io",
        "description": (
            "Bad compliance: data offshore, ISO expired 13 months ago, no SOC2, "
            "low cyber coverage (1Cr), 400 employees on <1Cr turnover, Core Banking Software + <1Cr. "
            "Bad docs: PAN card partial (no PAN line), GST cert partial (no GSTIN), "
            "personal name 'Vikram Malhotra Singh' on cheque. Company < 2 years old."
        ),
        "docs_to_upload": [
            {"file": "docs/nexaflow_v1/pan_card.jpg", "doc_type": "pan_card"},
            {"file": "docs/nexaflow_v1/gst_cert.pdf", "doc_type": "gst_cert"},
            {"file": "docs/nexaflow_v1/cancelled_cheque.jpg", "doc_type": "cancelled_cheque"},
            {"file": "docs/nexaflow_v1/incorporation.pdf", "doc_type": "incorporation"},
            {"file": "docs/nexaflow_v1/iso_cert.pdf", "doc_type": "iso_cert"},
            {"file": "docs/nexaflow_v1/dpa.pdf", "doc_type": "dpa"},
        ],
        "expected_layer1": "submitted",
        "expected_risk_factors": [
            "data_offshore (high=10)",
            "iso_cert_expired (high=10) ← notified",
            "employee_turnover_mismatch (high=10)",
            "processes_data_no_soc2 (med=5)",
            "low_cyber_coverage (med=5)",
            "new_company (low=2)",
            "partial_ocr_pan_card (med=5) ← notified",
            "partial_ocr_gst_cert (med=5) ← notified",
            "account_holder_name_mismatch (high=10) ← notified",
        ],
        "expected_user_flags": [
            "iso_cert — expired, upload renewed (high)",
            "pan_number — partial read, re-upload (medium)",
            "gst_number — partial read, re-upload (medium)",
            "account_holder_name — personal name on cheque (high)",
        ],
        "expected_base_score": 62,
        "expected_delta": 0,
        "expected_final_score": 62,
        "expected_decision": "human_review",
        "expected_email": "fires — 4 user_flags sent to vendor",
        "notified_factors_for_next_version": [
            "iso_cert_expired", "partial_ocr_pan_card",
            "partial_ocr_gst_cert", "account_holder_name_mismatch",
        ],
    })

    # ── V2 ────────────────────────────────────────────────────────────────────
    v2_dir = case_dir / "v2"
    docs_dir = str(v2_dir / "docs" / "nexaflow_v2")
    _ensure_dir(docs_dir)

    # Same docs, no fix
    gen_pan_card_partial(docs_dir, "Nexaflow Systems Private Limited")
    gen_gst_cert_partial(docs_dir, "Nexaflow Systems Private Limited",
                         form_v1["incorporation_date"])
    gen_cancelled_cheque(docs_dir, form_v1["ifsc_code"], form_v1["account_number"],
                         form_v1["bank_name"], "Vikram Malhotra Singh")
    generate_incorporation_cert(docs_dir, cin, "Nexaflow Systems Private Limited",
                                form_v1["incorporation_date"])
    generate_iso_cert(docs_dir, iso_cert_number, "Nexaflow Systems Private Limited",
                      expired_iso)
    generate_dpa(docs_dir, "Nexaflow Systems Private Limited", "Deepak Krishnaswamy")

    save_version(v2_dir, form_v1, {
        "case": "escalation_case_02",
        "version": 2,
        "login_email": "vendor.nexaflow@nexaflow.io",
        "description": "Vendor ignored all flags. Same form, same docs. No improvement.",
        "docs_to_upload": [
            {"file": "docs/nexaflow_v2/pan_card.jpg", "doc_type": "pan_card"},
            {"file": "docs/nexaflow_v2/gst_cert.pdf", "doc_type": "gst_cert"},
            {"file": "docs/nexaflow_v2/cancelled_cheque.jpg", "doc_type": "cancelled_cheque"},
            {"file": "docs/nexaflow_v2/incorporation.pdf", "doc_type": "incorporation"},
            {"file": "docs/nexaflow_v2/iso_cert.pdf", "doc_type": "iso_cert"},
            {"file": "docs/nexaflow_v2/dpa.pdf", "doc_type": "dpa"},
        ],
        "expected_layer1": "submitted",
        "expected_base_score": 62,
        "expected_delta": 20,
        "expected_delta_note": "4 notified from V1 all repeated × 5 × 1.0 = +20",
        "expected_final_score": 82,
        "expected_decision": "high_risk_review",
        "expected_email": "fires — same flags again",
        "notified_factors_for_next_version": [
            "iso_cert_expired", "partial_ocr_pan_card",
            "partial_ocr_gst_cert", "account_holder_name_mismatch",
        ],
    })

    # ── V3 ────────────────────────────────────────────────────────────────────
    v3_dir = case_dir / "v3"
    docs_dir = str(v3_dir / "docs" / "nexaflow_v3")
    _ensure_dir(docs_dir)

    new_iso_expiry = (date.today() + timedelta(days=900)).isoformat()
    gen_pan_card(docs_dir, pan, "Nexaflow Systems Private Limited")         # correct PAN ✓
    generate_gst_cert(docs_dir, gst, "Nexaflow Systems Private Limited",
                      form_v1["incorporation_date"])                         # correct GSTIN ✓
    gen_cancelled_cheque(docs_dir, form_v3["ifsc_code"], form_v3["account_number"],
                         form_v3["bank_name"], "Nexaflow Systems Pvt Ltd")  # company name ✓
    generate_incorporation_cert(docs_dir, cin, "Nexaflow Systems Private Limited",
                                form_v1["incorporation_date"])
    generate_iso_cert(docs_dir, iso_cert_number, "Nexaflow Systems Private Limited",
                      new_iso_expiry)                                        # renewed ISO ✓
    generate_dpa(docs_dir, "Nexaflow Systems Private Limited", "Deepak Krishnaswamy")

    save_version(v3_dir, form_v3, {
        "case": "escalation_case_02",
        "version": 3,
        "login_email": "vendor.nexaflow@nexaflow.io",
        "description": (
            "Vendor fixed everything. data_in_india=true, soc2=true, ISO renewed, "
            "cyber_coverage=15Cr, employee_count=25 (plausible), service=SaaS Platform. "
            "Correct PAN card, correct GSTIN, company name on cheque."
        ),
        "docs_to_upload": [
            {"file": "docs/nexaflow_v3/pan_card.jpg", "doc_type": "pan_card"},
            {"file": "docs/nexaflow_v3/gst_cert.pdf", "doc_type": "gst_cert"},
            {"file": "docs/nexaflow_v3/cancelled_cheque.jpg", "doc_type": "cancelled_cheque"},
            {"file": "docs/nexaflow_v3/incorporation.pdf", "doc_type": "incorporation"},
            {"file": "docs/nexaflow_v3/iso_cert.pdf", "doc_type": "iso_cert"},
            {"file": "docs/nexaflow_v3/dpa.pdf", "doc_type": "dpa"},
        ],
        "expected_layer1": "submitted",
        "expected_risk_factors": [
            "new_company (low=2) — company < 2 years, cannot be fixed",
        ],
        "expected_user_flags": [],
        "expected_base_score": 2,
        "expected_delta": -18,
        "expected_delta_note": (
            "4 resolved from V2 × -3 × 1.0 = -12 | "
            "4 resolved from V1 × -3 × 0.5 = -6 | total = -18"
        ),
        "expected_final_score": 0,
        "expected_decision": "approved",
        "expected_email": "no email — no user_flags",
    })


# ── Case 3 — Scammer: Human Review → High Risk → Rejected ────────────────────
# "Vortex Global Technologies Private Limited" — Telangana
#
# Same risk profile as Case 2 V1. Vendor shows zero improvement across 3 versions.
# Escalation via cross-version repeated notified factors pushes score over 90.
#
# V1: base=62, delta=0  → final=62 → human_review
# V2: base=62, delta=+20 (4 notified from V1 × 5 × 1.0) → final=82 → high_risk_review
# V3: base=62, delta=+20 (4 from V2 × 5 × 1.0) + +10 (4 from V1 × 5 × 0.5)
#      → delta=+30, final=92 → rejected (≥90) ✓

def case_03():
    case_dir = OUT / "escalation_case_03_scammer_rejected"
    print(f"\n[Case 3] Scammer: Human Review V1 → High Risk V2 → Rejected V3")

    pan = "AABCV9988R"                  # C = Private Limited ✓
    gst = "36AABCV9988R1Z7"             # 36=Telangana ✓
    cin = "U72200TS2023PTC555123"
    iso_cert_number = "IS 112843"
    expired_iso = (date.today() - timedelta(days=420)).isoformat()  # ~14 months ago

    form = {
        "company_name": "Vortex Global Technologies Private Limited",
        "company_type": "Private Limited",
        "incorporation_date": (date.today() - timedelta(days=520)).isoformat(),  # ~1.4 years
        "registered_address": "8-2-293, Road No. 12, Banjara Hills",
        "city": "Hyderabad",
        "state": "Telangana",
        "employee_count": 450,
        "annual_turnover": "<1 Cr",
        "website": "https://vortexglobal.tech",
        "signatory_name": "Suresh Venkata Rao",
        "pan_number": pan,
        "gst_registered": True,
        "gst_number": gst,
        "din": "04321987",
        "cin_number": cin,
        "account_holder_name": "Vortex Global Tech Pvt Ltd",
        "bank_name": "State Bank of India",
        "account_number": "10000234567890",
        "ifsc_code": "SBIN0000123",
        "account_type": "Current",
        "iso_certified": True,
        "iso_cert_number": iso_cert_number,
        "iso_expiry_date": expired_iso,
        "soc2_audited": False,
        "service_nature": "Core Banking Software",
        "processes_data": True,
        "data_in_india": False,
        "cloud_provider": "GCP",
        "cyber_insurance": True,
        "cyber_coverage_crores": 0.5,    # very low
        "contact_name": "Suresh Rao",
        "contact_email": "suresh@vortexglobal.tech",
        "contact_phone": "+917654321098",
    }

    personal_name = "Prashant Kumar Joshi"

    for version in range(1, 4):
        v_dir = case_dir / f"v{version}"
        docs_dir = str(v_dir / "docs" / f"vortex_v{version}")
        _ensure_dir(docs_dir)

        # Same docs every version — scammer never fixes anything
        gen_pan_card_partial(docs_dir, "Vortex Global Technologies Private Limited")
        gen_gst_cert_partial(docs_dir, "Vortex Global Technologies Private Limited",
                             form["incorporation_date"])
        gen_cancelled_cheque(docs_dir, form["ifsc_code"], form["account_number"],
                             form["bank_name"], personal_name)
        generate_incorporation_cert(docs_dir, cin, "Vortex Global Technologies Private Limited",
                                    form["incorporation_date"])
        generate_iso_cert(docs_dir, iso_cert_number, "Vortex Global Technologies Private Limited",
                          expired_iso)
        generate_dpa(docs_dir, "Vortex Global Technologies Private Limited", "Suresh Venkata Rao")

        if version == 1:
            expected_decision = "human_review"
            base = 62; delta = 0; final = 62
            delta_note = "first submission — no prior versions"
        elif version == 2:
            expected_decision = "high_risk_review"
            base = 62; delta = 20; final = 82
            delta_note = "4 notified from V1 × 5 × 1.0 = +20"
        else:
            expected_decision = "rejected"
            base = 62; delta = 30; final = 92
            delta_note = (
                "4 repeated from V2 × 5 × 1.0 = +20 | "
                "4 repeated from V1 × 5 × 0.5 = +10 | total delta = +30"
            )

        save_version(v_dir, form, {
            "case": "escalation_case_03",
            "version": version,
            "login_email": "vendor.vortex@vortexglobal.tech",
            "description": (
                f"Scammer V{version}. Same form, same bad docs. No changes. "
                "Score escalates via cross-version repeated notified factors."
            ),
            "docs_to_upload": [
                {"file": f"docs/vortex_v{version}/pan_card.jpg",       "doc_type": "pan_card"},
                {"file": f"docs/vortex_v{version}/gst_cert.pdf",       "doc_type": "gst_cert"},
                {"file": f"docs/vortex_v{version}/cancelled_cheque.jpg","doc_type": "cancelled_cheque"},
                {"file": f"docs/vortex_v{version}/incorporation.pdf",   "doc_type": "incorporation"},
                {"file": f"docs/vortex_v{version}/iso_cert.pdf",       "doc_type": "iso_cert"},
                {"file": f"docs/vortex_v{version}/dpa.pdf",            "doc_type": "dpa"},
            ],
            "expected_layer1": "submitted",
            "expected_risk_factors": [
                "data_offshore (high=10)",
                "iso_cert_expired (high=10) ← notified",
                "employee_turnover_mismatch (high=10)",
                "processes_data_no_soc2 (med=5)",
                "low_cyber_coverage (med=5)",
                "new_company (low=2)",
                "partial_ocr_pan_card (med=5) ← notified",
                "partial_ocr_gst_cert (med=5) ← notified",
                "account_holder_name_mismatch (high=10) ← notified",
            ],
            "expected_user_flags": [
                "iso_cert — expired (high)",
                "pan_number — partial read (medium)",
                "gst_number — partial read (medium)",
                "account_holder_name — personal name (high)",
            ],
            "expected_base_score": base,
            "expected_delta": delta,
            "expected_delta_note": delta_note,
            "expected_final_score": final,
            "expected_decision": expected_decision,
            "expected_email": (
                "fires" if expected_decision != "rejected" else
                "no email — decision=rejected, email suppressed"
            ),
        })


if __name__ == "__main__":
    print("Generating 3 escalation test cases...\n")
    case_01()
    case_02()
    case_03()
    print(f"\nDone. Output in {OUT}/")
    print("""
Manual test steps:
  1. Start backend:  cd vendor_onbording_backend && uvicorn main:app --reload --port 8000
  2. Start frontend: cd vendor_onboarding_frontend && npm run dev
  3. For each case + version:
     a. Login with the login_email from meta.json
     b. Upload each file listed in docs_to_upload
     c. Submit the payload from payload.json (or fill the form manually)
     d. Wait ~30s for OCR + AI pipeline
     e. Login to admin dashboard → check decision, risk_score, user_flags, risk_reasoning
     f. Verify against expected_decision and expected_final_score in meta.json

Case summary:
  Case 1 — Crescendo Tech: V1 waiting_for_response (score 10) → V2 approved (score 0)
  Case 2 — Nexaflow Systems: V1 human_review (62) → V2 high_risk_review (82) → V3 approved (0)
  Case 3 — Vortex Global: V1 human_review (62) → V2 high_risk_review (82) → V3 rejected (92)
""")
