from datetime import date
from generators.company import generate_company
from generators.legal import generate_legal
from generators.banking import generate_banking
from generators.compliance import generate_compliance, generate_iso_cert_number
from generators.contact import generate_contact
from scenarios.base import assemble_vendor


def generate(output_base: str = "output/docs") -> dict:
    company = generate_company()
    legal = generate_legal(company)
    banking = generate_banking(company)
    compliance = generate_compliance()
    compliance["iso_certified"] = True
    compliance["iso_cert_number"] = generate_iso_cert_number()
    compliance["iso_expiry_date"] = date.today().isoformat()
    contact = generate_contact(company)
    payload = assemble_vendor(company, legal, banking, compliance, contact, output_base=output_base)
    payload["scenario"] = "edge_iso_expires_today"
    payload["expected_result"] = {
        "status": "incomplete",
        "errors": ["ISO 27001 certificate has expired"],
    }
    return payload
