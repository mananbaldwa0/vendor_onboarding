from generators.company import generate_company
from generators.legal import generate_legal, generate_msme, STATE_ABBR
from generators.banking import generate_banking
from generators.compliance import generate_compliance
from generators.contact import generate_contact
from scenarios.base import assemble_vendor


def generate(output_base: str = "output/docs") -> dict:
    # Force MSME-eligible params
    company = generate_company()
    company["employee_count"] = 45
    company["annual_turnover"] = "1-10 Cr"

    legal = generate_legal(company)
    # Force MSME number
    legal["msme_number"] = generate_msme(company["state"])
    legal["_meta"]["pan"] = legal["pan_number"]

    banking = generate_banking(company)
    compliance = generate_compliance()
    contact = generate_contact(company)
    payload = assemble_vendor(company, legal, banking, compliance, contact, output_base=output_base)
    payload["scenario"] = "valid_with_msme"
    payload["expected_result"] = {"status": "submitted", "errors": []}
    return payload
