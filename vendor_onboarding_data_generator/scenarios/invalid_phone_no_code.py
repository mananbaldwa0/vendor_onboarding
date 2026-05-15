from scenarios.base import build_valid


def generate(output_base: str = "output/docs") -> dict:
    payload = build_valid(output_base=output_base)
    # Strip the +91 country code
    phone = payload["form_data"]["contact_phone"]
    if phone.startswith("+91"):
        payload["form_data"]["contact_phone"] = phone[3:]
    payload["scenario"] = "invalid_phone_no_code"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["Contact phone must include country code (e.g. +91)"],
    }
    return payload
