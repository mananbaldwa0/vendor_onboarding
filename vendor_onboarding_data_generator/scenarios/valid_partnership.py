from scenarios.base import build_valid


def generate(output_base: str = "output/docs") -> dict:
    payload = build_valid(company_type="Partnership Firm", output_base=output_base)
    payload["scenario"] = "valid_partnership"
    payload["expected_result"] = {"status": "submitted", "errors": []}
    return payload
