"""Deploy CounterpartyRisk.

    export GENLAYER_RPC_URL=https://studio.genlayer.com/api
    export GENLAYER_PRIVATE_KEY=0x...
    python scripts/deploy.py --allowlist examples/vendor_onboarding.json

The allowlist may come from an example file (constructor.allowed_domains) or be
passed inline with --domains 'sec.gov,companieshouse.gov.uk'.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

CONTRACT = Path("contracts/counterparty_risk.py")


def build_allowlist(args: argparse.Namespace) -> str:
    if args.domains:
        hosts = [d.strip() for d in args.domains.split(",") if d.strip()]
        return json.dumps(hosts)
    if args.allowlist:
        payload = json.loads(Path(args.allowlist).read_text(encoding="utf-8"))
        return payload["constructor"]["allowed_domains"]
    raise SystemExit("pass --allowlist <example.json> or --domains a.com,b.com")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allowlist", help="example JSON file with constructor.allowed_domains")
    parser.add_argument("--domains", help="comma-separated bare hosts")
    parser.add_argument("--dry-run", action="store_true", help="print the call, do not send")
    args = parser.parse_args()

    allowed_domains = build_allowlist(args)
    code = CONTRACT.read_bytes()

    print(f"contract      : {CONTRACT} ({len(code)} bytes)")
    print(f"allowed_domains: {allowed_domains}")

    if args.dry_run:
        print("dry run — nothing sent")
        return

    rpc = os.environ.get("GENLAYER_RPC_URL")
    key = os.environ.get("GENLAYER_PRIVATE_KEY")
    if not rpc or not key:
        raise SystemExit("set GENLAYER_RPC_URL and GENLAYER_PRIVATE_KEY")

    try:
        from genlayer_py import create_account, create_client  # type: ignore
    except ImportError:
        sys.exit("pip install -r requirements.txt (genlayer-py is required to deploy)")

    client = create_client(endpoint=rpc, account=create_account(key))
    address = client.deploy_contract(code=code, args=[allowed_domains])
    print(f"deployed at   : {address}")


if __name__ == "__main__":
    main()
