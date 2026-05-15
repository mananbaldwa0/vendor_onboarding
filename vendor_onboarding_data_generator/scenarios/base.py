import copy
import uuid
from generators.company import generate_company
from generators.legal import generate_legal
from generators.banking import generate_banking
from generators.compliance import generate_compliance
from generators.contact import generate_contact
from generators.documents import generate_all_documents


def assemble_vendor(
    company_data: dict,
    legal_data: dict,
    banking_data: dict,
    compliance_data: dict,
    contact_data: dict,
    output_base: str = "output/docs",
    vendor_id: str = None,
) -> dict:
    if vendor_id is None:
        vendor_id = f"vendor_{uuid.uuid4().hex[:8]}"

    form_data = {}
    for d in (company_data, legal_data, banking_data, compliance_data, contact_data):
        for k, v in d.items():
            if not k.startswith("_"):
                form_data[k] = v

    docs = generate_all_documents(
        vendor_id=vendor_id,
        output_base=output_base,
        form_data=form_data,
        legal_data=legal_data,
        banking_data=banking_data,
        compliance_data=compliance_data,
    )

    return {
        "vendor_id": vendor_id,
        "form_data": form_data,
        "documents": docs,
    }


def build_valid(company_type: str = None, state: str = None, output_base: str = "output/docs") -> dict:
    company = generate_company(company_type=company_type, state=state)
    legal = generate_legal(company)
    banking = generate_banking(company)
    compliance = generate_compliance()
    contact = generate_contact(company)
    return assemble_vendor(company, legal, banking, compliance, contact, output_base=output_base)
