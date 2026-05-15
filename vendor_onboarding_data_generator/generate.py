#!/usr/bin/env python3
import sys
import os
import json
import importlib
from pathlib import Path

# Ensure package root is on sys.path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

try:
    import typer
    from rich.console import Console
    from rich.table import Table
    RICH_TYPER = True
except ImportError:
    RICH_TYPER = False

SCENARIO_MAP = {
    # Valid
    "valid_pvt_ltd": "scenarios.valid_pvt_ltd",
    "valid_llp": "scenarios.valid_llp",
    "valid_sole_prop": "scenarios.valid_sole_prop",
    "valid_partnership": "scenarios.valid_partnership",
    "valid_no_gst": "scenarios.valid_no_gst",
    "valid_with_msme": "scenarios.valid_with_msme",
    # Invalid
    "invalid_pan_mismatch": "scenarios.invalid_pan_mismatch",
    "invalid_gst_state": "scenarios.invalid_gst_state",
    "invalid_cin_year": "scenarios.invalid_cin_year",
    "invalid_free_email": "scenarios.invalid_free_email",
    "invalid_data_offshore": "scenarios.invalid_data_offshore",
    "invalid_missing_dpa": "scenarios.invalid_missing_dpa",
    "invalid_expired_iso": "scenarios.invalid_expired_iso",
    "invalid_no_cyber_insurance": "scenarios.invalid_no_cyber_insurance",
    "invalid_account_name": "scenarios.invalid_account_name",
    "invalid_short_account": "scenarios.invalid_short_account",
    "invalid_bad_ifsc": "scenarios.invalid_bad_ifsc",
    "invalid_phone_no_code": "scenarios.invalid_phone_no_code",
    "invalid_pan_type_mismatch": "scenarios.invalid_pan_type_mismatch",
    "invalid_gst_registered_no_number": "scenarios.invalid_gst_registered_no_number",
    "invalid_dpin_missing_llp": "scenarios.invalid_dpin_missing_llp",
    "invalid_signatory_short": "scenarios.invalid_signatory_short",
    # Edge
    "edge_msme_limits": "scenarios.edge_msme_limits",
    "edge_iso_expires_today": "scenarios.edge_iso_expires_today",
    "edge_max_employees": "scenarios.edge_max_employees",
}

VALID_SCENARIOS = [k for k in SCENARIO_MAP if k.startswith("valid_")]
INVALID_SCENARIOS = [k for k in SCENARIO_MAP if k.startswith("invalid_")]
EDGE_SCENARIOS = [k for k in SCENARIO_MAP if k.startswith("edge_")]


def _run_scenario(name: str, output_base: str = "output/docs") -> dict:
    module_path = SCENARIO_MAP[name]
    mod = importlib.import_module(module_path)
    return mod.generate(output_base=output_base)


def _save_json(payload: dict, output_dir: str):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    scenario = payload.get("scenario", "unknown")
    vendor_id = payload.get("vendor_id", "vendor")
    fname = f"{scenario}_{vendor_id}.json"
    fpath = os.path.join(output_dir, fname)
    with open(fpath, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    return fpath


if RICH_TYPER:
    app = typer.Typer(help="Vendor Onboarding Data Generator")
    console = Console()

    @app.command()
    def single(
        scenario: str = typer.Option("valid_pvt_ltd", help="Scenario name"),
        output: str = typer.Option("output/json", help="JSON output directory"),
        docs: str = typer.Option("output/docs", help="Documents output directory"),
        print_json: bool = typer.Option(False, "--print", help="Print JSON to stdout"),
    ):
        """Generate one vendor payload for a given scenario."""
        if scenario not in SCENARIO_MAP:
            console.print(f"[red]Unknown scenario: {scenario}[/red]")
            console.print(f"Run [bold]list-scenarios[/bold] to see available options.")
            raise typer.Exit(1)
        payload = _run_scenario(scenario, output_base=docs)
        fpath = _save_json(payload, output)
        console.print(f"[green]✓[/green] Generated [bold]{scenario}[/bold] → {fpath}")
        if payload.get("documents"):
            console.print(f"  Documents: {len(payload['documents'])} files in {docs}/")
        if print_json:
            console.print_json(json.dumps(payload, default=str))

    @app.command()
    def bulk(
        count: int = typer.Option(10, help="Number of vendors to generate"),
        scenario: str = typer.Option("valid_pvt_ltd", help="Scenario to repeat"),
        output: str = typer.Option("output/json", help="JSON output directory"),
        docs: str = typer.Option("output/docs", help="Documents output directory"),
    ):
        """Generate multiple vendor payloads (bulk/load testing)."""
        if scenario not in SCENARIO_MAP:
            console.print(f"[red]Unknown scenario: {scenario}[/red]")
            raise typer.Exit(1)
        console.print(f"Generating {count} × [bold]{scenario}[/bold]...")
        for i in range(count):
            payload = _run_scenario(scenario, output_base=docs)
            fpath = _save_json(payload, output)
            console.print(f"  [{i+1}/{count}] {payload['vendor_id']} → {fpath}")
        console.print(f"[green]Done.[/green] {count} vendors saved to {output}/")

    @app.command(name="all-invalid")
    def all_invalid(
        output: str = typer.Option("output/json", help="JSON output directory"),
        docs: str = typer.Option("output/docs", help="Documents output directory"),
    ):
        """Generate all invalid scenarios."""
        for name in INVALID_SCENARIOS:
            payload = _run_scenario(name, output_base=docs)
            fpath = _save_json(payload, output)
            errors = payload.get("expected_result", {}).get("errors", [])
            console.print(f"[yellow]✗[/yellow] [bold]{name}[/bold] → {fpath}")
            for e in errors:
                console.print(f"    expected: {e}")

    @app.command(name="all-edge")
    def all_edge(
        output: str = typer.Option("output/json", help="JSON output directory"),
        docs: str = typer.Option("output/docs", help="Documents output directory"),
    ):
        """Generate all edge case scenarios."""
        for name in EDGE_SCENARIOS:
            payload = _run_scenario(name, output_base=docs)
            fpath = _save_json(payload, output)
            console.print(f"[cyan]~[/cyan] [bold]{name}[/bold] → {fpath}")

    @app.command(name="all-valid")
    def all_valid_cmd(
        output: str = typer.Option("output/json", help="JSON output directory"),
        docs: str = typer.Option("output/docs", help="Documents output directory"),
    ):
        """Generate all valid scenarios."""
        for name in VALID_SCENARIOS:
            payload = _run_scenario(name, output_base=docs)
            fpath = _save_json(payload, output)
            console.print(f"[green]✓[/green] [bold]{name}[/bold] → {fpath}")

    @app.command(name="list-scenarios")
    def list_scenarios():
        """List all available scenarios."""
        table = Table(title="Available Scenarios")
        table.add_column("Name", style="bold")
        table.add_column("Type")
        for name in SCENARIO_MAP:
            if name.startswith("valid_"):
                tag = "[green]valid[/green]"
            elif name.startswith("invalid_"):
                tag = "[red]invalid[/red]"
            else:
                tag = "[cyan]edge[/cyan]"
            table.add_row(name, tag)
        console.print(table)

    @app.command()
    def test(
        scenario: str = typer.Option("valid_pvt_ltd", help="Scenario to test"),
        api_url: str = typer.Option("http://localhost:8000", help="Backend API base URL"),
        docs: str = typer.Option("output/docs", help="Documents output directory"),
    ):
        """Generate and POST directly to the live API."""
        try:
            import httpx
        except ImportError:
            console.print("[red]httpx not installed. Run: pip install httpx[/red]")
            raise typer.Exit(1)

        if scenario not in SCENARIO_MAP:
            console.print(f"[red]Unknown scenario: {scenario}[/red]")
            raise typer.Exit(1)

        payload = _run_scenario(scenario, output_base=docs)
        expected = payload.get("expected_result", {})

        console.print(f"POSTing [bold]{scenario}[/bold] to {api_url}/api/application/submit ...")
        try:
            resp = httpx.post(
                f"{api_url}/api/application/submit",
                json=payload["form_data"],
                timeout=30,
            )
            status_code = resp.status_code
            try:
                body = resp.json()
            except Exception:
                body = resp.text

            if expected.get("status") == "submitted" and status_code in (200, 201):
                console.print(f"[green]PASS[/green] {status_code} — expected submitted, got {status_code}")
            elif expected.get("status") == "incomplete" and status_code in (400, 422):
                console.print(f"[green]PASS[/green] {status_code} — expected error, got error")
            else:
                console.print(f"[red]FAIL[/red] {status_code} — expected {expected.get('status')}")
            console.print(f"Response: {body}")
        except httpx.ConnectError:
            console.print(f"[red]Could not connect to {api_url}. Is the backend running?[/red]")

    if __name__ == "__main__":
        app()

else:
    # Minimal fallback without typer/rich
    import argparse

    def main():
        parser = argparse.ArgumentParser(description="Vendor Onboarding Data Generator")
        subparsers = parser.add_subparsers(dest="command")

        s = subparsers.add_parser("single")
        s.add_argument("--scenario", default="valid_pvt_ltd")
        s.add_argument("--output", default="output/json")
        s.add_argument("--docs", default="output/docs")

        b = subparsers.add_parser("bulk")
        b.add_argument("--count", type=int, default=10)
        b.add_argument("--scenario", default="valid_pvt_ltd")
        b.add_argument("--output", default="output/json")
        b.add_argument("--docs", default="output/docs")

        subparsers.add_parser("list-scenarios")
        subparsers.add_parser("all-invalid")
        subparsers.add_parser("all-valid")

        args = parser.parse_args()

        if args.command == "list-scenarios":
            for name in SCENARIO_MAP:
                print(name)
        elif args.command == "single":
            payload = _run_scenario(args.scenario, output_base=args.docs)
            fpath = _save_json(payload, args.output)
            print(f"Generated: {fpath}")
        elif args.command == "bulk":
            for _ in range(args.count):
                payload = _run_scenario(args.scenario, output_base=args.docs)
                fpath = _save_json(payload, args.output)
                print(f"Generated: {fpath}")
        elif args.command == "all-invalid":
            for name in INVALID_SCENARIOS:
                payload = _run_scenario(name, output_base="output/docs")
                fpath = _save_json(payload, "output/json")
                print(f"Generated: {fpath}")
        elif args.command == "all-valid":
            for name in VALID_SCENARIOS:
                payload = _run_scenario(name, output_base="output/docs")
                fpath = _save_json(payload, "output/json")
                print(f"Generated: {fpath}")
        else:
            parser.print_help()

    if __name__ == "__main__":
        main()
