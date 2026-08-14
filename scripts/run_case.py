"""Open a case, run round 0, and print the structured ruling.

    export GENLAYER_RPC_URL=... GENLAYER_PRIVATE_KEY=...
    python scripts/run_case.py --address 0xContract --case examples/vendor_onboarding.json
    python scripts/run_case.py --address 0xContract --case examples/otc_desk_kyb.json --challenge
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

FIELDS = ["subject_name", "subject_domain", "context", "criteria", "evidence_urls", "reviewer"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--address", required=True, help="deployed contract address")
    parser.add_argument("--case", required=True, help="example JSON file with an open_case block")
    parser.add_argument("--challenge", action="store_true", help="run one challenge round too")
    args = parser.parse_args()

    payload = json.loads(Path(args.case).read_text(encoding="utf-8"))["open_case"]
    call_args = [payload[f] for f in FIELDS]

    rpc = os.environ.get("GENLAYER_RPC_URL")
    key = os.environ.get("GENLAYER_PRIVATE_KEY")
    if not rpc or not key:
        raise SystemExit("set GENLAYER_RPC_URL and GENLAYER_PRIVATE_KEY")

    try:
        from genlayer_py import create_account, create_client  # type: ignore
    except ImportError:
        sys.exit("pip install -r requirements.txt (genlayer-py is required)")

    account = create_account(key)
    client = create_client(endpoint=rpc, account=account)

    def write(method: str, a: list) -> None:
        tx = client.write_contract(address=args.address, function_name=method, args=a)
        client.wait_for_transaction_receipt(transaction_hash=tx)
        print(f"  sent {method}")

    def read(method: str, a: list):
        return client.read_contract(address=args.address, function_name=method, args=a)

    # open_case returns None by design; read the id back from cases_of
    write("open_case", call_args)
    ids = read("cases_of", [account.address])
    case_id = ids[-1]
    print(f"case id: {case_id}")

    write("assess", [case_id])
    if args.challenge:
        write("challenge", [case_id])
        # note: one challenge per address per case; a second call from the same
        # key is rejected on purpose.

    print("\ncase:")
    print(json.dumps(read("get_case", [case_id]), indent=2))
    print("\nstanding ruling:")
    print(json.dumps(read("get_assessment", [case_id]), indent=2))
    print("\nfull history:")
    print(json.dumps(read("get_rulings", [case_id]), indent=2))


if __name__ == "__main__":
    main()
