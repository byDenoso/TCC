import argparse
import json
from pathlib import Path

from runtime.nexo_execution.core import ExecutionContract, LocalProvider, ResultVerifier


def run_contract(contract_path: str, result_path: str, verification_path: str, expected_hash: str | None = None) -> int:
    contract = ExecutionContract.load(contract_path)
    if expected_hash and contract.contract_hash != expected_hash:
        Path(verification_path).write_text(json.dumps({"status": "FAIL", "errors": ["contract_hash_mismatch"]}, indent=2) + "\n", encoding="utf-8")
        return 3

    result = LocalProvider().submit(contract)
    Path(result_path).write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    verification = ResultVerifier().verify(contract, result)
    Path(verification_path).write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": result.to_dict(), "verification": verification}, indent=2))
    return 0 if verification["status"] == "PASS" else 2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract")
    parser.add_argument("--result", default="nexo_execution_result.json")
    parser.add_argument("--verification", default="nexo_verification.json")
    parser.add_argument("--expected-contract-hash", default=None)
    args = parser.parse_args()
    code = run_contract(args.contract, args.result, args.verification, args.expected_contract_hash)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
