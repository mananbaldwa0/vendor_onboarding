# Validation Rules — Rule-Based Checks Only
> No AI. No OCR. Pure format + logic checks.
> AI-based checks are Phase 3 — noted where applicable.

---

## Group 1 — Company Identity

| Field | Rule | Error Message |
|---|---|---|
| `company_name` | Required. Min 3 chars. | "Company name is required" |
| `company_type` | Required. Must be one of: `Private Limited`, `Public Limited`, `LLP`, `Partnership Firm`, `Sole Proprietorship` | "Invalid company type" |
| `incorporation_date` | Required. Must be past date. Must not be before 1900-01-01. | "Incorporation date must be a past date" |
| `registered_address` | Required. Min 10 chars. | "Enter full registered address" |
| `city` | Required. Min 2 chars. | "City is required" |
| `state` | Required. Must be from allowed Indian states list. | "Select a valid Indian state" |
| `employee_count` | Required. Integer ≥ 1. | "Employee count must be at least 1" |
| `annual_turnover` | Required. One of: `<1 Cr`, `1-10 Cr`, `10-100 Cr`, `>100 Cr` | "Select a valid turnover range" |
| `website` | Optional. If provided, must match `^https?://[^\s]+\.[^\s]+$` | "Enter a valid website URL" |

---

## Group 2 — PAN

| Field | Rule | Error Message |
|---|---|---|
| `pan_number` | Required. Regex: `^[A-Z]{5}[0-9]{4}[A-Z]{1}$` | "Invalid PAN format (e.g. ABCDE1234F)" |
| `pan_number` 4th char | Cross-check with `company_type`: C=Company (Pvt/Public Ltd), F=Firm (LLP/Partnership), P=Individual (Sole Prop) | "PAN 4th character does not match company type" |

---

## Group 3 — GST

| Field | Rule | Error Message |
|---|---|---|
| `gst_registered` | Required boolean. | "Specify if GST registered" |
| `gst_number` | Required if `gst_registered = true`. Regex: `^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$` | "Invalid GST number format" |
| `gst_number` state code | `gst_number[0:2]` must match state code of `state` field. See state code map below. | "GST state code does not match selected state" |
| `gst_number` PAN embed | `gst_number[2:12]` must equal `pan_number`. | "PAN embedded in GST does not match PAN field" |

### State Code Map (GST)
```
Andhra Pradesh=37, Arunachal Pradesh=12, Assam=18, Bihar=10, Chhattisgarh=22,
Goa=30, Gujarat=24, Haryana=06, Himachal Pradesh=02, Jharkhand=20,
Karnataka=29, Kerala=32, Madhya Pradesh=23, Maharashtra=27, Manipur=14,
Meghalaya=17, Mizoram=15, Nagaland=13, Odisha=21, Punjab=03,
Rajasthan=08, Sikkim=11, Tamil Nadu=33, Telangana=36, Tripura=16,
Uttar Pradesh=09, Uttarakhand=05, West Bengal=19, Delhi=07,
Jammu & Kashmir=01, Ladakh=38, Puducherry=34, Chandigarh=04,
Andaman & Nicobar=35, Dadra & Nagar Haveli=26, Daman & Diu=25, Lakshadweep=31
```

---

## Group 4 — Director / Company IDs

| Field | Rule | Error Message |
|---|---|---|
| `signatory_name` | Required. Min 3 chars. | "Signatory name is required" |
| `din` | Required if `company_type` in `[Private Limited, Public Limited]`. Regex: `^[0-9]{8}$` | "DIN must be exactly 8 digits" |
| `cin_number` | Required if `company_type` in `[Private Limited, Public Limited]`. Regex: `^[UL][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$` | "Invalid CIN format (e.g. U72900MH2015PTC123456)" |
| `cin_number` year | `cin_number[8:12]` must match year in `incorporation_date`. | "CIN year does not match incorporation year" |
| `dpin` | Required if `company_type = LLP`. Regex: `^[0-9]{8}$` | "DPIN must be exactly 8 digits" |
| `llp_number` | Required if `company_type = LLP`. Regex: `^[A-Z]{3}-[0-9]{4}$` | "Invalid LLP number format (e.g. AAA-1234)" |
| `msme_number` | Optional. If provided, regex: `^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$` | "Invalid MSME number format (e.g. UDYAM-MH-00-0000000)" |
| `msme_number` limits | If `msme_number` provided: `employee_count` ≤ 250 AND `annual_turnover` in `[<1 Cr, 1-10 Cr]` | "Employee count or turnover exceeds MSME limits" |

---

## Group 5 — Banking

| Field | Rule | Error Message |
|---|---|---|
| `account_holder_name` | Required. Min 3 chars. | "Account holder name is required" |
| `bank_name` | Required. Min 3 chars. | "Bank name is required" |
| `account_number` | Required. Regex: `^[0-9]{9,18}$` | "Account number must be 9–18 digits, numeric only" |
| `ifsc_code` | Required. Regex: `^[A-Z]{4}0[A-Z0-9]{6}$` (5th char always 0) | "Invalid IFSC format (e.g. HDFC0001234)" |
| `account_type` | Required. One of: `Current`, `Savings` | "Select account type" |

---

## Group 6 — ISO

| Field | Rule | Error Message |
|---|---|---|
| `iso_certified` | Required boolean. | "Specify ISO certification status" |
| `iso_cert_number` | Required if `iso_certified = true`. Min 3 chars. | "ISO certificate number is required" |
| `iso_expiry_date` | Required if `iso_certified = true`. Must be a **future** date. | "ISO certificate is expired — expiry date must be in the future" |
| `soc2_audited` | Optional boolean. No validation needed. | — |

---

## Group 7 — Data & Compliance

| Field | Rule | Error Message |
|---|---|---|
| `service_nature` | Required. One of: `Core Banking Software`, `Cybersecurity Tool`, `Cloud Infrastructure`, `SaaS Platform`, `Data Analytics`, `HR/ERP Software`, `Network/Hardware`, `Other` | "Select nature of IT service" |
| `processes_data` | Required boolean. | "Specify if service processes bank/customer data" |
| `data_in_india` | Required boolean. If `false` → flag for RBI review (not a hard block, just a warning flag). | "Data stored outside India — flagged for RBI compliance review" |
| `cloud_provider` | Required. One of: `AWS`, `Azure`, `GCP`, `Private Cloud`, `On-Premise`, `Hybrid`, `Not Applicable` | "Select cloud provider" |
| `cyber_insurance` | Required if `processes_data = true`. | "Cyber insurance is mandatory when service processes customer data" |
| `cyber_coverage_crores` | Required if `cyber_insurance = true`. Must be numeric > 0. | "Enter cyber insurance coverage amount" |

---

## Group 8 — Contact

| Field | Rule | Error Message |
|---|---|---|
| `contact_name` | Required. Min 3 chars. | "Contact name is required" |
| `contact_email` | Required. Valid email format. Domain must NOT be in: `gmail.com, yahoo.com, hotmail.com, outlook.com, rediffmail.com, yahoo.in, ymail.com` | "Use official company email — free email domains not allowed" |
| `contact_phone` | Required. Regex: `^\+[0-9]{1,3}[0-9]{7,12}$` | "Phone must include country code (e.g. +919876543210)" |

---

## Documents — Required Per Submission

| Document `doc_type` | Required When | Notes |
|---|---|---|
| `pan_card` | Always | — |
| `gst_cert` | `gst_registered = true` | — |
| `incorporation` | `company_type` in `[Private Limited, Public Limited]` | — |
| `llp_agreement` | `company_type = LLP` | — |
| `partnership_deed` | `company_type = Partnership Firm` | — |
| `cancelled_cheque` | Always | — |
| `iso_cert` | `iso_certified = true` | — |
| `dpa` | `processes_data = true` | — |
| `msme_cert` | `msme_number` provided | — |

**Document check:** verify that required `doc_type` rows exist in `documents` table for this `vendor_id` before marking submission valid.
> **Known limitation:** docs are scoped by `vendor_id` only, not `application_id`. All docs ever uploaded by vendor are visible. Phase 2 will tighten this.

---

## Cross-Field Summary

| Check | Fields Involved |
|---|---|
| PAN 4th char vs company type | `pan_number`, `company_type` |
| GST state code vs state | `gst_number`, `state` |
| GST embedded PAN vs PAN | `gst_number`, `pan_number` |
| CIN year vs incorporation year | `cin_number`, `incorporation_date` |
| Cyber insurance required if data processing | `processes_data`, `cyber_insurance` |
| ISO fields required if ISO certified | `iso_certified`, `iso_cert_number`, `iso_expiry_date` |
| MSME number format + limits | `msme_number`, `employee_count`, `annual_turnover` |
| DIN/CIN required for Pvt/Public Ltd | `company_type`, `din`, `cin_number` |
| DPIN/LLP required for LLP | `company_type`, `dpin`, `llp_number` |
| Required docs present | `documents` table vs form field values |

---

## What AI Will Add Later (Phase 3)

- Company name vs bank account name fuzzy match
- Email domain vs company website match
- Employee count vs turnover coherence
- Service type vs data processing flag coherence
- ISO age vs company age coherence
- Cyber coverage adequacy for service risk level
- Document type verification (is the uploaded file actually a PAN card?)
