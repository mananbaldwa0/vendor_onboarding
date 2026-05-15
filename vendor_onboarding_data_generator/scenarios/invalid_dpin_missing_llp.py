from scenarios.base import build_valid


def generate(output_base: str = "output/docs") -> dict:
    payload = build_valid(company_type="LLP", output_base=output_base)
    payload["form_data"].pop("dpin", None)
    payload["scenario"] = "invalid_dpin_missing_llp"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["DPIN is required for LLP company type"],
    }
    return payload
