#!/usr/bin/env python3
"""
Generates all 10 final test cases with docs.
Run from vendor_onboarding_data_generator/:
  python final_tests/generate_tests.py
"""
import sys
import os
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from generators.company import generate_company
from generators.legal import (
    generate_legal, generate_pan, generate_gst, generate_cin,
    generate_msme, STATE_ABBR
)
from generators.banking import generate_banking
from generators.compliance import generate_compliance, generate_iso_cert_number
from generators.contact import generate_contact
from generators.documents import generate_all_documents
from scenarios.base import assemble_vendor, build_valid
from datetime import date, timedelta
import random

OUT = Path(__file__).parent


def save(test_dir: Path, payload: dict, subdir: str = ""):
    target = test_dir / subdir if subdir else test_dir
    target.mkdir(parents=True, exist_ok=True)
    with open(target / "payload.json", "w") as f:
        json.dump(payload["form_data"], f, indent=2, default=str)
    meta = {
        "test_name": payload.get("test_name"),
        "email": payload.get("email"),
        "expected_round_1": payload.get("expected_round_1"),
        "expected_round_2": payload.get("expected_round_2"),
        "notes": payload.get("notes"),
        "documents": payload.get("documents", []),
    }
    with open(target / "meta.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)
    print(f"  saved → {target}/payload.json  ({len(payload.get('documents', []))} docs)")


# ── Test 01: Pvt Ltd — clean pass ────────────────────────────────────────────
def test_01():
    d = OUT / "test_01_pass_pvt_ltd"
    company = generate_company(company_type="Private Limited", state="Maharashtra")
    company["employee_count"] = 85
    company["annual_turnover"] = "10-100 Cr"
    legal = generate_legal(company, include_gst=True)
    banking = generate_banking(company)
    compliance = generate_compliance(force_processes_data=True)
    contact = generate_contact(company)
    docs_dir = str(d / "docs")
    p = assemble_vendor(company, legal, banking, compliance, contact, output_base=docs_dir)
    p["test_name"] = "test_01_pass_pvt_ltd"
    p["email"] = "test1@gmail.com"
    p["expected_round_1"] = "submitted"
    p["notes"] = "Private Limited, GST registered, ISO certified, processes data. Should pass in one shot."
    save(d, p)


# ── Test 02: LLP, no GST — clean pass ────────────────────────────────────────
def test_02():
    d = OUT / "test_02_pass_llp_no_gst"
    company = generate_company(company_type="LLP", state="Karnataka")
    legal = generate_legal(company, include_gst=False)
    banking = generate_banking(company)
    compliance = generate_compliance(force_processes_data=False)
    contact = generate_contact(company)
    docs_dir = str(d / "docs")
    p = assemble_vendor(company, legal, banking, compliance, contact, output_base=docs_dir)
    p["test_name"] = "test_02_pass_llp_no_gst"
    p["email"] = "test2@gmail.com"
    p["expected_round_1"] = "submitted"
    p["notes"] = "LLP, GST exempt, dpin + llp_number present. Should pass in one shot."
    save(d, p)


# ── Test 03: Partnership + MSME — clean pass ─────────────────────────────────
def test_03():
    d = OUT / "test_03_pass_partnership_msme"
    company = generate_company(company_type="Partnership Firm", state="Gujarat")
    company["employee_count"] = 40
    company["annual_turnover"] = "1-10 Cr"
    legal = generate_legal(company, include_gst=True)
    legal["msme_number"] = generate_msme(company["state"])
    legal["_meta"]["pan"] = legal["pan_number"]
    banking = generate_banking(company)
    compliance = generate_compliance(force_processes_data=False)
    contact = generate_contact(company)
    docs_dir = str(d / "docs")
    p = assemble_vendor(company, legal, banking, compliance, contact, output_base=docs_dir)
    p["test_name"] = "test_03_pass_partnership_msme"
    p["email"] = "test3@gmail.com"
    p["expected_round_1"] = "submitted"
    p["notes"] = "Partnership Firm, MSME eligible, partnership_deed + msme_cert docs. Should pass in one shot."
    save(d, p)


# ── Test 04: Fix CIN year — fail → pass ──────────────────────────────────────
def test_04():
    d = OUT / "test_04_fix_cin_year"
    company = generate_company(company_type="Private Limited", state="Delhi")
    legal = generate_legal(company, include_gst=True)
    banking = generate_banking(company)
    compliance = generate_compliance()
    contact = generate_contact(company)
    docs_dir_r1 = str(d / "round_1" / "docs")

    # Round 1: corrupt CIN year
    p1 = assemble_vendor(company, legal, banking, compliance, contact, output_base=docs_dir_r1)
    cin = p1["form_data"]["cin_number"]
    p1["form_data"]["cin_number"] = cin[:8] + "1999" + cin[12:]   # wrong year
    p1["test_name"] = "test_04_fix_cin_year"
    p1["email"] = "test4@gmail.com"
    p1["expected_round_1"] = "draft"
    p1["expected_round_2"] = "submitted"
    p1["notes"] = "Round 1: CIN year=1999 (wrong). Round 2: CIN year corrected to incorporation year."
    save(d, p1, subdir="round_1")

    # Round 2: correct CIN (original legal data had correct CIN)
    docs_dir_r2 = str(d / "round_2" / "docs")
    p2 = assemble_vendor(company, legal, banking, compliance, contact, output_base=docs_dir_r2)
    p2["test_name"] = "test_04_fix_cin_year"
    p2["email"] = "test4@gmail.com"
    p2["expected_round_1"] = "submitted"
    p2["notes"] = "Round 2: CIN year corrected. Should submit successfully."
    save(d, p2, subdir="round_2")


# ── Test 05: Fix free email — fail → pass ────────────────────────────────────
def test_05():
    d = OUT / "test_05_fix_free_email"
    company = generate_company(company_type="Sole Proprietorship", state="Tamil Nadu")
    legal = generate_legal(company, include_gst=True)
    banking = generate_banking(company)
    compliance = generate_compliance()
    docs_dir_r1 = str(d / "round_1" / "docs")

    # Round 1: gmail contact
    contact_bad = generate_contact(company, force_free_email=True)
    p1 = assemble_vendor(company, legal, banking, compliance, contact_bad, output_base=docs_dir_r1)
    p1["test_name"] = "test_05_fix_free_email"
    p1["email"] = "test5@gmail.com"
    p1["expected_round_1"] = "draft"
    p1["expected_round_2"] = "submitted"
    p1["notes"] = "Round 1: contact_email uses gmail.com. Round 2: corrected to company domain."
    save(d, p1, subdir="round_1")

    # Round 2: company email
    docs_dir_r2 = str(d / "round_2" / "docs")
    contact_good = generate_contact(company, force_free_email=False)
    p2 = assemble_vendor(company, legal, banking, compliance, contact_good, output_base=docs_dir_r2)
    p2["test_name"] = "test_05_fix_free_email"
    p2["email"] = "test5@gmail.com"
    p2["expected_round_1"] = "submitted"
    p2["notes"] = "Round 2: company domain email. Should submit successfully."
    save(d, p2, subdir="round_2")


# ── Test 06: Fix missing DPA — fail → pass ───────────────────────────────────
def test_06():
    d = OUT / "test_06_fix_missing_dpa"
    company = generate_company(company_type="Private Limited", state="Telangana")
    legal = generate_legal(company, include_gst=True)
    banking = generate_banking(company)
    compliance = generate_compliance(force_processes_data=True)
    contact = generate_contact(company)
    docs_dir_r1 = str(d / "round_1" / "docs")

    # Round 1: remove DPA doc
    p1 = assemble_vendor(company, legal, banking, compliance, contact, output_base=docs_dir_r1)
    p1["documents"] = [doc for doc in p1["documents"] if doc["doc_type"] != "dpa"]
    p1["test_name"] = "test_06_fix_missing_dpa"
    p1["email"] = "test6@gmail.com"
    p1["expected_round_1"] = "draft"
    p1["expected_round_2"] = "submitted"
    p1["notes"] = "Round 1: processes_data=True but DPA doc missing. Round 2: DPA added."
    save(d, p1, subdir="round_1")

    # Round 2: all docs including DPA
    docs_dir_r2 = str(d / "round_2" / "docs")
    p2 = assemble_vendor(company, legal, banking, compliance, contact, output_base=docs_dir_r2)
    p2["test_name"] = "test_06_fix_missing_dpa"
    p2["email"] = "test6@gmail.com"
    p2["expected_round_1"] = "submitted"
    p2["notes"] = "Round 2: DPA document included. Should submit successfully."
    save(d, p2, subdir="round_2")


# ── Test 07: PAN type mismatch — always fail ─────────────────────────────────
def test_07():
    d = OUT / "test_07_fail_pan_type"
    company = generate_company(company_type="Private Limited", state="West Bengal")
    legal = generate_legal(company, include_gst=True)
    # Corrupt PAN: replace 4th char C → F (firm char for a company)
    pan = legal["pan_number"]
    legal["pan_number"] = pan[:3] + "F" + pan[4:]
    # Also update GST to embed the corrupted PAN
    if legal.get("gst_number"):
        gst = legal["gst_number"]
        legal["gst_number"] = gst[:2] + legal["pan_number"] + gst[12:]
    banking = generate_banking(company)
    compliance = generate_compliance()
    contact = generate_contact(company)
    docs_dir = str(d / "docs")
    p = assemble_vendor(company, legal, banking, compliance, contact, output_base=docs_dir)
    p["test_name"] = "test_07_fail_pan_type"
    p["email"] = "test7@gmail.com"
    p["expected_round_1"] = "draft"
    p["notes"] = "PAN 4th char=F but company_type=Private Limited (needs C). Always fails Phase 1."
    save(d, p)


# ── Test 08: Data offshore — always fail ─────────────────────────────────────
def test_08():
    d = OUT / "test_08_fail_data_offshore"
    company = generate_company(company_type="LLP", state="Punjab")
    legal = generate_legal(company, include_gst=True)
    banking = generate_banking(company)
    compliance = generate_compliance(force_processes_data=False, force_data_offshore=True)
    contact = generate_contact(company)
    docs_dir = str(d / "docs")
    p = assemble_vendor(company, legal, banking, compliance, contact, output_base=docs_dir)
    p["test_name"] = "test_08_fail_data_offshore"
    p["email"] = "test8@gmail.com"
    p["expected_round_1"] = "submitted"
    p["notes"] = "data_in_india=False. WARNING only — not a hard block per spec. Submits but flagged for RBI review."
    save(d, p)


# ── Test 09: No cyber insurance — always fail ────────────────────────────────
def test_09():
    d = OUT / "test_09_fail_no_cyber"
    company = generate_company(company_type="Private Limited", state="Rajasthan")
    legal = generate_legal(company, include_gst=True)
    banking = generate_banking(company)
    compliance = generate_compliance(force_processes_data=True)
    compliance["cyber_insurance"] = False
    compliance.pop("cyber_coverage_crores", None)
    contact = generate_contact(company)
    docs_dir = str(d / "docs")
    p = assemble_vendor(company, legal, banking, compliance, contact, output_base=docs_dir)
    p["test_name"] = "test_09_fail_no_cyber"
    p["email"] = "test9@gmail.com"
    p["expected_round_1"] = "draft"
    p["notes"] = "processes_data=True but cyber_insurance=False. Always fails Phase 1."
    save(d, p)


# ── Test 10: Phase 2 preview — passes Phase 1, needs AI to catch ─────────────
def test_10():
    d = OUT / "test_10_phase2_preview"
    company = generate_company(company_type="Private Limited", state="Karnataka")
    legal = generate_legal(company, include_gst=True)
    banking = generate_banking(company)
    # Completely unrelated account holder name — Phase 1 won't catch, Phase 2 will
    banking["account_holder_name"] = "Random Traders Private Limited"
    compliance = generate_compliance(force_processes_data=True)
    contact = generate_contact(company)
    docs_dir = str(d / "docs")
    p = assemble_vendor(company, legal, banking, compliance, contact, output_base=docs_dir)
    p["test_name"] = "test_10_phase2_preview"
    p["email"] = "test10@gmail.com"
    p["expected_round_1"] = "submitted"  # Phase 1 passes — no fuzzy check yet
    p["notes"] = (
        "MY CHOICE: account_holder_name='Random Traders Private Limited' has zero relation "
        "to actual company_name. Phase 1 passes (no fuzzy match rule). "
        "Phase 2 AI will flag this as account name mismatch — potential fraud signal."
    )
    save(d, p)


# ── Test 11: 3-round trail — manual doc-linking verification ─────────────────
def test_11():
    d = OUT / "test_11_trail_verify"
    # Sole Proprietorship = minimal fields (no CIN/DIN/LLP/DPIN)
    # No GST, no ISO, no processes_data → required docs: pan_card + cancelled_cheque + msme_cert (if MSME)
    company = generate_company(company_type="Sole Proprietorship", state="Maharashtra")
    legal = generate_legal(company, include_gst=False)
    # Force MSME so we have 3 required docs and can demo partial upload
    if not legal.get("msme_number"):
        from generators.legal import generate_msme
        legal["msme_number"] = generate_msme(company["state"])
    banking = generate_banking(company)
    compliance = generate_compliance(force_processes_data=False)
    compliance["iso_certified"] = False
    compliance.pop("iso_cert_number", None)
    compliance.pop("iso_expiry_date", None)
    contact = generate_contact(company)
    docs_dir = str(d / "docs")  # all docs generated once, shared across rounds

    # Build clean base (generates all 3 docs: pan_card, cancelled_cheque, msme_cert)
    base = assemble_vendor(company, legal, banking, compliance, contact, output_base=docs_dir)

    msme_doc   = next(doc for doc in base["documents"] if doc["doc_type"] == "msme_cert")
    other_docs = [doc for doc in base["documents"] if doc["doc_type"] != "msme_cert"]

    # ── Round 1: bad PAN + missing msme_cert → 2 errors ─────────────────────
    p1 = deepcopy(base)
    pan = p1["form_data"]["pan_number"]
    p1["form_data"]["pan_number"] = pan[:3] + "C" + pan[4:]   # P → C (wrong entity type)
    p1["documents"] = other_docs   # pan_card + cancelled_cheque, NO msme_cert
    p1["test_name"] = "test_11_trail_verify"
    p1["email"] = "test11@gmail.com"
    p1["expected_round_1"] = "draft"
    p1["notes"] = "Round 1: PAN 4th char C (needs P for Sole Prop) + msme_cert not uploaded. Two errors."
    save(d, p1, subdir="round_1")

    # ── Round 2: fix PAN, upload msme_cert only, but bad IFSC → 1 error ─────
    p2 = deepcopy(base)
    ifsc = p2["form_data"]["ifsc_code"]
    p2["form_data"]["ifsc_code"] = ifsc[:4] + "1" + ifsc[5:]  # 5th char 0 → 1
    p2["documents"] = [msme_doc]   # only the missing doc — user re-uploads just this one
    p2["test_name"] = "test_11_trail_verify"
    p2["email"] = "test11@gmail.com"
    p2["expected_round_1"] = "draft"
    p2["notes"] = "Round 2: PAN fixed, msme_cert uploaded. IFSC 5th char wrong. One error remains."
    save(d, p2, subdir="round_2")

    # ── Round 3: fix IFSC, no new docs needed → submitted ────────────────────
    p3 = deepcopy(base)
    p3["documents"] = []   # all 3 docs already linked from rounds 1+2
    p3["test_name"] = "test_11_trail_verify"
    p3["email"] = "test11@gmail.com"
    p3["expected_round_1"] = "submitted"
    p3["notes"] = "Round 3: IFSC fixed. No new docs — all 3 already linked. Should submit."
    save(d, p3, subdir="round_3")


if __name__ == "__main__":
    print("Generating 10 automated + 1 manual trail test...\n")
    for i, fn in enumerate([
        test_01, test_02, test_03,
        test_04, test_05, test_06,
        test_07, test_08, test_09,
        test_10, test_11,
    ], start=1):
        print(f"[{i:02d}] {fn.__name__}")
        fn()
    print("\nDone. All tests generated in final_tests/")
