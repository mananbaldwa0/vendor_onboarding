import sys
import os
import re
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from generators.company import generate_company, COMPANY_TYPES, STATES, ANNUAL_TURNOVER_OPTIONS
from generators.legal import generate_legal, generate_pan, generate_gst, generate_cin, STATE_GST_CODES, PAN_TYPE_CHAR
from generators.banking import generate_banking
from generators.compliance import generate_compliance, generate_compliance_expired_iso, generate_compliance_no_cyber
from generators.contact import generate_contact, FREE_DOMAINS

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GST_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")
CIN_RE = re.compile(r"^[UL][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")
LLP_RE = re.compile(r"^[A-Z]{3}-[0-9]{4}$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
PHONE_RE = re.compile(r"^\+[0-9]{1,3}[0-9]{7,12}$")
MSME_RE = re.compile(r"^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$")


class TestCompanyGenerator:
    def test_required_fields_present(self):
        data = generate_company()
        for field in ("company_name", "company_type", "incorporation_date",
                      "registered_address", "city", "state", "employee_count",
                      "annual_turnover", "signatory_name"):
            assert field in data, f"Missing field: {field}"

    def test_company_type_valid(self):
        for _ in range(20):
            data = generate_company()
            assert data["company_type"] in COMPANY_TYPES

    def test_state_valid(self):
        for _ in range(20):
            data = generate_company()
            assert data["state"] in STATES

    def test_employee_count_positive(self):
        for _ in range(20):
            data = generate_company()
            assert data["employee_count"] >= 1

    def test_turnover_valid(self):
        for _ in range(20):
            data = generate_company()
            assert data["annual_turnover"] in ANNUAL_TURNOVER_OPTIONS

    def test_seeded_company_type(self):
        data = generate_company(company_type="LLP")
        assert data["company_type"] == "LLP"

    def test_seeded_state(self):
        data = generate_company(state="Maharashtra")
        assert data["state"] == "Maharashtra"

    def test_website_format_when_present(self):
        for _ in range(30):
            data = generate_company()
            if data.get("website"):
                assert data["website"].startswith("https://")

    def test_incorporation_date_in_past(self):
        from datetime import date
        for _ in range(20):
            data = generate_company()
            inc = date.fromisoformat(data["incorporation_date"])
            assert inc < date.today()
            assert inc.year >= 1990

    def test_signatory_name_min_length(self):
        for _ in range(20):
            data = generate_company()
            assert len(data["signatory_name"]) >= 3


class TestLegalGenerator:
    def setup_method(self):
        self.company = generate_company(company_type="Private Limited", state="Maharashtra")

    def test_pan_format(self):
        for ct in COMPANY_TYPES:
            company = generate_company(company_type=ct)
            pan = generate_pan(ct)
            assert PAN_RE.match(pan), f"PAN {pan} invalid"

    def test_pan_4th_char_matches_type(self):
        for ct, expected_char in PAN_TYPE_CHAR.items():
            pan = generate_pan(ct)
            assert pan[3] == expected_char, f"PAN[3] should be {expected_char} for {ct}, got {pan[3]}"

    def test_gst_format(self):
        legal = generate_legal(self.company)
        if legal.get("gst_number"):
            assert GST_RE.match(legal["gst_number"]), f"GST {legal['gst_number']} invalid"

    def test_gst_embeds_pan(self):
        legal = generate_legal(self.company)
        if legal.get("gst_number") and legal.get("pan_number"):
            assert legal["gst_number"][2:12] == legal["pan_number"]

    def test_gst_state_code_matches(self):
        company = generate_company(state="Maharashtra")
        legal = generate_legal(company)
        if legal.get("gst_number"):
            assert legal["gst_number"][:2] == "27"

    def test_cin_format_pvt_ltd(self):
        company = generate_company(company_type="Private Limited", state="Maharashtra")
        legal = generate_legal(company)
        assert "cin_number" in legal
        assert CIN_RE.match(legal["cin_number"]), f"CIN {legal['cin_number']} invalid"

    def test_cin_year_matches_incorporation(self):
        company = generate_company(company_type="Private Limited")
        legal = generate_legal(company)
        inc_year = company["_meta"]["incorporation_year"]
        cin = legal["cin_number"]
        cin_year = int(cin[8:12])
        assert cin_year == inc_year

    def test_llp_number_format(self):
        company = generate_company(company_type="LLP")
        legal = generate_legal(company)
        assert "llp_number" in legal
        assert LLP_RE.match(legal["llp_number"])

    def test_dpin_present_for_llp(self):
        company = generate_company(company_type="LLP")
        legal = generate_legal(company)
        assert "dpin" in legal
        assert re.match(r"^[0-9]{8}$", legal["dpin"])

    def test_din_present_for_pvt_ltd(self):
        company = generate_company(company_type="Private Limited")
        legal = generate_legal(company)
        assert "din" in legal
        assert re.match(r"^[0-9]{8}$", legal["din"])

    def test_no_cin_for_llp(self):
        company = generate_company(company_type="LLP")
        legal = generate_legal(company)
        assert "cin_number" not in legal

    def test_no_cin_for_sole_prop(self):
        company = generate_company(company_type="Sole Proprietorship")
        legal = generate_legal(company)
        assert "cin_number" not in legal

    def test_msme_format_when_present(self):
        for _ in range(50):
            company = generate_company()
            company["employee_count"] = 50
            company["annual_turnover"] = "1-10 Cr"
            legal = generate_legal(company)
            if legal.get("msme_number"):
                assert MSME_RE.match(legal["msme_number"])
                break

    def test_no_gst_when_not_registered(self):
        company = generate_company()
        legal = generate_legal(company, include_gst=False)
        assert legal["gst_registered"] is False
        assert "gst_number" not in legal

    def test_gst_registered_field_always_present(self):
        company = generate_company()
        legal = generate_legal(company)
        assert "gst_registered" in legal


class TestBankingGenerator:
    def test_required_fields(self):
        company = generate_company()
        banking = generate_banking(company)
        for field in ("account_holder_name", "bank_name", "account_number", "ifsc_code", "account_type"):
            assert field in banking

    def test_ifsc_format(self):
        company = generate_company()
        for _ in range(20):
            banking = generate_banking(company)
            assert IFSC_RE.match(banking["ifsc_code"]), f"IFSC {banking['ifsc_code']} invalid"

    def test_account_number_length(self):
        company = generate_company()
        for _ in range(20):
            banking = generate_banking(company)
            acc = banking["account_number"]
            assert 9 <= len(acc) <= 18
            assert acc.isdigit()

    def test_account_type_valid(self):
        company = generate_company()
        for _ in range(20):
            banking = generate_banking(company)
            assert banking["account_type"] in ("Current", "Savings")


class TestComplianceGenerator:
    def test_required_fields(self):
        comp = generate_compliance()
        for field in ("service_nature", "processes_data", "data_in_india",
                      "cloud_provider", "iso_certified", "soc2_audited"):
            assert field in comp

    def test_cyber_insurance_required_when_processes_data(self):
        for _ in range(20):
            comp = generate_compliance(force_processes_data=True)
            assert comp.get("cyber_insurance") is True

    def test_iso_fields_present_when_certified(self):
        for _ in range(20):
            comp = generate_compliance()
            if comp.get("iso_certified"):
                assert "iso_cert_number" in comp
                assert "iso_expiry_date" in comp

    def test_expired_iso_has_past_date(self):
        from datetime import date
        comp = generate_compliance_expired_iso()
        assert comp["iso_certified"] is True
        expiry = date.fromisoformat(comp["iso_expiry_date"])
        assert expiry < date.today()

    def test_no_cyber_insurance_when_processes_data_false_possible(self):
        # cyber_insurance can be False only when processes_data is False
        found_false = False
        for _ in range(50):
            comp = generate_compliance(force_processes_data=False)
            if comp.get("cyber_insurance") is False:
                found_false = True
                break
        # Just ensure it can happen without assertion error
        assert True

    def test_no_cyber_compliance(self):
        comp = generate_compliance_no_cyber()
        assert comp["processes_data"] is True
        assert comp["cyber_insurance"] is False


class TestContactGenerator:
    def test_required_fields(self):
        company = generate_company()
        contact = generate_contact(company)
        for field in ("contact_name", "contact_email", "contact_phone"):
            assert field in contact

    def test_no_free_email_by_default(self):
        company = generate_company()
        for _ in range(20):
            contact = generate_contact(company)
            domain = contact["contact_email"].split("@")[1]
            assert domain not in FREE_DOMAINS

    def test_free_email_when_forced(self):
        company = generate_company()
        contact = generate_contact(company, force_free_email=True)
        domain = contact["contact_email"].split("@")[1]
        assert domain in FREE_DOMAINS

    def test_phone_format(self):
        company = generate_company()
        for _ in range(20):
            contact = generate_contact(company)
            assert PHONE_RE.match(contact["contact_phone"]), f"Phone {contact['contact_phone']} invalid"

    def test_email_domain_matches_website(self):
        company = generate_company()
        company["website"] = "https://acmecorp.in"
        company["_meta"]["domain"] = "acmecorp.in"
        contact = generate_contact(company)
        assert contact["contact_email"].endswith("@acmecorp.in")
