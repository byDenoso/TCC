from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.request
from pathlib import Path
from typing import Any

from runtime.nexo_execution.peer_detection import evaluate_gate

OUTPUT_PATH = Path("peer_detection_gate_result.json")
_ALLOWED_BINDINGS = ("INPUT_PATH", "INPUT_URL", "INPUT_SHA256", "RESULTS_BUNDLE_PATH")


def _env(name: str) -> str:
    for prefix in ("NEXO_BINDING_", "NEXO_PARAM_"):
        value = os.environ.get(f"{prefix}{name}", "").strip()
        if value:
            return value
    return ""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode_json(data: bytes, source: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON evidence from {source}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"evidence root from {source} must be an object")
    return value


def _read_path(raw: str) -> tuple[dict[str, Any], dict[str, Any]]:
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"evidence path not found: {raw}")
    data = path.read_bytes()
    return _decode_json(data, str(path)), {"source": "path", "path": str(path), "sha256": _sha256(data)}


def _read_url(raw: str, expected_sha: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not raw.startswith(("https://", "http://")):
        raise ValueError("input_url must use http or https")
    with urllib.request.urlopen(raw, timeout=30) as response:
        data = response.read()
    actual = _sha256(data)
    if expected_sha and actual.lower() != expected_sha.lower():
        raise ValueError("input_url sha256 mismatch")
    return _decode_json(data, raw), {"source": "url", "url": raw, "sha256": actual, "sha256_verified": bool(expected_sha)}


def load_bound_evidence(gate_id: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    bundle_path = _env("RESULTS_BUNDLE_PATH")
    input_path = _env("INPUT_PATH")
    input_url = _env("INPUT_URL")
    expected_sha = _env("INPUT_SHA256")

    if gate_id == "D25" and bundle_path:
        return _read_path(bundle_path)
    if input_path:
        return _read_path(input_path)
    if input_url:
        return _read_url(input_url, expected_sha)
    if bundle_path:
        bundle, provenance = _read_path(bundle_path)
        gates = bundle.get("gates")
        if isinstance(gates, dict):
            selected = gates.get(gate_id)
            if selected is None:
                return None, {**provenance, "bundle_gate": gate_id, "gate_present": False}
            if not isinstance(selected, dict):
                raise ValueError(f"bundle gate {gate_id} must be an object")
            return selected, {**provenance, "bundle_gate": gate_id, "gate_present": True}
        return bundle, provenance
    return None, {"source": "unbound"}


def run_gate(gate_id: str) -> dict[str, Any]:
    evidence, provenance = load_bound_evidence(gate_id)
    if gate_id == "D25" and evidence is not None and isinstance(evidence.get("gates"), dict):
        evidence = {"results": evidence["gates"]}
    result = evaluate_gate(gate_id, evidence)
    result["binding_provenance"] = provenance
    result["binding_keys_present"] = [key.lower() for key in _ALLOWED_BINDINGS if _env(key)]
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate one frozen PEER detection gate")
    parser.add_argument("--gate", required=True)
    args = parser.parse_args()
    result = run_gate(args.gate.strip().upper())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
