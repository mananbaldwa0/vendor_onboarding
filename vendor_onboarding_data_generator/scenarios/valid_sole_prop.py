from scenarios.base import build_valid


def generate(output_base: str = "output/docs") -> dict:
    payload = build_valid(company_type="Sole Proprietorship", output_base=output_base)
    payload["scenario"] = "valid_sole_prop"
    payload["expected_result"] = {"status": "submitted", "errors": []}
    return payload
