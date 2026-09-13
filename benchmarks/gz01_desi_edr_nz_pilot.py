#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import tempfile
import urllib.request
from collections import defaultdict
from pathlib import Path

SOURCE_URL = "https://data.desi.lbl.gov/public/edr/vac/edr/epoviz/v1.0/EDR-Viz-Outreach-VAC.csv.gz"
EXPECTED_SHA256 = "83a4c4c4c4e8eb309e6a71459b3e6087113b82ef03edeeb09752ce368443b6d6"
OUTPUT = Path("gz01_edr_nz_result.json")
BIN_WIDTH = 0.1
Z_MIN = 0.0
Z_MAX = 4.0
TRACERS = {0: "QSO", 1: "ELG", 2: "LRG", 3: "BGS"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def bin_index(z: float) -> int | None:
    if not math.isfinite(z) or z < Z_MIN or z >= Z_MAX:
        return None
    return int((z - Z_MIN) / BIN_WIDTH)


def summarize_catalog(path: Path) -> dict:
    bins = int((Z_MAX - Z_MIN) / BIN_WIDTH)
    counts = {name: [0] * bins for name in TRACERS.values()}
    sums = defaultdict(float)
    totals = defaultdict(int)
    skipped = 0

    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"REDSHIFT", "TRACER"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise RuntimeError(f"missing required columns: {sorted(required)}")
        for row in reader:
            try:
                z = float(row["REDSHIFT"])
                tracer_code = int(row["TRACER"])
            except (TypeError, ValueError):
                skipped += 1
                continue
            name = TRACERS.get(tracer_code)
            idx = bin_index(z)
            if name is None or idx is None:
                skipped += 1
                continue
            counts[name][idx] += 1
            totals[name] += 1
            sums[name] += z

    edges = [round(Z_MIN + i * BIN_WIDTH, 3) for i in range(bins + 1)]
    tracers = {}
    for name in TRACERS.values():
        hist = counts[name]
        peak_idx = max(range(len(hist)), key=hist.__getitem__) if hist else 0
        tracers[name] = {
            "total": totals[name],
            "mean_z": (sums[name] / totals[name]) if totals[name] else None,
            "peak_bin": [edges[peak_idx], edges[peak_idx + 1]],
            "peak_count": hist[peak_idx] if hist else 0,
            "counts": hist,
        }
    return {
        "bin_edges": edges,
        "tracers": tracers,
        "total_used": sum(totals.values()),
        "skipped": skipped,
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="nexo-gz01-") as raw:
        source = Path(raw) / "EDR-Viz-Outreach-VAC.csv.gz"
        request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "NEXO-GZ01/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response, source.open("wb") as target:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                target.write(chunk)
        source_sha256 = sha256_file(source)
        if source_sha256 != EXPECTED_SHA256:
            raise RuntimeError(f"DESI source hash mismatch: {source_sha256}")
        summary = summarize_catalog(source)
        result = {
            "schema": "nexo.gz01.nz-pilot.v1",
            "campaign_id": "GZ-01",
            "batch_id": "GZ-01-B01",
            "test_id": "GZ01-T01-DESI-NZ-PILOT",
            "status": "PASS",
            "dataset": {
                "name": "DESI EDR Visualization and Outreach VAC",
                "release": "EDR",
                "version": "v1.0",
                "source_url": SOURCE_URL,
                "sha256": source_sha256,
                "expected_sha256": EXPECTED_SHA256
            },
            "analysis": summary,
            "claim_boundary": (
                "Observed tracer-resolved N(z) pilot only. This EDR outreach catalog is not DESI DR1, "
                "is not selection/completeness corrected, and must not be interpreted as comoving galaxy density."
            ),
            "canonicalization": "PENDING_CANONICALIZATION",
        }
        OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({
            "status": result["status"],
            "source_sha256": source_sha256,
            "total_used": summary["total_used"],
            "output": str(OUTPUT),
        }, sort_keys=True))


if __name__ == "__main__":
    main()
