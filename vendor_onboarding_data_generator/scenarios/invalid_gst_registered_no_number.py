from scenarios.base import build_valid


def generate(output_base: str = "output/docs") -> dict:
    payload = build_valid(output_base=output_base)
    payload["form_data"]["gst_registered"] = True
    payload["form_data"].pop("gst_number", None)
    # Remove GST cert doc too
    payload["documents"] = [d for d in payload["documents"] if d["doc_type"] != "gst_cert"]
    payload["scenario"] = "invalid_gst_registered_no_number"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["GST number is required when gst_registered is true"],
    }
    return payload
