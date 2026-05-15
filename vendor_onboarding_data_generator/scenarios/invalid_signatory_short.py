from scenarios.base import build_valid


def generate(output_base: str = "output/docs") -> dict:
    payload = build_valid(output_base=output_base)
    payload["form_data"]["signatory_name"] = "AB"  # less than 3 chars
    payload["scenario"] = "invalid_signatory_short"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["Signatory name must be at least 3 characters"],
    }
    return payload
