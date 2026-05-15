import random
import re
from faker import Faker

fake = Faker("en_IN")

FREE_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "rediffmail.com", "yahoo.in", "ymail.com",
}

INDIAN_FIRST_NAMES = [
    "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Kavya", "Rohan",
    "Anjali", "Arjun", "Deepa", "Sanjay", "Meera", "Rajesh", "Sunita",
    "Kiran", "Pooja", "Nikhil", "Divya", "Arun", "Ritu",
]

INDIAN_LAST_NAMES = [
    "Mehta", "Sharma", "Patel", "Singh", "Kumar", "Joshi", "Gupta",
    "Verma", "Nair", "Iyer", "Reddy", "Rao", "Mishra", "Pandey", "Shah",
]


def _derive_domain(company_data: dict) -> str:
    website = company_data.get("website")
    if website:
        match = re.search(r"https?://([^/]+)", website)
        if match:
            return match.group(1)
    base = company_data["_meta"]["domain"]
    return base


def generate_contact(company_data: dict, force_free_email: bool = False) -> dict:
    first = random.choice(INDIAN_FIRST_NAMES)
    last = random.choice(INDIAN_LAST_NAMES)
    contact_name = f"{first} {last}"

    if force_free_email:
        domain = random.choice(list(FREE_DOMAINS))
    else:
        domain = _derive_domain(company_data)

    email_local = f"{first.lower()}.{last.lower()}"
    contact_email = f"{email_local}@{domain}"

    digits = "".join([str(random.randint(6, 9))] + [str(random.randint(0, 9)) for _ in range(9)])
    contact_phone = f"+91{digits}"

    return {
        "contact_name": contact_name,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
    }
