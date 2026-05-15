from scenarios.base import build_valid


def generate(output_base: str = "output/docs") -> dict:
    payload = build_valid(company_type="LLP", output_base=output_base)
    payload["scenario"] = "valid_llp"
    payload["expected_result"] = {"status": "submitted", "errors": []}
    return payload
