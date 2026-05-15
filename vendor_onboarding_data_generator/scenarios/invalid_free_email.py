from generators.company import generate_company
from generators.legal import generate_legal
from generators.banking import generate_banking
from generators.compliance import generate_compliance
from generators.contact import generate_contact
from scenarios.base import assemble_vendor


def generate(output_base: str = "output/docs") -> dict:
    company = generate_company()
    legal = generate_legal(company)
    banking = generate_banking(company)
    compliance = generate_compliance()
    contact = generate_contact(company, force_free_email=True)
    payload = assemble_vendor(company, legal, banking, compliance, contact, output_base=output_base)
    payload["scenario"] = "invalid_free_email"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["Contact email must use a corporate domain, not a free email provider"],
    }
    return payload
