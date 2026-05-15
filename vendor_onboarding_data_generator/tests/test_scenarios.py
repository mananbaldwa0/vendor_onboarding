"""
Scenario structure tests — verify every scenario produces a well-formed payload
without hitting the live API.
"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import scenarios.valid_pvt_ltd as valid_pvt_ltd
import scenarios.valid_llp as valid_llp
import scenarios.valid_sole_prop as valid_sole_prop
import scenarios.valid_partnership as valid_partnership
import scenarios.valid_no_gst as valid_no_gst
import scenarios.valid_with_msme as valid_with_msme
import scenarios.invalid_pan_mismatch as invalid_pan_mismatch
import scenarios.invalid_gst_state as invalid_gst_state
import scenarios.invalid_cin_year as invalid_cin_year
import scenarios.invalid_free_email as invalid_free_email
import scenarios.invalid_data_offshore as invalid_data_offshore
import scenarios.invalid_missing_dpa as invalid_missing_dpa
import scenarios.invalid_expired_iso as invalid_expired_iso
import scenarios.invalid_no_cyber_insurance as invalid_no_cyber_insurance
import scenarios.invalid_account_name as invalid_account_name
import scenarios.invalid_short_account as invalid_short_account
import scenarios.invalid_bad_ifsc as invalid_bad_ifsc
import scenarios.invalid_phone_no_code as invalid_phone_no_code
import scenarios.invalid_pan_type_mismatch as invalid_pan_type_mismatch
import scenarios.invalid_gst_registered_no_number as invalid_gst_registered_no_number
import scenarios.invalid_dpin_missing_llp as invalid_dpin_missing_llp
import scenarios.invalid_signatory_short as invalid_signatory_short
import scenarios.edge_msme_limits as edge_msme_limits
import scenarios.edge_iso_expires_today as edge_iso_expires_today
import scenarios.edge_max_employees as edge_max_employees

ALL_MODULES = [
    valid_pvt_ltd, valid_llp, valid_sole_prop, valid_partnership,
    valid_no_gst, valid_with_msme,
    invalid_pan_mismatch, invalid_gst_state, invalid_cin_year,
    invalid_free_email, invalid_data_offshore, invalid_missing_dpa,
    invalid_expired_iso, invalid_no_cyber_insurance, invalid_account_name,
    invalid_short_account, invalid_bad_ifsc, invalid_phone_no_code,
    invalid_pan_type_mismatch, invalid_gst_registered_no_number,
    invalid_dpin_missing_llp, invalid_signatory_short,
    edge_msme_limits, edge_iso_expires_today, edge_max_employees,
]

REQUIRED_FORM_FIELDS = [
    "company_name", "company_type", "incorporation_date", "registered_address",
    "city", "state", "employee_count", "annual_turnover",
    "pan_number", "gst_registered",
    "signatory_name",
    "account_holder_name", "bank_name", "account_number", "ifsc_code", "account_type",
    "service_nature", "processes_data", "data_in_india", "cloud_provider",
    "iso_certified", "soc2_audited",
    "contact_name", "contact_email", "contact_phone",
]


def _generate(mod):
    return mod.generate(output_base="/tmp/test_docs")


class TestPayloadStructure:
    @pytest.mark.parametrize("mod", ALL_MODULES, ids=[m.__name__.split(".")[-1] for m in ALL_MODULES])
    def test_has_vendor_id(self, mod):
        payload = _generate(mod)
        assert "vendor_id" in payload
        assert payload["vendor_id"]

    @pytest.mark.parametrize("mod", ALL_MODULES, ids=[m.__name__.split(".")[-1] for m in ALL_MODULES])
    def test_has_scenario_key(self, mod):
        payload = _generate(mod)
        assert "scenario" in payload

    @pytest.mark.parametrize("mod", ALL_MODULES, ids=[m.__name__.split(".")[-1] for m in ALL_MODULES])
    def test_has_expected_result(self, mod):
        payload = _generate(mod)
        er = payload.get("expected_result", {})
        assert "status" in er
        assert er["status"] in ("submitted", "incomplete")

    @pytest.mark.parametrize("mod", ALL_MODULES, ids=[m.__name__.split(".")[-1] for m in ALL_MODULES])
    def test_has_documents_list(self, mod):
        payload = _generate(mod)
        assert isinstance(payload.get("documents"), list)
        assert len(payload["documents"]) > 0

    @pytest.mark.parametrize("mod", ALL_MODULES, ids=[m.__name__.split(".")[-1] for m in ALL_MODULES])
    def test_form_data_has_core_fields(self, mod):
        payload = _generate(mod)
        fd = payload["form_data"]
        for field in REQUIRED_FORM_FIELDS:
            assert field in fd, f"Scenario {payload.get('scenario')} missing field: {field}"


class TestValidScenarios:
    def test_pvt_ltd_has_cin(self):
        p = _generate(valid_pvt_ltd)
        assert "cin_number" in p["form_data"]
        assert "din" in p["form_data"]

    def test_llp_has_llp_number_and_dpin(self):
        p = _generate(valid_llp)
        assert "llp_number" in p["form_data"]
        assert "dpin" in p["form_data"]

    def test_sole_prop_no_cin(self):
        p = _generate(valid_sole_prop)
        assert "cin_number" not in p["form_data"]
        assert "din" not in p["form_data"]

    def test_partnership_has_partnership_deed(self):
        p = _generate(valid_partnership)
        doc_types = [d["doc_type"] for d in p["documents"]]
        assert "partnership_deed" in doc_types

    def test_no_gst_scenario(self):
        p = _generate(valid_no_gst)
        assert p["form_data"]["gst_registered"] is False
        assert "gst_number" not in p["form_data"]

    def test_msme_scenario_has_msme_cert(self):
        p = _generate(valid_with_msme)
        assert "msme_number" in p["form_data"]
        doc_types = [d["doc_type"] for d in p["documents"]]
        assert "msme_cert" in doc_types


class TestInvalidScenarios:
    def test_pan_mismatch_gst_differs(self):
        p = _generate(invalid_pan_mismatch)
        pan = p["form_data"]["pan_number"]
        gst = p["form_data"].get("gst_number", "")
        if gst:
            assert gst[2:12] != pan

    def test_gst_state_wrong(self):
        p = _generate(invalid_gst_state)
        gst = p["form_data"].get("gst_number", "")
        if gst:
            assert gst[:2] == "99"

    def test_cin_year_wrong(self):
        p = _generate(invalid_cin_year)
        cin = p["form_data"].get("cin_number", "")
        inc_year = p["form_data"]["incorporation_date"][:4]
        if cin:
            cin_year = cin[8:12]
            assert cin_year != inc_year

    def test_free_email(self):
        from generators.contact import FREE_DOMAINS
        p = _generate(invalid_free_email)
        domain = p["form_data"]["contact_email"].split("@")[1]
        assert domain in FREE_DOMAINS

    def test_data_offshore(self):
        p = _generate(invalid_data_offshore)
        assert p["form_data"]["data_in_india"] is False

    def test_missing_dpa_no_doc(self):
        p = _generate(invalid_missing_dpa)
        assert p["form_data"]["processes_data"] is True
        doc_types = [d["doc_type"] for d in p["documents"]]
        assert "dpa" not in doc_types

    def test_expired_iso(self):
        from datetime import date
        p = _generate(invalid_expired_iso)
        expiry = date.fromisoformat(p["form_data"]["iso_expiry_date"])
        assert expiry < date.today()

    def test_no_cyber_insurance(self):
        p = _generate(invalid_no_cyber_insurance)
        assert p["form_data"]["processes_data"] is True
        assert p["form_data"]["cyber_insurance"] is False

    def test_short_account_number(self):
        p = _generate(invalid_short_account)
        assert len(p["form_data"]["account_number"]) < 9

    def test_bad_ifsc_5th_char(self):
        p = _generate(invalid_bad_ifsc)
        ifsc = p["form_data"]["ifsc_code"]
        assert ifsc[4] != "0"

    def test_phone_no_country_code(self):
        p = _generate(invalid_phone_no_code)
        phone = p["form_data"]["contact_phone"]
        assert not phone.startswith("+")

    def test_pan_type_mismatch(self):
        p = _generate(invalid_pan_type_mismatch)
        pan = p["form_data"]["pan_number"]
        assert pan[3] != "C"

    def test_gst_registered_no_number(self):
        p = _generate(invalid_gst_registered_no_number)
        assert p["form_data"]["gst_registered"] is True
        assert "gst_number" not in p["form_data"]

    def test_dpin_missing_for_llp(self):
        p = _generate(invalid_dpin_missing_llp)
        assert p["form_data"]["company_type"] == "LLP"
        assert "dpin" not in p["form_data"]

    def test_signatory_short(self):
        p = _generate(invalid_signatory_short)
        assert len(p["form_data"]["signatory_name"]) < 3


class TestEdgeCases:
    def test_msme_limits_over_ceiling(self):
        p = _generate(edge_msme_limits)
        assert p["form_data"]["employee_count"] > 250
        assert "msme_number" in p["form_data"]

    def test_iso_expires_today(self):
        from datetime import date
        p = _generate(edge_iso_expires_today)
        expiry = date.fromisoformat(p["form_data"]["iso_expiry_date"])
        assert expiry == date.today()

    def test_max_employees(self):
        p = _generate(edge_max_employees)
        assert p["form_data"]["employee_count"] == 999999
