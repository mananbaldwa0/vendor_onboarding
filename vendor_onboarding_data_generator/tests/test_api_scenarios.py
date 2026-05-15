"""
Integration tests — POST generated payloads to live API and verify responses.
Run with: pytest tests/test_api_scenarios.py --api-url http://localhost:8000

Skip automatically if API is unreachable.
"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def pytest_addoption(parser):
    parser.addoption("--api-url", default="http://localhost:8000", help="Backend API base URL")


@pytest.fixture(scope="session")
def api_url(request):
    return request.config.getoption("--api-url")


@pytest.fixture(scope="session")
def http_client(api_url):
    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed")
    try:
        client = httpx.Client(base_url=api_url, timeout=30)
        client.get("/health")
        return client
    except Exception:
        pytest.skip(f"API not reachable at {api_url}")


def _post_form(client, form_data: dict):
    resp = client.post("/api/application/submit", json=form_data)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    return resp.status_code, body


import scenarios.valid_pvt_ltd as valid_pvt_ltd
import scenarios.valid_llp as valid_llp
import scenarios.valid_sole_prop as valid_sole_prop
import scenarios.valid_partnership as valid_partnership
import scenarios.valid_no_gst as valid_no_gst
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


class TestValidScenariosAPI:
    def test_valid_pvt_ltd(self, http_client):
        p = valid_pvt_ltd.generate(output_base="/tmp/test_docs")
        status, body = _post_form(http_client, p["form_data"])
        assert status in (200, 201), f"Expected 2xx, got {status}: {body}"

    def test_valid_llp(self, http_client):
        p = valid_llp.generate(output_base="/tmp/test_docs")
        status, body = _post_form(http_client, p["form_data"])
        assert status in (200, 201), f"Expected 2xx, got {status}: {body}"

    def test_valid_sole_prop(self, http_client):
        p = valid_sole_prop.generate(output_base="/tmp/test_docs")
        status, body = _post_form(http_client, p["form_data"])
        assert status in (200, 201), f"Expected 2xx, got {status}: {body}"

    def test_valid_partnership(self, http_client):
        p = valid_partnership.generate(output_base="/tmp/test_docs")
        status, body = _post_form(http_client, p["form_data"])
        assert status in (200, 201), f"Expected 2xx, got {status}: {body}"

    def test_valid_no_gst(self, http_client):
        p = valid_no_gst.generate(output_base="/tmp/test_docs")
        status, body = _post_form(http_client, p["form_data"])
        assert status in (200, 201), f"Expected 2xx, got {status}: {body}"


class TestInvalidScenariosAPI:
    def _assert_error(self, http_client, mod, expected_fragment: str):
        p = mod.generate(output_base="/tmp/test_docs")
        status, body = _post_form(http_client, p["form_data"])
        assert status in (400, 422), f"Expected 4xx for {mod.__name__}, got {status}: {body}"

    def test_invalid_pan_mismatch(self, http_client):
        self._assert_error(http_client, invalid_pan_mismatch, "PAN")

    def test_invalid_gst_state(self, http_client):
        self._assert_error(http_client, invalid_gst_state, "GST")

    def test_invalid_cin_year(self, http_client):
        self._assert_error(http_client, invalid_cin_year, "CIN")

    def test_invalid_free_email(self, http_client):
        self._assert_error(http_client, invalid_free_email, "email")

    def test_invalid_data_offshore(self, http_client):
        self._assert_error(http_client, invalid_data_offshore, "India")

    def test_invalid_missing_dpa(self, http_client):
        self._assert_error(http_client, invalid_missing_dpa, "DPA")

    def test_invalid_expired_iso(self, http_client):
        self._assert_error(http_client, invalid_expired_iso, "ISO")

    def test_invalid_no_cyber_insurance(self, http_client):
        self._assert_error(http_client, invalid_no_cyber_insurance, "cyber")

    def test_invalid_account_name(self, http_client):
        self._assert_error(http_client, invalid_account_name, "account")

    def test_invalid_short_account(self, http_client):
        self._assert_error(http_client, invalid_short_account, "account")

    def test_invalid_bad_ifsc(self, http_client):
        self._assert_error(http_client, invalid_bad_ifsc, "IFSC")

    def test_invalid_phone_no_code(self, http_client):
        self._assert_error(http_client, invalid_phone_no_code, "phone")

    def test_invalid_pan_type_mismatch(self, http_client):
        self._assert_error(http_client, invalid_pan_type_mismatch, "PAN")

    def test_invalid_gst_registered_no_number(self, http_client):
        self._assert_error(http_client, invalid_gst_registered_no_number, "GST")
