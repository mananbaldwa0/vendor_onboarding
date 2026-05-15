import random
from faker import Faker
from datetime import date, timedelta

fake = Faker("en_IN")

COMPANY_TYPES = [
    "Private Limited",
    "Public Limited",
    "LLP",
    "Partnership Firm",
    "Sole Proprietorship",
]

STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]

ANNUAL_TURNOVER_OPTIONS = ["<1 Cr", "1-10 Cr", "10-100 Cr", ">100 Cr"]

COMPANY_SUFFIXES = {
    "Private Limited": ["Private Limited", "Pvt. Ltd.", "Pvt Ltd"],
    "Public Limited": ["Limited", "Ltd."],
    "LLP": ["LLP", "Limited Liability Partnership"],
    "Partnership Firm": ["& Associates", "& Partners", "and Company"],
    "Sole Proprietorship": [],
}

TECH_WORDS = [
    "Syntara", "Nexgen", "Infovant", "Cloudrise", "Datavex", "Techspark",
    "Algoriv", "Softbridge", "Pinnacle", "Coretec", "Axiom", "Vyom",
    "Sarvam", "Primus", "Celero", "Infranet", "Quantix", "Zaplink",
]


def generate_company(company_type: str = None, state: str = None) -> dict:
    if company_type is None:
        company_type = random.choice(COMPANY_TYPES)
    if state is None:
        state = random.choice(STATES)

    base_name = random.choice(TECH_WORDS) + " " + random.choice(
        ["Technologies", "Solutions", "Systems", "Infotech", "Innovations", "Analytics", "Ventures"]
    )
    suffix_list = COMPANY_SUFFIXES[company_type]
    suffix = random.choice(suffix_list) if suffix_list else ""
    company_name = f"{base_name} {suffix}".strip() if suffix else base_name

    start = date(1990, 1, 1)
    end = date.today() - timedelta(days=365)
    incorporation_date = start + timedelta(days=random.randint(0, (end - start).days))

    employee_count = random.randint(1, 500)
    annual_turnover = random.choice(ANNUAL_TURNOVER_OPTIONS)

    domain = base_name.lower().replace(" ", "") + ".io"
    has_website = random.random() > 0.15
    website = f"https://{domain}" if has_website else None

    signatory_name = fake.name()

    return {
        "company_name": company_name,
        "company_type": company_type,
        "incorporation_date": incorporation_date.isoformat(),
        "registered_address": fake.street_address(),
        "city": fake.city(),
        "state": state,
        "employee_count": employee_count,
        "annual_turnover": annual_turnover,
        "website": website,
        "signatory_name": signatory_name,
        "_meta": {
            "base_name": base_name,
            "domain": domain,
            "incorporation_year": incorporation_date.year,
        },
    }
