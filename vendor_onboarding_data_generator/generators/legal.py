import random
import string

STATE_GST_CODES = {
    "Andhra Pradesh": "37", "Arunachal Pradesh": "12", "Assam": "18",
    "Bihar": "10", "Chhattisgarh": "22", "Goa": "30", "Gujarat": "24",
    "Haryana": "06", "Himachal Pradesh": "02", "Jharkhand": "20",
    "Karnataka": "29", "Kerala": "32", "Madhya Pradesh": "23",
    "Maharashtra": "27", "Manipur": "14", "Meghalaya": "17",
    "Mizoram": "15", "Nagaland": "13", "Odisha": "21", "Punjab": "03",
    "Rajasthan": "08", "Sikkim": "11", "Tamil Nadu": "33",
    "Telangana": "36", "Tripura": "16", "Uttar Pradesh": "09",
    "Uttarakhand": "05", "West Bengal": "19",
    "Andaman and Nicobar Islands": "35", "Chandigarh": "04",
    "Dadra and Nagar Haveli and Daman and Diu": "26", "Delhi": "07",
    "Jammu and Kashmir": "01", "Ladakh": "38", "Lakshadweep": "31",
    "Puducherry": "34",
}

PAN_TYPE_CHAR = {
    "Private Limited": "C",
    "Public Limited": "C",
    "LLP": "F",
    "Partnership Firm": "F",
    "Sole Proprietorship": "P",
}

NIC_CODES = ["72900", "62010", "63110", "64200", "65910", "66190", "74100", "74900"]

STATE_ABBR = {
    "Andhra Pradesh": "AP", "Arunachal Pradesh": "AR", "Assam": "AS",
    "Bihar": "BR", "Chhattisgarh": "CG", "Goa": "GA", "Gujarat": "GJ",
    "Haryana": "HR", "Himachal Pradesh": "HP", "Jharkhand": "JH",
    "Karnataka": "KA", "Kerala": "KL", "Madhya Pradesh": "MP",
    "Maharashtra": "MH", "Manipur": "MN", "Meghalaya": "ML",
    "Mizoram": "MZ", "Nagaland": "NL", "Odisha": "OD", "Punjab": "PB",
    "Rajasthan": "RJ", "Sikkim": "SK", "Tamil Nadu": "TN",
    "Telangana": "TS", "Tripura": "TR", "Uttar Pradesh": "UP",
    "Uttarakhand": "UK", "West Bengal": "WB",
    "Andaman and Nicobar Islands": "AN", "Chandigarh": "CH",
    "Dadra and Nagar Haveli and Daman and Diu": "DN", "Delhi": "DL",
    "Jammu and Kashmir": "JK", "Ladakh": "LA", "Lakshadweep": "LD",
    "Puducherry": "PY",
}

MSME_ELIGIBLE_TURNOVER = ["<1 Cr", "1-10 Cr", "10-100 Cr", ">100 Cr"]  # all buckets valid — Medium MSME up to 250 Cr


def _rand_upper(n: int) -> str:
    return "".join(random.choices(string.ascii_uppercase, k=n))


def _rand_digits(n: int) -> str:
    return "".join(random.choices(string.digits, k=n))


def generate_pan(company_type: str) -> str:
    type_char = PAN_TYPE_CHAR[company_type]
    # Format: [A-Z]{5}[0-9]{4}[A-Z]  with 4th char = type_char
    part1 = _rand_upper(3)
    part2 = type_char
    part3 = _rand_upper(1)
    digits = _rand_digits(4)
    last = _rand_upper(1)
    return f"{part1}{part2}{part3}{digits}{last}"


def generate_gst(pan: str, state: str) -> str:
    state_code = STATE_GST_CODES.get(state, "27")
    entity_no = str(random.randint(1, 9))
    check_digit = random.choice(string.digits + string.ascii_uppercase[:6])
    return f"{state_code}{pan}{entity_no}Z{check_digit}"


def generate_cin(state: str, incorporation_year: int, company_type: str) -> str:
    listing = random.choice(["U", "L"])
    nic = random.choice(NIC_CODES)
    state_abbr = STATE_ABBR.get(state, "MH")
    suffix = "PTC" if company_type == "Private Limited" else "PLC"
    serial = _rand_digits(6)
    return f"{listing}{nic}{state_abbr}{incorporation_year}{suffix}{serial}"


def generate_llp_number() -> str:
    return f"{_rand_upper(3)}-{_rand_digits(4)}"


def generate_din() -> str:
    return _rand_digits(8)


def generate_dpin() -> str:
    return _rand_digits(8)


def generate_msme(state: str) -> str:
    state_abbr = STATE_ABBR.get(state, "MH")[:2]
    district = _rand_digits(2)
    serial = _rand_digits(7)
    return f"UDYAM-{state_abbr}-{district}-{serial}"


def generate_legal(company_data: dict, include_gst: bool = True) -> dict:
    company_type = company_data["company_type"]
    state = company_data["state"]
    incorporation_year = company_data["_meta"]["incorporation_year"]
    employee_count = company_data["employee_count"]
    annual_turnover = company_data["annual_turnover"]

    pan = generate_pan(company_type)

    gst_registered = include_gst
    gst_number = generate_gst(pan, state) if gst_registered else None

    cin_number = None
    llp_number = None
    dpin = None
    din = None

    if company_type in ("Private Limited", "Public Limited"):
        cin_number = generate_cin(state, incorporation_year, company_type)
        din = generate_din()
    elif company_type == "LLP":
        llp_number = generate_llp_number()
        dpin = generate_dpin()

    msme_eligible = employee_count <= 250
    msme_number = None
    if msme_eligible and random.random() < 0.30:
        msme_number = generate_msme(state)

    result = {
        "pan_number": pan,
        "gst_registered": gst_registered,
    }
    if gst_number:
        result["gst_number"] = gst_number
    if cin_number:
        result["cin_number"] = cin_number
    if din:
        result["din"] = din
    if llp_number:
        result["llp_number"] = llp_number
    if dpin:
        result["dpin"] = dpin
    if msme_number:
        result["msme_number"] = msme_number

    result["_meta"] = {"pan": pan}
    return result
