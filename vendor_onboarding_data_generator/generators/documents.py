import os
import random
from pathlib import Path
from datetime import date

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def _ensure_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)


def _make_pdf(output_path: str, lines: list[str]):
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab not installed. Run: pip install reportlab")
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    y = height - 3 * cm
    c.setFont("Helvetica-Bold", 18)
    for i, line in enumerate(lines):
        if i == 0:
            c.setFont("Helvetica-Bold", 18)
        else:
            c.setFont("Helvetica", 14)
        c.drawString(2 * cm, y, line)
        y -= 1.2 * cm
        if y < 3 * cm:
            c.showPage()
            y = height - 3 * cm

    # Draw a grid of tiny rectangles with varying grey shades — incompressible, pushes file > 10KB
    import random as _r
    c.showPage()
    grid_x, grid_y = 1 * cm, 1 * cm
    cell = 0.18 * cm
    cols = int((width - 2 * cm) / cell)
    rows = int((height - 2 * cm) / cell)
    for row in range(rows):
        for col in range(cols):
            shade = 0.97 + _r.uniform(-0.02, 0.02)
            c.setFillColorRGB(shade, shade, shade)
            c.rect(
                grid_x + col * cell,
                grid_y + row * cell,
                cell - 0.01,
                cell - 0.01,
                fill=1,
                stroke=0,
            )

    c.save()


def _make_jpg(output_path: str, lines: list[str]):
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow not installed. Run: pip install Pillow")
    img = Image.new("RGB", (800, 500), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font_large = ImageFont.truetype("/Library/Fonts/Arial.ttf", 36)
        font_normal = ImageFont.truetype("/Library/Fonts/Arial.ttf", 28)
    except Exception:
        font_large = ImageFont.load_default()
        font_normal = ImageFont.load_default()

    y = 40
    for i, line in enumerate(lines):
        font = font_large if i == 0 else font_normal
        draw.text((40, y), line, fill=(30, 30, 30), font=font)
        y += 60
    img.save(output_path, "JPEG", quality=90)


def generate_pan_card(vendor_dir: str, pan_number: str, company_name: str) -> str:
    path = os.path.join(vendor_dir, "pan_card.jpg")
    lines = [
        "INCOME TAX DEPARTMENT",
        "PERMANENT ACCOUNT NUMBER CARD",
        f"PAN: {pan_number}",
        f"Name: {company_name}",
        "Government of India",
    ]
    _make_jpg(path, lines)
    return path


def generate_gst_cert(vendor_dir: str, gst_number: str, company_name: str) -> str:
    path = os.path.join(vendor_dir, "gst_cert.pdf")
    lines = [
        "GOODS AND SERVICES TAX REGISTRATION CERTIFICATE",
        f"GSTIN: {gst_number}",
        f"Legal Name of Business: {company_name}",
        "Registration Type: Regular",
        "Issued by: GST Council of India",
    ]
    _make_pdf(path, lines)
    return path


def generate_incorporation_cert(vendor_dir: str, cin_number: str, company_name: str, incorporation_date: str) -> str:
    path = os.path.join(vendor_dir, "incorporation.pdf")
    lines = [
        "CERTIFICATE OF INCORPORATION",
        f"Corporate Identification Number (CIN): {cin_number}",
        f"Company Name: {company_name}",
        f"Date of Incorporation: {incorporation_date}",
        "Issued by: Ministry of Corporate Affairs, Government of India",
    ]
    _make_pdf(path, lines)
    return path


def generate_llp_agreement(vendor_dir: str, llp_number: str, company_name: str) -> str:
    path = os.path.join(vendor_dir, "llp_agreement.pdf")
    lines = [
        "LIMITED LIABILITY PARTNERSHIP AGREEMENT",
        f"LLP Identification Number: {llp_number}",
        f"Name of LLP: {company_name}",
        "Registered under the Limited Liability Partnership Act, 2008",
        "Ministry of Corporate Affairs",
    ]
    _make_pdf(path, lines)
    return path


def generate_partnership_deed(vendor_dir: str, company_name: str, incorporation_date: str) -> str:
    path = os.path.join(vendor_dir, "partnership_deed.pdf")
    lines = [
        "PARTNERSHIP DEED",
        f"Firm Name: {company_name}",
        f"Date of Partnership: {incorporation_date}",
        "Registered under the Indian Partnership Act, 1932",
        "This deed constitutes a valid partnership firm.",
    ]
    _make_pdf(path, lines)
    return path


def generate_cancelled_cheque(vendor_dir: str, ifsc_code: str, account_number: str, bank_name: str) -> str:
    path = os.path.join(vendor_dir, "cancelled_cheque.jpg")
    lines = [
        "CANCELLED",
        bank_name,
        f"IFSC: {ifsc_code}",
        f"A/C No: {account_number}",
        "Pay _______________",
    ]
    _make_jpg(path, lines)
    return path


def generate_iso_cert(vendor_dir: str, cert_number: str, company_name: str, expiry_date: str) -> str:
    path = os.path.join(vendor_dir, "iso_cert.pdf")
    lines = [
        "ISO/IEC 27001 CERTIFICATE",
        f"Certificate Number: {cert_number}",
        f"Awarded to: {company_name}",
        f"Expiry Date: {expiry_date}",
        "Information Security Management System",
        "Certified by: Bureau Veritas Certification",
    ]
    _make_pdf(path, lines)
    return path


def generate_dpa(vendor_dir: str, company_name: str) -> str:
    path = os.path.join(vendor_dir, "dpa.pdf")
    lines = [
        "DATA PROCESSING AGREEMENT",
        f"Data Processor: {company_name}",
        f"Date: {date.today().isoformat()}",
        "This Data Processing Agreement governs the processing",
        "of personal data under applicable data protection laws.",
        "GDPR / PDPB compliant data processing terms apply.",
    ]
    _make_pdf(path, lines)
    return path


def generate_msme_cert(vendor_dir: str, msme_number: str, company_name: str) -> str:
    path = os.path.join(vendor_dir, "msme_cert.pdf")
    lines = [
        "UDYAM REGISTRATION CERTIFICATE",
        f"Udyam Registration Number: {msme_number}",
        f"Name of Enterprise: {company_name}",
        "Ministry of Micro, Small and Medium Enterprises",
        "Government of India",
    ]
    _make_pdf(path, lines)
    return path


def generate_all_documents(
    vendor_id: str,
    output_base: str,
    form_data: dict,
    legal_data: dict,
    banking_data: dict,
    compliance_data: dict,
) -> list[dict]:
    vendor_dir = os.path.join(output_base, vendor_id)
    _ensure_dir(vendor_dir)

    docs = []
    company_name = form_data["company_name"]
    company_type = form_data["company_type"]
    incorporation_date = form_data["incorporation_date"]

    # Always required
    pan_path = generate_pan_card(vendor_dir, legal_data["pan_number"], company_name)
    docs.append({"doc_type": "pan_card", "file_path": pan_path})

    cheque_path = generate_cancelled_cheque(
        vendor_dir,
        banking_data["ifsc_code"],
        banking_data["account_number"],
        banking_data["bank_name"],
    )
    docs.append({"doc_type": "cancelled_cheque", "file_path": cheque_path})

    # GST cert
    if legal_data.get("gst_registered") and legal_data.get("gst_number"):
        gst_path = generate_gst_cert(vendor_dir, legal_data["gst_number"], company_name)
        docs.append({"doc_type": "gst_cert", "file_path": gst_path})

    # Company type docs
    if company_type in ("Private Limited", "Public Limited"):
        inc_path = generate_incorporation_cert(
            vendor_dir, legal_data["cin_number"], company_name, incorporation_date
        )
        docs.append({"doc_type": "incorporation", "file_path": inc_path})
    elif company_type == "LLP":
        llp_path = generate_llp_agreement(vendor_dir, legal_data["llp_number"], company_name)
        docs.append({"doc_type": "llp_agreement", "file_path": llp_path})
    elif company_type == "Partnership Firm":
        deed_path = generate_partnership_deed(vendor_dir, company_name, incorporation_date)
        docs.append({"doc_type": "partnership_deed", "file_path": deed_path})

    # ISO cert
    if compliance_data.get("iso_certified") and compliance_data.get("iso_cert_number"):
        iso_path = generate_iso_cert(
            vendor_dir,
            compliance_data["iso_cert_number"],
            company_name,
            compliance_data["iso_expiry_date"],
        )
        docs.append({"doc_type": "iso_cert", "file_path": iso_path})

    # DPA
    if compliance_data.get("processes_data"):
        dpa_path = generate_dpa(vendor_dir, company_name)
        docs.append({"doc_type": "dpa", "file_path": dpa_path})

    # MSME cert
    if legal_data.get("msme_number"):
        msme_path = generate_msme_cert(vendor_dir, legal_data["msme_number"], company_name)
        docs.append({"doc_type": "msme_cert", "file_path": msme_path})

    return docs
