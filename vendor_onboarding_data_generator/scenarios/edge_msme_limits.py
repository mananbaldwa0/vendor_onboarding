from generators.company import generate_company
from generators.legal import generate_legal, generate_msme
from generators.banking import generate_banking
from generators.compliance import generate_compliance
from generators.contact import generate_contact
from scenarios.base import assemble_vendor


def generate(output_base: str = "output/docs") -> dict:
    company = generate_company()
    # Over MSME limit: employee count > 250
    company["employee_count"] = 300
    company["annual_turnover"] = "10-100 Cr"

    legal = generate_legal(company)
    # Force MSME number despite being ineligible
    legal["msme_number"] = generate_msme(company["state"])

    banking = generate_banking(company)
    compliance = generate_compliance()
    contact = generate_contact(company)
    payload = assemble_vendor(company, legal, banking, compliance, contact, output_base=output_base)
    payload["scenario"] = "edge_msme_limits"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["Company exceeds MSME limits for registered MSME number"],
    }
    return payload
