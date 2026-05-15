from scenarios.base import build_valid


def generate(output_base: str = "output/docs") -> dict:
    payload = build_valid(output_base=output_base)
    payload["form_data"]["employee_count"] = 999999
    payload["scenario"] = "edge_max_employees"
    payload["expected_result"] = {"status": "submitted", "errors": []}
    return payload
