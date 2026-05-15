from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
import uuid


class LoginRequest(BaseModel):
    email: str


class LoginResponse(BaseModel):
    token: str
    vendor_id: str


class ApplicationSubmit(BaseModel):
    # Group 1: Company Identity
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    incorporation_date: Optional[date] = None
    registered_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    employee_count: Optional[int] = None
    annual_turnover: Optional[str] = None
    website: Optional[str] = None

    # Group 2: PAN
    pan_number: Optional[str] = None

    # Group 3: GST
    gst_registered: Optional[bool] = None
    gst_number: Optional[str] = None

    # Group 4: Director / Company IDs
    signatory_name: Optional[str] = None
    din: Optional[str] = None
    dpin: Optional[str] = None
    cin_number: Optional[str] = None
    llp_number: Optional[str] = None
    msme_number: Optional[str] = None

    # Group 5: Banking
    account_holder_name: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    account_type: Optional[str] = None

    # Group 6: ISO
    iso_certified: Optional[bool] = None
    iso_cert_number: Optional[str] = None
    iso_expiry_date: Optional[date] = None
    soc2_audited: Optional[bool] = None

    # Group 7: Data & Compliance
    service_nature: Optional[str] = None
    processes_data: Optional[bool] = None
    data_in_india: Optional[bool] = None
    cloud_provider: Optional[str] = None
    cyber_insurance: Optional[bool] = None
    cyber_coverage_crores: Optional[float] = None

    # Group 8: Contact
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class ApplicationResponse(BaseModel):
    application_id: str
    status: str
    version: int
    errors: list[str] = []


class StatusResponse(BaseModel):
    application_id: Optional[str] = None
    status: Optional[str] = None
    submitted_at: Optional[datetime] = None
    version: Optional[int] = None
    application: Optional[dict] = None


class DocumentResponse(BaseModel):
    doc_id: str
    file_url: str
    doc_type: str
