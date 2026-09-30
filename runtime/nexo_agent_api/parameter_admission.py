"""Run the catalog's pure parameter validator; never infer compatible inputs.

The scientific rules live once in the Pantheon recipe catalog. The Writer only
verifies that the validator's receipt commits the exact files it invoked.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

CONTRACT = "RECIPE_PARAM_PREFLIGHT_V1"
# Migration is deliberately bounded. Other recipes opt in with a manifest and
# retain their explicitly weaker syntax/smoke scope until one is supplied.
REQUIRED_RECIPES = frozenset({"w0wa_bao_sn_multi"})
RECEIPT_FIELDS = ("contract", "eligible", "reasons", "manifest_sha256", "validator_sha256")


def validate(recipe: str, params: dict, inputs: list, recipe_root: Path) -> dict | None:
    manifest = recipe_root / "preflight" / (recipe + ".json")
    if recipe not in REQUIRED_RECIPES and not manifest.is_file():
        return None
    receipt = {"contract": CONTRACT, "eligible": False, "reasons": [],
               "manifest_sha256": None, "validator_sha256": None}
    validator = recipe_root / "recipe_param_preflight.py"
    if not manifest.is_file() or not validator.is_file():
        return dict(receipt, reasons=["PREFLIGHT_CONTRACT_MISSING"])
    try:
        manifest_raw, validator_raw = manifest.read_bytes(), validator.read_bytes()
        receipt.update(manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
                       validator_sha256=hashlib.sha256(validator_raw).hexdigest())
        namespace = {"__name__": "nexo_catalog_parameter_preflight", "__file__": str(validator)}
        exec(compile(validator_raw, str(validator), "exec"), namespace)
        result = namespace["validate_params"](recipe, params, inputs, recipe_root)
        if not isinstance(result, dict) or result.get("contract") != CONTRACT or type(result.get("eligible")) is not bool:
            raise ValueError("invalid validator contract")
        reasons = result.get("reasons")
        if (not isinstance(reasons, list) or len(reasons) > 32 or
                any(not isinstance(reason, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,79}", reason) for reason in reasons) or
                result["eligible"] != (not reasons)):
            raise ValueError("invalid validator decision")
        if (any(result.get(key) != receipt[key] for key in ("manifest_sha256", "validator_sha256")) or
                manifest.read_bytes() != manifest_raw or validator.read_bytes() != validator_raw):
            return dict(receipt, reasons=["PREFLIGHT_RECEIPT_HASH_MISMATCH"])
        return {key: result[key] for key in RECEIPT_FIELDS}
    except Exception:
        return dict(receipt, reasons=["PREFLIGHT_VALIDATOR_ERROR"])


def commitment(receipt: dict | None) -> dict | None:
    if receipt is None:
        return None
    return {key: receipt.get(key) for key in ("contract", "manifest_sha256", "validator_sha256")}
