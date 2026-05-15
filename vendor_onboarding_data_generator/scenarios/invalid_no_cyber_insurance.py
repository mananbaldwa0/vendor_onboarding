from generators.company import generate_company
from generators.legal import generate_legal
from generators.banking import generate_banking
from generators.compliance import generate_compliance_no_cyber
from generators.contact import generate_contact
from scenarios.base import assemble_vendor


def generate(output_base: str = "output/docs") -> dict:
    company = generate_company()
    legal = generate_legal(company)
    banking = generate_banking(company)
    compliance = generate_compliance_no_cyber()
    contact = generate_contact(company)
    payload = assemble_vendor(company, legal, banking, compliance, contact, output_base=output_base)
    payload["scenario"] = "invalid_no_cyber_insurance"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["Cyber insurance is required when vendor processes personal data"],
    }
    return payload
