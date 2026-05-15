import random
import string

BANKS = [
    ("HDFC Bank", "HDFC"),
    ("State Bank of India", "SBIN"),
    ("ICICI Bank", "ICIC"),
    ("Axis Bank", "UTIB"),
    ("Kotak Mahindra Bank", "KKBK"),
    ("Punjab National Bank", "PUNB"),
    ("Bank of Baroda", "BARB"),
    ("Canara Bank", "CNRB"),
    ("IndusInd Bank", "INDB"),
    ("Yes Bank", "YESB"),
    ("IDFC First Bank", "IDFB"),
    ("Federal Bank", "FDRL"),
]

ACCOUNT_TYPES = ["Current", "Savings"]


def _fuzzy_shorten(company_name: str) -> str:
    replacements = {
        "Private Limited": "Pvt Ltd",
        "Pvt. Ltd.": "Pvt Ltd",
        "Public Limited": "Ltd",
        "Limited Liability Partnership": "LLP",
        "Technologies": "Tech",
        "Solutions": "Sol",
        "Innovations": "Innov",
        "Analytics": "Analytics",
    }
    result = company_name
    for k, v in replacements.items():
        result = result.replace(k, v)
    return result.strip()


def generate_banking(company_data: dict) -> dict:
    bank_name, bank_code = random.choice(BANKS)
    account_type = random.choice(ACCOUNT_TYPES)

    account_length = random.randint(9, 18)
    account_number = "".join(random.choices(string.digits, k=account_length))

    branch_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    ifsc_code = f"{bank_code}0{branch_code}"

    account_holder_name = _fuzzy_shorten(company_data["company_name"])

    return {
        "account_holder_name": account_holder_name,
        "bank_name": bank_name,
        "account_number": account_number,
        "ifsc_code": ifsc_code,
        "account_type": account_type,
    }
