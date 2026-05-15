import random
import string
from scenarios.base import build_valid


def generate(output_base: str = "output/docs") -> dict:
    payload = build_valid(output_base=output_base)
    # Replace chars 3-12 of GST with a different PAN
    gst = payload["form_data"].get("gst_number", "")
    if gst and len(gst) == 15:
        wrong_pan = "ZZZZP9999Z"  # different from real PAN
        payload["form_data"]["gst_number"] = gst[:2] + wrong_pan + gst[12:]
    payload["scenario"] = "invalid_pan_mismatch"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["GST number does not contain the registered PAN"],
    }
    return payload
