#!/usr/bin/env python3
"""Materialize the official frozen Pantheon+SH0ES full covariance, fail closed.

This is input acquisition, not scientific execution or Tower binding. The
Engineer must still persist verified bytes through the authorized Drive
surface and prove readback before changing a canonical DATA_BINDING.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request

DATARELEASE_COMMIT = "c447f0fea703fcd0fff57de5000947b5ca81286b"
SOURCE_GIT_BLOB_SHA = "d1a1498154e7ba826df14bdbef35ebcb7f5efba1"
SOURCE_URL = (
    "https://raw.githubusercontent.com/PantheonPlusSH0ES/DataRelease/"
    + DATARELEASE_COMMIT
    + "/Pantheon%2B_Data/4_DISTANCES_AND_COVAR/Pantheon%2BSH0ES_STAT%2BSYS.cov"
)
EXPECTED_SHA256 = "abf806d966485e64afdb359c87bffc0ecc00d05eff0a31ced66f247385df0fdc"
EXPECTED_SIZE = 33284960
EXPECTED_DIMENSION = 1701


def verify_covariance(path: Path, *, digest: str = EXPECTED_SHA256,
                      size: int = EXPECTED_SIZE, dimension: int = EXPECTED_DIMENSION) -> dict:
    hasher = hashlib.sha256()
    nbytes = 0
    with path.open("rb") as source:
        header = source.readline()
        try:
            observed_dimension = int(header.strip())
        except ValueError as exc:
            raise ValueError("BAD_COVARIANCE_DIMENSION_HEADER") from exc
        hasher.update(header)
        nbytes += len(header)
        count = 0
        for row in source:
            count += 1
            hasher.update(row)
            nbytes += len(row)
    observed_sha = hasher.hexdigest()
    if nbytes != size:
        raise ValueError(f"COVARIANCE_SIZE_MISMATCH:{nbytes}!={size}")
    if observed_sha != digest:
        raise ValueError(f"COVARIANCE_SHA256_MISMATCH:{observed_sha}")
    if observed_dimension != dimension or count != dimension * dimension:
        raise ValueError(f"COVARIANCE_SHAPE_MISMATCH:{observed_dimension}:{count}")
    return {"status": "INPUT_BYTES_VERIFIED_ONLY", "source": SOURCE_URL,
            "source_git_blob_sha": SOURCE_GIT_BLOB_SHA,
            "dimension": dimension, "bytes": nbytes, "sha256": observed_sha}


def materialize(output: Path) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        return {**verify_covariance(output), "action": "REUSED_VERIFIED"}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".pantheon-cov-", suffix=".tmp",
                                         dir=output.parent, delete=False) as destination:
            temporary = Path(destination.name)
            req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "NEXO-verified-input/1.0"})
            with urllib.request.urlopen(req, timeout=120) as remote:
                while True:
                    chunk = remote.read(1024 * 1024)
                    if not chunk:
                        break
                    destination.write(chunk)
                    if destination.tell() > EXPECTED_SIZE:
                        raise ValueError("COVARIANCE_TOO_LARGE")
            destination.flush()
            os.fsync(destination.fileno())
        report = verify_covariance(temporary)
        if output.exists():
            return {**verify_covariance(output), "action": "REUSED_VERIFIED_AFTER_RACE"}
        os.replace(temporary, output)
        temporary = None
        return {**report, "action": "MATERIALIZED_VERIFIED"}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
