from scenarios.base import build_valid


def generate(output_base: str = "output/docs") -> dict:
    payload = build_valid(company_type="Private Limited", output_base=output_base)
    cin = payload["form_data"].get("cin_number", "")
    if cin and len(cin) >= 11:
        # Replace year portion (chars 7-10, 0-indexed) with wrong year
        wrong_year = "1999"
        payload["form_data"]["cin_number"] = cin[:8] + wrong_year + cin[12:]
    payload["scenario"] = "invalid_cin_year"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["CIN year does not match incorporation year"],
    }
    return payload
