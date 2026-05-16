#!/usr/bin/env python3
"""
Generates 3 manual test cases for end-to-end testing.

Run from vendor_onboarding_data_generator/:
  python generate.py

Output: output/case_01_clean_pass/
        output/case_02_ai_mismatch/
        output/case_03_high_risk/

Each case folder has:
  payload.json  — POST this body to /api/application/submit
  meta.json     — what to expect from each pipeline layer
  docs/vendor_*/  — upload these files via /api/documents/upload
"""
import json
import sys
import uuid
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from generators.company import generate_company
from generators.legal import generate_legal
from generators.banking import generate_banking
from generators.compliance import generate_compliance, generate_iso_cert_number
from generators.contact import generate_contact
from generators.documents import generate_all_documents
from scenarios.base import assemble_vendor

OUT = ROOT / "output"


def save_case(case_dir: Path, form_data: dict, docs: list, meta: dict):
    case_dir.mkdir(parents=True, exist_ok=True)
    with open(case_dir / "payload.json", "w") as f:
        json.dump(form_data, f, indent=2, default=str)
    with open(case_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)
    print(f"  [{meta['case']}] {len(docs)} docs → {case_dir}")


# ── Case 1: Clean valid vendor ────────────────────────────────────────────────
# Private Limited. All docs embed values that match form exactly.
# Good compliance: data in India, ISO valid, SOC2 audited.
# Expected: Layer 1 → submitted. AI → no flags. decision = approved.

def case_01_clean_pass():
    company = generate_company(company_type="Private Limited")
    legal = generate_legal(company)
    banking = generate_banking(company)
    compliance = generate_compliance(force_processes_data=True, force_data_offshore=False)
    compliance["data_in_india"] = True
    compliance["soc2_audited"] = True
    compliance["iso_certified"] = True
    compliance["iso_cert_number"] = generate_iso_cert_number()
    compliance["iso_expiry_date"] = (date.today() + timedelta(days=365)).isoformat()
    contact = generate_contact(company)

    vendor_id = f"vendor_{uuid.uuid4().hex[:8]}"
    vendor = assemble_vendor(
        company, legal, banking, compliance, contact,
        output_base=str(OUT / "case_01_clean_pass" / "docs"),
        vendor_id=vendor_id,
    )

    save_case(
        OUT / "case_01_clean_pass",
        vendor["form_data"],
        vendor["documents"],
        {
            "case": "case_01_clean_pass",
            "description": (
                "Private Limited. All docs match form exactly. "
                "Data in India. ISO valid 1 year. SOC2 audited."
            ),
            "expected_layer1": "submitted",
            "expected_ai_decision": "approved",
            "expected_user_flags": [],
            "expected_risk_factors": [],
        },
    )


# ── Case 2: AI mismatch flags ─────────────────────────────────────────────────
# Form has correct values. Docs have wrong PAN + unrelated account holder name.
# Layer 1 passes (format valid). AI catches both mismatches via OCR cross-check.
# Expected: Layer 1 → submitted. AI → pan_number + account_holder_name flags.
# decision = waiting_for_response.

def case_02_ai_mismatch():
    company = generate_company(company_type="Private Limited")
    legal = generate_legal(company)
    banking = generate_banking(company)
    compliance = generate_compliance(force_processes_data=False, force_data_offshore=False)
    compliance["data_in_india"] = True
    contact = generate_contact(company)

    vendor_id = f"vendor_{uuid.uuid4().hex[:8]}"
    case_dir = OUT / "case_02_ai_mismatch"

    # Form data uses correct values
    form_data = {}
    for d in (company, legal, banking, compliance, contact):
        for k, v in d.items():
            if not k.startswith("_"):
                form_data[k] = v

    # Docs embed WRONG values:
    # - PAN card: last letter flipped (format still valid, value differs)
    # - Cancelled cheque: unrelated personal name as account holder
    corrupted_legal = deepcopy(legal)
    pan = legal["pan_number"]
    corrupted_legal["pan_number"] = pan[:9] + ("Z" if pan[9] != "Z" else "A")

    corrupted_banking = deepcopy(banking)
    corrupted_banking["account_holder_name"] = "Rajesh Kumar Mehta"

    docs = generate_all_documents(
        vendor_id=vendor_id,
        output_base=str(case_dir / "docs"),
        form_data=form_data,
        legal_data=corrupted_legal,
        banking_data=corrupted_banking,
        compliance_data=compliance,
    )

    save_case(
        case_dir,
        form_data,
        docs,
        {
            "case": "case_02_ai_mismatch",
            "description": (
                "Form has correct PAN and company account holder. "
                f"PAN card doc has PAN ending in '{corrupted_legal['pan_number'][-1]}' "
                f"(form says '{pan[-1]}'). "
                "Cancelled cheque shows 'Rajesh Kumar Mehta' — unrelated personal name."
            ),
            "expected_layer1": "submitted",
            "expected_ai_decision": "waiting_for_response",
            "expected_user_flags": ["pan_number mismatch", "account_holder_name mismatch"],
            "expected_risk_factors": ["account_holder_name_mismatch"],
            "form_pan": pan,
            "doc_pan": corrupted_legal["pan_number"],
        },
    )


# ── Case 3: High risk vendor ──────────────────────────────────────────────────
# Docs match form exactly. Risk is in the form values themselves.
# data_in_india=False, soc2=False, ISO expired ~13 months ago, low cyber coverage.
# Expected: Layer 1 → submitted. AI → 4 risk factors. decision = human_review or high_risk_review.

def case_03_high_risk():
    company = generate_company(company_type="Private Limited")
    legal = generate_legal(company)
    banking = generate_banking(company)
    contact = generate_contact(company)

    expired_date = (date.today() - timedelta(days=400)).isoformat()
    compliance = {
        "service_nature": "Core Banking Software",
        "processes_data": True,
        "data_in_india": False,
        "cloud_provider": "AWS",
        "iso_certified": True,
        "iso_cert_number": generate_iso_cert_number(),
        "iso_expiry_date": expired_date,
        "soc2_audited": False,
        "cyber_insurance": True,
        "cyber_coverage_crores": 1.0,
    }

    vendor_id = f"vendor_{uuid.uuid4().hex[:8]}"
    vendor = assemble_vendor(
        company, legal, banking, compliance, contact,
        output_base=str(OUT / "case_03_high_risk" / "docs"),
        vendor_id=vendor_id,
    )

    save_case(
        OUT / "case_03_high_risk",
        vendor["form_data"],
        vendor["documents"],
        {
            "case": "case_03_high_risk",
            "description": (
                f"data_in_india=False (offshore). soc2_audited=False. "
                f"ISO cert expired {expired_date} (~13 months ago). "
                "cyber_coverage=₹1Cr (low for data processor). "
                "All docs match form — risk is in compliance posture only."
            ),
            "expected_layer1": "submitted",
            "expected_ai_decision": "human_review or high_risk_review",
            "expected_risk_factors": [
                "data_offshore",
                "processes_data_no_soc2",
                "iso_cert_expired",
                "low_cyber_coverage",
            ],
            "expected_user_flags": ["iso_cert (expired — vendor notified to renew)"],
        },
    )


if __name__ == "__main__":
    print("Generating 3 test cases...\n")
    case_01_clean_pass()
    case_02_ai_mismatch()
    case_03_high_risk()
    print(f"\nDone. Output in {OUT}/")
    print("\nManual test steps per case:")
    print("  1. Start backend:  uvicorn main:app --reload --port 8000")
    print("  2. Login:          POST /api/auth/login with any email")
    print("  3. Upload docs:    POST /api/documents/upload for each file in docs/vendor_*/")
    print("  4. Submit:         POST /api/application/submit with payload.json body")
    print("  5. Wait ~30s for OCR + AI pipeline to complete in background")
    print("  6. Check Supabase: reviews table → risk_score, decision, risk_reasoning, user_flags")
