#!/usr/bin/env python3
"""
Runs all 10 final test cases against the live API.
Usage:
  python final_tests/run_tests.py --api-url http://localhost:8000
"""
import sys
import json
import os
import argparse
from pathlib import Path

try:
    import httpx
except ImportError:
    print("httpx not installed. Run: pip install httpx")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    console = Console()
    def info(msg): console.print(msg)
    def success(msg): console.print(f"[green]{msg}[/green]")
    def fail(msg): console.print(f"[red]{msg}[/red]")
    def warn(msg): console.print(f"[yellow]{msg}[/yellow]")
    def cyan(msg): console.print(f"[cyan]{msg}[/cyan]")
except ImportError:
    def info(msg): print(msg)
    def success(msg): print(f"PASS: {msg}")
    def fail(msg): print(f"FAIL: {msg}")
    def warn(msg): print(f"WARN: {msg}")
    def cyan(msg): print(f"INFO: {msg}")

TESTS_DIR = Path(__file__).parent

TEST_EMAILS = {
    "test_01_pass_pvt_ltd":         "test1@gmail.com",
    "test_02_pass_llp_no_gst":      "test2@gmail.com",
    "test_03_pass_partnership_msme":"test3@gmail.com",
    "test_04_fix_cin_year":         "test4@gmail.com",
    "test_05_fix_free_email":       "test5@gmail.com",
    "test_06_fix_missing_dpa":      "test6@gmail.com",
    "test_07_fail_pan_type":        "test7@gmail.com",
    "test_08_fail_data_offshore":   "test8@gmail.com",
    "test_09_fail_no_cyber":        "test9@gmail.com",
    "test_10_phase2_preview":       "test10@gmail.com",
}

# Tests that have round_1 / round_2 (fail then fix)
FIX_TESTS = {
    "test_04_fix_cin_year",
    "test_05_fix_free_email",
    "test_06_fix_missing_dpa",
}

results = []


def login(client: httpx.Client, email: str) -> str:
    resp = client.post("/api/auth/login", json={"email": email})
    resp.raise_for_status()
    return resp.json()["token"]


def reset_vendor(client: httpx.Client, token: str):
    """Delete all docs + applications for this vendor before test run."""
    for endpoint in ("/api/documents/all", "/api/application/reset"):
        resp = client.delete(endpoint, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code not in (200, 404):
            warn(f"  Cleanup warning [{resp.status_code}] {endpoint}: {resp.text[:80]}")


def reset_vendor_docs(client: httpx.Client, token: str):
    """Delete only docs (used between rounds of fix tests)."""
    resp = client.delete(
        "/api/documents/all",
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code not in (200, 404):
        warn(f"  Cleanup warning [{resp.status_code}]: {resp.text[:80]}")


def upload_docs(client: httpx.Client, token: str, docs: list[dict]) -> list[str]:
    uploaded = []
    for doc in docs:
        path = doc["file_path"]
        doc_type = doc["doc_type"]
        if not os.path.exists(path):
            warn(f"    Doc missing on disk: {path} — skipping")
            continue
        with open(path, "rb") as f:
            content = f.read()
        ext = path.rsplit(".", 1)[-1].lower()
        mime = "application/pdf" if ext == "pdf" else "image/jpeg"
        files = {"file": (os.path.basename(path), content, mime)}
        data = {"doc_type": doc_type}
        resp = client.post(
            "/api/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        if resp.status_code == 200:
            uploaded.append(doc_type)
        else:
            warn(f"    Doc upload failed [{resp.status_code}]: {doc_type} — {resp.text[:120]}")
    return uploaded


def submit(client: httpx.Client, token: str, payload: dict) -> tuple[int, dict]:
    resp = client.post(
        "/api/application/submit",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    return resp.status_code, body


def run_single_test(client: httpx.Client, test_dir: Path, test_name: str, email: str):
    info(f"\n{'─'*60}")
    info(f"[bold]{test_name}[/bold]  ({email})")

    meta_path = test_dir / "meta.json"
    payload_path = test_dir / "payload.json"
    if not payload_path.exists():
        fail(f"  payload.json not found — run generate_tests.py first")
        results.append({"test": test_name, "round": 1, "status": "SKIP", "note": "no payload"})
        return

    with open(payload_path) as f:
        payload = json.load(f)
    with open(meta_path) as f:
        meta = json.load(f)

    info(f"  Notes: {meta.get('notes', '')}")

    token = login(client, email)
    info(f"  Logged in as {email}")
    reset_vendor(client, token)

    uploaded = upload_docs(client, token, meta.get("documents", []))
    info(f"  Uploaded {len(uploaded)} docs: {uploaded}")

    status_code, body = submit(client, token, payload)
    actual_status = body.get("status", "unknown")
    errors = body.get("errors", [])
    expected = meta.get("expected_round_1", "submitted")

    passed = (
        (expected == "submitted" and actual_status == "submitted") or
        (expected == "draft" and actual_status == "draft")
    )

    if passed:
        success(f"  ✓ PASS  [{status_code}] status={actual_status}  expected={expected}")
    else:
        fail(f"  ✗ FAIL  [{status_code}] status={actual_status}  expected={expected}")

    if errors:
        for e in errors:
            warn(f"    → {e}")

    results.append({
        "test": test_name,
        "round": 1,
        "expected": expected,
        "actual": actual_status,
        "status": "PASS" if passed else "FAIL",
        "errors": errors,
    })


def run_fix_test(client: httpx.Client, test_dir: Path, test_name: str, email: str):
    info(f"\n{'─'*60}")
    info(f"[bold]{test_name}[/bold]  ({email})  [2-round fix test]")

    for rnd, subdir in [(1, "round_1"), (2, "round_2")]:
        rnd_dir = test_dir / subdir
        payload_path = rnd_dir / "payload.json"
        meta_path = rnd_dir / "meta.json"

        if not payload_path.exists():
            fail(f"  {subdir}/payload.json not found — run generate_tests.py first")
            results.append({"test": test_name, "round": rnd, "status": "SKIP"})
            continue

        with open(payload_path) as f:
            payload = json.load(f)
        with open(meta_path) as f:
            meta = json.load(f)

        info(f"\n  [Round {rnd}] Notes: {meta.get('notes', '')}")

        # Same vendor re-uses same token (same email = same vendor_id in Supabase)
        token = login(client, email)

        # Round 1: full reset (docs + applications). Round 2: docs only — keep draft from round 1
        if rnd == 1:
            reset_vendor(client, token)
        else:
            reset_vendor_docs(client, token)

        uploaded = upload_docs(client, token, meta.get("documents", []))
        info(f"  Uploaded {len(uploaded)} docs: {uploaded}")

        status_code, body = submit(client, token, payload)
        actual_status = body.get("status", "unknown")
        errors = body.get("errors", [])
        expected = meta.get("expected_round_1", "submitted")

        passed = (
            (expected == "submitted" and actual_status == "submitted") or
            (expected == "draft" and actual_status == "draft")
        )

        if passed:
            success(f"  ✓ PASS  [Round {rnd}] [{status_code}] status={actual_status}  expected={expected}")
        else:
            fail(f"  ✗ FAIL  [Round {rnd}] [{status_code}] status={actual_status}  expected={expected}")

        if errors:
            for e in errors:
                warn(f"    → {e}")

        results.append({
            "test": test_name,
            "round": rnd,
            "expected": expected,
            "actual": actual_status,
            "status": "PASS" if passed else "FAIL",
            "errors": errors,
        })


def print_summary():
    info(f"\n{'═'*60}")
    info("[bold]FINAL TEST RESULTS[/bold]")
    info(f"{'═'*60}")

    try:
        table = Table()
        table.add_column("Test", style="bold")
        table.add_column("Round")
        table.add_column("Expected")
        table.add_column("Actual")
        table.add_column("Result")

        for r in results:
            color = "green" if r["status"] == "PASS" else ("yellow" if r["status"] == "SKIP" else "red")
            table.add_row(
                r["test"],
                str(r.get("round", 1)),
                r.get("expected", "—"),
                r.get("actual", "—"),
                f"[{color}]{r['status']}[/{color}]",
            )
        console.print(table)
    except Exception:
        for r in results:
            print(f"{r['test']}  round={r.get('round')}  {r['status']}")

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIP")
    info(f"\nTotal: {len(results)}  |  ✓ {passed} passed  |  ✗ {failed} failed  |  ~ {skipped} skipped")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8000")
    args = parser.parse_args()

    info(f"[bold]Running final tests against {args.api_url}[/bold]")

    try:
        client = httpx.Client(base_url=args.api_url, timeout=30)
        client.get("/health")
    except Exception:
        fail(f"Cannot reach API at {args.api_url}. Start backend first.")
        sys.exit(1)

    test_dirs = sorted(TESTS_DIR.glob("test_*/"))

    for test_dir in test_dirs:
        test_name = test_dir.name
        email = TEST_EMAILS.get(test_name)
        if not email:
            continue

        if test_name in FIX_TESTS:
            run_fix_test(client, test_dir, test_name, email)
        else:
            run_single_test(client, test_dir, test_name, email)

    print_summary()


if __name__ == "__main__":
    main()
