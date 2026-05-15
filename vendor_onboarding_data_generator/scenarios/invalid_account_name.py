from scenarios.base import build_valid


def generate(output_base: str = "output/docs") -> dict:
    payload = build_valid(output_base=output_base)
    payload["form_data"]["account_holder_name"] = "Random Unrelated Entity Ltd"
    payload["scenario"] = "invalid_account_name"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["Account holder name must closely match the company name"],
    }
    return payload
