from scenarios.base import build_valid


def generate(output_base: str = "output/docs") -> dict:
    payload = build_valid(output_base=output_base)
    payload["form_data"]["account_number"] = "12345"  # only 5 digits
    payload["scenario"] = "invalid_short_account"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["Account number must be between 9 and 18 digits"],
    }
    return payload
