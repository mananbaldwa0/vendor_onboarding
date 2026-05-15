from scenarios.base import build_valid


def generate(output_base: str = "output/docs") -> dict:
    payload = build_valid(output_base=output_base)
    ifsc = payload["form_data"]["ifsc_code"]
    # Replace 5th char (index 4) with non-zero
    payload["form_data"]["ifsc_code"] = ifsc[:4] + "1" + ifsc[5:]
    payload["scenario"] = "invalid_bad_ifsc"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["IFSC code 5th character must be 0"],
    }
    return payload
