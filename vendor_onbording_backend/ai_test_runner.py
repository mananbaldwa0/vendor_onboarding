"""
Run AI pipeline test cases against Groq and write results to ai_test_output.json.
Usage: python3 ai_test_runner.py
"""
import json
import os
import sys
from datetime import date
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from services.ai_service import _call_llm, SYSTEM_PROMPT, _compute_company_age_years

TODAY = date.today().isoformat()

# ── Test cases in exact LLM feeding format ─────────────────────────────────────

TEST_CASES = [

    # ── 1. All clean — no flags, only minor risk (new company) ──────────────────
    {
        "id": "tc_01_all_clean",
        "description": "Clean vendor. All docs match form. Only risk: company < 2 years old.",
        "input": {
            "today": TODAY,
            "form": {
                "company_name": "Nexvault Technologies Private Limited",
                "company_type": "Private Limited",
                "pan_number": "AABCN1234C",
                "state": "Maharashtra",
                "gst_registered": True,
                "gst_number": "27AABCN1234C1Z5",
                "incorporation_date": "2024-02-10",
                "annual_turnover": "1-10 Cr",
                "employee_count": 35,
                "account_holder_name": "Nexvault Technologies Pvt Ltd",
                "bank_name": "HDFC Bank",
                "account_number": "003601234567",
                "ifsc_code": "HDFC0001234",
                "iso_certified": False,
                "soc2_audited": False,
                "processes_data": False,
                "data_in_india": True,
                "cyber_insurance": False,
                "service_nature": "SaaS Platform",
                "contact_email": "admin@nexvault.io",
            },
            "ocr": {
                "pan_card":         {"status": "done", "pan_number": "AABCN1234C", "name_on_card": "NEXVAULT TECHNOLOGIES PVT LTD"},
                "cancelled_cheque": {"status": "done", "ifsc_code": "HDFC0001234", "account_number": "003601234567", "account_holder_name": "Nexvault Technologies Pvt Ltd", "cancelled_watermark": True},
                "gst_cert":         {"status": "done", "gstin": "27AABCN1234C1Z5", "legal_name": "Nexvault Technologies Private Limited", "registration_date": "2024-02-10"},
            },
            "exact_matches": {
                "pan_number":      True,
                "ifsc_code":       True,
                "account_number":  True,
                "gst_number":      True,
                "cin_number":      None,
                "llp_number":      None,
                "msme_number":     None,
                "iso_cert_number": None,
                "ocr_gstin_state_matches_form_state":   True,
                "ocr_gstin_pan_matches_form_pan":        True,
                "ocr_pan_4th_char_matches_company_type": True,
            },
        },
    },

    # ── 2. PAN number mismatch — card shows different PAN ────────────────────────
    {
        "id": "tc_02_pan_mismatch",
        "description": "PAN on uploaded card doesn't match form. Vendor possibly uploaded wrong card.",
        "input": {
            "today": TODAY,
            "form": {
                "company_name": "Brightwave Solutions LLP",
                "company_type": "LLP",
                "pan_number": "AABFB5678F",
                "state": "Karnataka",
                "gst_registered": False,
                "incorporation_date": "2019-06-15",
                "annual_turnover": "<1 Cr",
                "employee_count": 12,
                "account_holder_name": "Brightwave Solutions LLP",
                "bank_name": "ICICI Bank",
                "account_number": "123400056789",
                "ifsc_code": "ICIC0001234",
                "iso_certified": False,
                "soc2_audited": False,
                "processes_data": False,
                "data_in_india": True,
                "cyber_insurance": False,
                "llp_number": "AAB-1234",
                "service_nature": "HR/ERP Software",
                "contact_email": "ceo@brightwave.in",
            },
            "ocr": {
                "pan_card":         {"status": "done", "pan_number": "AABFX9999F", "name_on_card": "BRIGHTWAVE SOLUTIONS LLP"},
                "cancelled_cheque": {"status": "done", "ifsc_code": "ICIC0001234", "account_number": "123400056789", "account_holder_name": "Brightwave Solutions LLP", "cancelled_watermark": True},
                "llp_agreement":    {"status": "done", "llp_number": "AAB-1234", "company_name": "Brightwave Solutions LLP"},
            },
            "exact_matches": {
                "pan_number":      False,
                "ifsc_code":       True,
                "account_number":  True,
                "gst_number":      None,
                "cin_number":      None,
                "llp_number":      True,
                "msme_number":     None,
                "iso_cert_number": None,
                "ocr_gstin_state_matches_form_state":   None,
                "ocr_gstin_pan_matches_form_pan":        None,
                "ocr_pan_4th_char_matches_company_type": True,
            },
        },
    },

    # ── 3. Partial OCR on GST cert — gstin field missing ─────────────────────────
    {
        "id": "tc_03_partial_ocr_gst",
        "description": "GST cert OCR succeeded but gstin field is null. Possible obscured stamp over GSTIN.",
        "input": {
            "today": TODAY,
            "form": {
                "company_name": "Infrastack Cloud Pvt Ltd",
                "company_type": "Private Limited",
                "pan_number": "AABCI4321C",
                "state": "Delhi",
                "gst_registered": True,
                "gst_number": "07AABCI4321C1Z3",
                "incorporation_date": "2017-09-01",
                "annual_turnover": "10-100 Cr",
                "employee_count": 180,
                "account_holder_name": "Infrastack Cloud Private Limited",
                "bank_name": "SBI",
                "account_number": "987654321012",
                "ifsc_code": "SBIN0001234",
                "cin_number": "U72900DL2017PTC123456",
                "iso_certified": True,
                "iso_cert_number": "ISO-2023-DL-00512",
                "iso_expiry_date": "2026-08-31",
                "soc2_audited": True,
                "processes_data": True,
                "data_in_india": True,
                "cyber_insurance": True,
                "cyber_coverage_crores": 10.0,
                "service_nature": "Cloud Infrastructure",
                "contact_email": "compliance@infrastack.io",
            },
            "ocr": {
                "pan_card":         {"status": "done", "pan_number": "AABCI4321C", "name_on_card": "INFRASTACK CLOUD PVT LTD"},
                "cancelled_cheque": {"status": "done", "ifsc_code": "SBIN0001234", "account_number": "987654321012", "account_holder_name": "Infrastack Cloud Private Limited", "cancelled_watermark": True},
                "gst_cert":         {"status": "done", "gstin": None, "legal_name": "Infrastack Cloud Private Limited", "registration_date": "2017-09-01"},
                "incorporation":    {"status": "done", "cin_number": "U72900DL2017PTC123456", "company_name": "Infrastack Cloud Pvt Ltd", "incorporation_date": "2017-09-01"},
                "iso_cert":         {"status": "done", "cert_number": "ISO-2023-DL-00512", "company_name": "Infrastack Cloud Pvt Ltd", "expiry_date": "2026-08-31", "standard_text": "ISO/IEC 27001"},
                "dpa":              {"status": "done", "company_name": "Infrastack Cloud Pvt Ltd", "is_signed": True, "signing_date": TODAY},
            },
            "exact_matches": {
                "pan_number":      True,
                "ifsc_code":       True,
                "account_number":  True,
                "gst_number":      "partial",
                "cin_number":      True,
                "llp_number":      None,
                "msme_number":     None,
                "iso_cert_number": True,
                "ocr_gstin_state_matches_form_state":   "partial",
                "ocr_gstin_pan_matches_form_pan":        "partial",
                "ocr_pan_4th_char_matches_company_type": True,
            },
        },
    },

    # ── 4. Whole doc failed + wrong entity GST cert ───────────────────────────────
    {
        "id": "tc_04_failed_doc_wrong_gst_entity",
        "description": "Incorporation cert OCR completely failed. GST cert belongs to different entity (PAN mismatch inside GSTIN).",
        "input": {
            "today": TODAY,
            "form": {
                "company_name": "Quantedge Fintech Private Limited",
                "company_type": "Private Limited",
                "pan_number": "AABCQ7890C",
                "state": "Gujarat",
                "gst_registered": True,
                "gst_number": "24AABCQ7890C1Z1",
                "incorporation_date": "2016-03-22",
                "cin_number": "U65900GJ2016PTC654321",
                "annual_turnover": "10-100 Cr",
                "employee_count": 95,
                "account_holder_name": "Quantedge Fintech Pvt Ltd",
                "bank_name": "Axis Bank",
                "account_number": "918010012345",
                "ifsc_code": "UTIB0001234",
                "iso_certified": False,
                "soc2_audited": False,
                "processes_data": True,
                "data_in_india": True,
                "cyber_insurance": True,
                "cyber_coverage_crores": 5.0,
                "service_nature": "Core Banking Software",
                "contact_email": "ops@quantedge.in",
            },
            "ocr": {
                "pan_card":         {"status": "done", "pan_number": "AABCQ7890C", "name_on_card": "QUANTEDGE FINTECH PVT LTD"},
                "cancelled_cheque": {"status": "done", "ifsc_code": "UTIB0001234", "account_number": "918010012345", "account_holder_name": "Quantedge Fintech Pvt Ltd", "cancelled_watermark": True},
                "gst_cert":         {"status": "done", "gstin": "24AABCX1111C1Z9", "legal_name": "Quantedge Fintech Private Limited", "registration_date": "2016-03-22"},
                "incorporation":    {"status": "failed"},
                "dpa":              {"status": "done", "company_name": "Quantedge Fintech Pvt Ltd", "is_signed": True, "signing_date": TODAY},
            },
            "exact_matches": {
                "pan_number":      True,
                "ifsc_code":       True,
                "account_number":  True,
                "gst_number":      False,
                "cin_number":      None,
                "llp_number":      None,
                "msme_number":     None,
                "iso_cert_number": None,
                "ocr_gstin_state_matches_form_state":   True,
                "ocr_gstin_pan_matches_form_pan":        False,
                "ocr_pan_4th_char_matches_company_type": True,
            },
        },
    },

    # ── 5. High risk profile — offshore data, no ISO, low insurance, high employees ─
    {
        "id": "tc_05_high_risk_profile",
        "description": "All docs match but vendor is high risk: data offshore, processes data with no ISO/SOC2, 400 employees on <1Cr turnover, very low cyber coverage.",
        "input": {
            "today": TODAY,
            "form": {
                "company_name": "Datavault Systems Private Limited",
                "company_type": "Private Limited",
                "pan_number": "AABCD2222C",
                "state": "Tamil Nadu",
                "gst_registered": True,
                "gst_number": "33AABCD2222C1Z7",
                "incorporation_date": "2020-11-05",
                "cin_number": "U72200TN2020PTC999888",
                "annual_turnover": "<1 Cr",
                "employee_count": 400,
                "account_holder_name": "Datavault Systems Pvt Ltd",
                "bank_name": "HDFC Bank",
                "account_number": "112233445566",
                "ifsc_code": "HDFC0005678",
                "iso_certified": False,
                "soc2_audited": False,
                "processes_data": True,
                "data_in_india": False,
                "cloud_provider": "AWS",
                "cyber_insurance": True,
                "cyber_coverage_crores": 0.5,
                "service_nature": "Data Analytics",
                "contact_email": "cto@datavault.io",
            },
            "ocr": {
                "pan_card":         {"status": "done", "pan_number": "AABCD2222C", "name_on_card": "DATAVAULT SYSTEMS PVT LTD"},
                "cancelled_cheque": {"status": "done", "ifsc_code": "HDFC0005678", "account_number": "112233445566", "account_holder_name": "Datavault Systems Pvt Ltd", "cancelled_watermark": True},
                "gst_cert":         {"status": "done", "gstin": "33AABCD2222C1Z7", "legal_name": "Datavault Systems Private Limited", "registration_date": "2020-11-05"},
                "incorporation":    {"status": "done", "cin_number": "U72200TN2020PTC999888", "company_name": "Datavault Systems Private Limited", "incorporation_date": "2020-11-05"},
                "dpa":              {"status": "done", "company_name": "Datavault Systems Pvt Ltd", "is_signed": True, "signing_date": TODAY},
            },
            "exact_matches": {
                "pan_number":      True,
                "ifsc_code":       True,
                "account_number":  True,
                "gst_number":      True,
                "cin_number":      True,
                "llp_number":      None,
                "msme_number":     None,
                "iso_cert_number": None,
                "ocr_gstin_state_matches_form_state":   True,
                "ocr_gstin_pan_matches_form_pan":        True,
                "ocr_pan_4th_char_matches_company_type": True,
            },
        },
    },

    # ── 6. DPA unsigned + ISO expired + fuzzy name mismatch on cheque ─────────────
    {
        "id": "tc_06_dpa_unsigned_iso_expired_name_mismatch",
        "description": "DPA not signed, ISO cert expired 8 months ago, account holder name clearly different from company name.",
        "input": {
            "today": TODAY,
            "form": {
                "company_name": "Silverline IT Solutions Private Limited",
                "company_type": "Private Limited",
                "pan_number": "AABCS3456C",
                "state": "Telangana",
                "gst_registered": True,
                "gst_number": "36AABCS3456C1Z2",
                "incorporation_date": "2015-07-19",
                "cin_number": "U72200TG2015PTC111222",
                "annual_turnover": "1-10 Cr",
                "employee_count": 60,
                "account_holder_name": "Silverline IT Solutions Pvt Ltd",
                "bank_name": "Kotak Bank",
                "account_number": "9876001234567",
                "ifsc_code": "KKBK0001234",
                "iso_certified": True,
                "iso_cert_number": "ISO-2022-HYD-00301",
                "iso_expiry_date": "2025-09-30",
                "soc2_audited": False,
                "processes_data": True,
                "data_in_india": True,
                "cyber_insurance": True,
                "cyber_coverage_crores": 3.0,
                "service_nature": "Cybersecurity Tool",
                "contact_email": "security@silverlineit.in",
            },
            "ocr": {
                "pan_card":         {"status": "done", "pan_number": "AABCS3456C", "name_on_card": "SILVERLINE IT SOLUTIONS PVT LTD"},
                "cancelled_cheque": {"status": "done", "ifsc_code": "KKBK0001234", "account_number": "9876001234567", "account_holder_name": "Rajesh Kumar Mehta", "cancelled_watermark": True},
                "gst_cert":         {"status": "done", "gstin": "36AABCS3456C1Z2", "legal_name": "Silverline IT Solutions Private Limited", "registration_date": "2015-07-19"},
                "incorporation":    {"status": "done", "cin_number": "U72200TG2015PTC111222", "company_name": "Silverline IT Solutions Pvt Ltd", "incorporation_date": "2015-07-19"},
                "iso_cert":         {"status": "done", "cert_number": "ISO-2022-HYD-00301", "company_name": "Silverline IT Solutions Pvt Ltd", "expiry_date": "2025-09-30", "standard_text": "ISO/IEC 27001"},
                "dpa":              {"status": "done", "company_name": "Silverline IT Solutions Pvt Ltd", "is_signed": False, "signing_date": None},
            },
            "exact_matches": {
                "pan_number":      True,
                "ifsc_code":       True,
                "account_number":  True,
                "gst_number":      True,
                "cin_number":      True,
                "llp_number":      None,
                "msme_number":     None,
                "iso_cert_number": True,
                "ocr_gstin_state_matches_form_state":   True,
                "ocr_gstin_pan_matches_form_pan":        True,
                "ocr_pan_4th_char_matches_company_type": True,
            },
        },
    },

    # ── 7. Multiple partial reads across docs — fraud signal ──────────────────────
    {
        "id": "tc_07_multiple_partial_reads",
        "description": "Three docs return partial OCR — pan_number, cin_number, and msme_number fields all missing despite docs being 'done'. Strong fraud signal.",
        "input": {
            "today": TODAY,
            "form": {
                "company_name": "Orion Micro Enterprises",
                "company_type": "Private Limited",
                "pan_number": "AABCO6677C",
                "state": "West Bengal",
                "gst_registered": True,
                "gst_number": "19AABCO6677C1Z4",
                "incorporation_date": "2018-04-11",
                "cin_number": "U74900WB2018PTC777888",
                "msme_number": "UDYAM-WB-19-0005678",
                "annual_turnover": "<1 Cr",
                "employee_count": 18,
                "account_holder_name": "Orion Micro Enterprises Pvt Ltd",
                "bank_name": "PNB",
                "account_number": "3456789012345",
                "ifsc_code": "PUNB0001234",
                "iso_certified": False,
                "soc2_audited": False,
                "processes_data": False,
                "data_in_india": True,
                "cyber_insurance": False,
                "service_nature": "Network/Hardware",
                "contact_email": "orders@orionmicro.in",
            },
            "ocr": {
                "pan_card":         {"status": "done", "pan_number": None, "name_on_card": "ORION MICRO ENTERPRISES PVT LTD"},
                "cancelled_cheque": {"status": "done", "ifsc_code": "PUNB0001234", "account_number": "3456789012345", "account_holder_name": "Orion Micro Enterprises Pvt Ltd", "cancelled_watermark": True},
                "gst_cert":         {"status": "done", "gstin": "19AABCO6677C1Z4", "legal_name": "Orion Micro Enterprises", "registration_date": "2018-04-11"},
                "incorporation":    {"status": "done", "cin_number": None, "company_name": "Orion Micro Enterprises Pvt Ltd", "incorporation_date": "2018-04-11"},
                "msme_cert":        {"status": "done", "udyam_number": None, "enterprise_name": "Orion Micro Enterprises", "category": "Micro"},
            },
            "exact_matches": {
                "pan_number":      "partial",
                "ifsc_code":       True,
                "account_number":  True,
                "gst_number":      True,
                "cin_number":      "partial",
                "llp_number":      None,
                "msme_number":     "partial",
                "iso_cert_number": None,
                "ocr_gstin_state_matches_form_state":   True,
                "ocr_gstin_pan_matches_form_pan":        True,
                "ocr_pan_4th_char_matches_company_type": None,
            },
        },
    },

]


def run_tests():
    results = []
    total_prompt_tokens = 0
    total_completion_tokens = 0

    for tc in TEST_CASES:
        print(f"Running {tc['id']} — {tc['description']}")
        try:
            form = dict(tc["input"]["form"])
            # pre-compute age for test cases that still have incorporation_date
            if "incorporation_date" in form and "company_age_years" not in form:
                form["company_age_years"] = _compute_company_age_years(form.pop("incorporation_date"))
            ocr  = tc["input"]["ocr"]
            exact_matches = tc["input"]["exact_matches"]
            output = _call_llm(form, ocr, exact_matches)
            status = "ok"
            error = None
        except Exception as e:
            output = {}
            status = "error"
            error = str(e)
            print(f"  ERROR: {e}")

        results.append({
            "id":          tc["id"],
            "description": tc["description"],
            "status":      status,
            "error":       error,
            "input":       tc["input"],
            "output":      output,
        })
        print(f"  → {status}")

    out_path = os.path.join(os.path.dirname(__file__), "ai_test_output.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    run_tests()
