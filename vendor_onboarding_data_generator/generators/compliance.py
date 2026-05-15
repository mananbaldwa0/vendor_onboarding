import random
import string
from datetime import date, timedelta

SERVICE_NATURES = [
    "Core Banking Software",
    "Cybersecurity Tool",
    "Cloud Infrastructure",
    "SaaS Platform",
    "Data Analytics",
    "HR/ERP Software",
    "Network/Hardware",
    "Other",
]

CLOUD_PROVIDERS = ["AWS", "Azure", "GCP", "Private Cloud", "On-Premise", "Hybrid", "Not Applicable"]


def _future_date(min_days: int = 180, max_days: int = 1095) -> str:
    delta = timedelta(days=random.randint(min_days, max_days))
    return (date.today() + delta).isoformat()


def _past_date(min_days: int = 30, max_days: int = 365) -> str:
    delta = timedelta(days=random.randint(min_days, max_days))
    return (date.today() - delta).isoformat()


def generate_iso_cert_number() -> str:
    year = random.randint(2020, 2024)
    state = "".join(random.choices(string.ascii_uppercase, k=2))
    serial = str(random.randint(10000, 99999))
    return f"IS-{year}-{state}-{serial}"


def generate_compliance(force_processes_data: bool = None, force_data_offshore: bool = False) -> dict:
    service_nature = random.choice(SERVICE_NATURES)

    if force_processes_data is None:
        processes_data = random.choice([True, False])
    else:
        processes_data = force_processes_data

    data_in_india = not force_data_offshore if not force_data_offshore else False
    if not force_data_offshore:
        data_in_india = random.choices([True, False], weights=[85, 15])[0]

    cloud_provider = random.choice(CLOUD_PROVIDERS)

    iso_certified = random.choice([True, False])
    iso_cert_number = None
    iso_expiry_date = None
    if iso_certified:
        iso_cert_number = generate_iso_cert_number()
        iso_expiry_date = _future_date()

    soc2_audited = random.choice([True, False])

    cyber_insurance = True if processes_data else random.choice([True, False])
    cyber_coverage_crores = None
    if cyber_insurance:
        cyber_coverage_crores = round(random.uniform(1.0, 50.0), 1)

    result = {
        "service_nature": service_nature,
        "processes_data": processes_data,
        "data_in_india": data_in_india,
        "cloud_provider": cloud_provider,
        "iso_certified": iso_certified,
        "soc2_audited": soc2_audited,
    }
    if iso_certified:
        result["iso_cert_number"] = iso_cert_number
        result["iso_expiry_date"] = iso_expiry_date
    if processes_data:
        result["cyber_insurance"] = cyber_insurance
        if cyber_insurance:
            result["cyber_coverage_crores"] = cyber_coverage_crores

    return result


def generate_compliance_expired_iso() -> dict:
    data = generate_compliance(force_processes_data=False)
    data["iso_certified"] = True
    data["iso_cert_number"] = generate_iso_cert_number()
    data["iso_expiry_date"] = _past_date()
    return data


def generate_compliance_no_cyber() -> dict:
    data = generate_compliance(force_processes_data=True)
    data["cyber_insurance"] = False
    data.pop("cyber_coverage_crores", None)
    return data
