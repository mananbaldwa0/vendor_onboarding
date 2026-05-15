from scenarios.base import build_valid


def generate(output_base: str = "output/docs") -> dict:
    # Use Private Limited but put F (Firm) as 4th PAN char
    payload = build_valid(company_type="Private Limited", output_base=output_base)
    pan = payload["form_data"]["pan_number"]
    # 4th char (index 3) should be C for company; replace with F
    payload["form_data"]["pan_number"] = pan[:3] + "F" + pan[4:]
    payload["scenario"] = "invalid_pan_type_mismatch"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["PAN 4th character does not match company type"],
    }
    return payload
