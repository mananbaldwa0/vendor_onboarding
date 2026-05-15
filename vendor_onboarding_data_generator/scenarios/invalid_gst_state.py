from scenarios.base import build_valid


def generate(output_base: str = "output/docs") -> dict:
    payload = build_valid(output_base=output_base)
    gst = payload["form_data"].get("gst_number", "")
    if gst and len(gst) == 15:
        # Replace state code with wrong one (99 never valid)
        payload["form_data"]["gst_number"] = "99" + gst[2:]
    payload["scenario"] = "invalid_gst_state"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["GST state code does not match selected state"],
    }
    return payload
