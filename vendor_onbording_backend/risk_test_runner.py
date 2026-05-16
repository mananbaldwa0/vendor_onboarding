"""
Risk scoring test runner.
Tests _base_score, _cross_version_delta, _decision, _compute_notified_factors
with mock data — no Supabase needed.

Run: python risk_test_runner.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()
from services.ai_service import (
    _base_score, _cross_version_delta, _decision,
    _compute_notified_factors, build_reasoning_input, _call_reasoning_llm,
)

TEST_CASES = [

    # tc_01 — v1 only, truly clean, zero user_flags
    {
        "id": "tc_01_clean",
        "description": "v1 only. One low flag, zero user_flags. Expect: approved.",
        "versions": [
            {
                "version": 1,
                "risk_factors": [
                    {"factor": "new_company", "severity": "low", "note": "Company < 2 years old."},
                ],
                "user_flags": [],
            }
        ],
    },

    # tc_02 — v1 heavy, user_flags present (vendor notified)
    {
        "id": "tc_02_heavy_with_user_flags",
        "description": "v1 only. Heavy flags, user_flags present. Expect: waiting_for_response.",
        "versions": [
            {
                "version": 1,
                "risk_factors": [
                    {"factor": "data_offshore",              "severity": "high",   "note": "Data outside India."},
                    {"factor": "employee_turnover_mismatch", "severity": "high",   "note": "400 employees <1Cr."},
                    {"factor": "processes_data_no_soc2",     "severity": "medium", "note": "No SOC2."},
                    {"factor": "iso_cert_expired",           "severity": "high",   "note": "ISO expired."},
                    {"factor": "partial_ocr_pan_card",       "severity": "medium", "note": "PAN partial OCR."},
                    {"factor": "new_company",                "severity": "low",    "note": "New company."},
                ],
                "user_flags": [
                    {"field": "iso_cert",   "severity": "high",   "message": "ISO cert expired. Please renew."},
                    {"field": "pan_number", "severity": "medium", "message": "PAN card could not be fully read."},
                ],
            }
        ],
    },

    # tc_03 — v1 heavy internal-only flags, zero user_flags
    {
        "id": "tc_03_internal_risks_no_user_flags",
        "description": "v1 only. Medium/high internal flags but zero user_flags. Expect: human_review (not waiting_for_response).",
        "versions": [
            {
                "version": 1,
                "risk_factors": [
                    {"factor": "data_offshore",          "severity": "high",   "note": "Data outside India."},
                    {"factor": "processes_data_no_soc2", "severity": "medium", "note": "No SOC2."},
                    {"factor": "low_cyber_coverage",     "severity": "medium", "note": "Low cyber coverage."},
                ],
                "user_flags": [],
            }
        ],
    },

    # tc_04 — v1 notified flags, v2 same flags repeated (escalation)
    {
        "id": "tc_04_escalation",
        "description": "v1 had notified flags. v2 same flags still present. Expect: score escalates vs base.",
        "versions": [
            {
                "version": 1,
                "risk_factors": [
                    {"factor": "iso_cert_expired",     "severity": "high",   "note": "ISO expired."},
                    {"factor": "partial_ocr_pan_card", "severity": "medium", "note": "PAN partial OCR."},
                    {"factor": "data_offshore",        "severity": "high",   "note": "Offshore data."},
                ],
                "user_flags": [
                    {"field": "iso_cert",   "severity": "high",   "message": "ISO cert expired."},
                    {"field": "pan_number", "severity": "medium", "message": "PAN card partial read."},
                ],
            },
            {
                "version": 2,
                "risk_factors": [
                    {"factor": "iso_cert_expired",     "severity": "high",   "note": "Still expired."},
                    {"factor": "partial_ocr_pan_card", "severity": "medium", "note": "Still partial."},
                    {"factor": "data_offshore",        "severity": "high",   "note": "Still offshore."},
                ],
                "user_flags": [
                    {"field": "iso_cert",   "severity": "high",   "message": "ISO cert still expired."},
                    {"field": "pan_number", "severity": "medium", "message": "PAN card still partial."},
                ],
            },
        ],
    },

    # tc_05 — v1 heavy → v2 vendor fixed notified flags, internal ones remain
    {
        "id": "tc_05_resolution",
        "description": "v1 notified flags resolved in v2. Internal flags remain. Expect: score drops.",
        "versions": [
            {
                "version": 1,
                "risk_factors": [
                    {"factor": "iso_cert_expired",     "severity": "high",   "note": "ISO expired."},
                    {"factor": "partial_ocr_pan_card", "severity": "medium", "note": "PAN partial."},
                    {"factor": "data_offshore",        "severity": "high",   "note": "Offshore data."},
                    {"factor": "processes_data_no_soc2","severity": "medium", "note": "No SOC2."},
                ],
                "user_flags": [
                    {"field": "iso_cert",   "severity": "high",   "message": "ISO cert expired."},
                    {"field": "pan_number", "severity": "medium", "message": "PAN partial read."},
                ],
            },
            {
                "version": 2,
                "risk_factors": [
                    {"factor": "data_offshore",         "severity": "high",   "note": "Still offshore."},
                    {"factor": "processes_data_no_soc2","severity": "medium", "note": "Still no SOC2."},
                ],
                "user_flags": [],
            },
        ],
    },

]


def run():
    results = []

    for tc in TEST_CASES:
        versions = tc["versions"]
        curr = versions[-1]
        prior = versions[:-1]

        curr_factors = curr["risk_factors"]
        curr_flags   = curr["user_flags"]

        # Build prior_reviews with notified_factors computed from their user_flags
        prior_reviews = []
        for v in prior:
            nf = _compute_notified_factors(v["risk_factors"], v["user_flags"])
            prior_reviews.append({
                "version":          v["version"],
                "risk_factors":     v["risk_factors"],
                "notified_factors": nf,
            })

        notified = _compute_notified_factors(curr_factors, curr_flags)
        base     = _base_score(curr_factors)
        delta    = _cross_version_delta(prior_reviews, curr_factors)
        final    = max(0, min(100, base + delta))
        decision = _decision(final, curr_flags)
        all_reviews_for_reasoning = [
            {
                "version":          v["version"],
                "risk_factors":     v["risk_factors"],
                "notified_factors": _compute_notified_factors(v["risk_factors"], v["user_flags"]),
                "risk_score":       None,
                "decision":         None,
            }
            for v in versions[:-1]
        ] + [{
            "version":          curr["version"],
            "risk_factors":     curr_factors,
            "notified_factors": notified,
            "risk_score":       final,
            "decision":         decision,
        }]
        reasoning_input = build_reasoning_input("vendor_test", all_reviews_for_reasoning)

        print(f"\n=== {tc['id']} ===")
        print(f"  {tc['description']}")
        print(f"  base={base}  delta={delta:+d}  final={final}  decision={decision}")
        print(f"  notified_factors={notified}")
        print(f"  Calling reasoning LLM...")

        try:
            reasoning = _call_reasoning_llm(reasoning_input)
        except Exception as e:
            reasoning = f"ERROR: {e}"

        print(f"  REASONING: {reasoning}")

        result = {
            "id":                   tc["id"],
            "description":          tc["description"],
            "base_score":           base,
            "cross_version_delta":  delta,
            "final_score":          final,
            "decision":             decision,
            "notified_factors":     notified,
            "reasoning_input":      reasoning_input,
            "risk_reasoning":       reasoning,
        }
        results.append(result)

    out_path = os.path.join(os.path.dirname(__file__), "risk_test_output.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {out_path}")
    return results


if __name__ == "__main__":
    run()
