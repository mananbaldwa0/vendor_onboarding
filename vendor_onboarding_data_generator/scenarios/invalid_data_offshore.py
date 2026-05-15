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
    compliance = generate_compliance(force_data_offshore=True)
    contact = generate_contact(company)
    payload = assemble_vendor(company, legal, banking, compliance, contact, output_base=output_base)
    payload["scenario"] = "invalid_data_offshore"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["Data stored outside India requires RBI approval"],
    }
    return payload
