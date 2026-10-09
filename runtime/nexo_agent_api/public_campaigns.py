"""Writer policy registry and private bridge to the sanitized Atlas projector.

This module never translates prose or invents campaign membership. Canonical
question IDs, public visibility and bilingual presentation must already exist.
The Node bridge verifies byte commitments before adapting JSON number encoding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import autonomy
from .scientific_integrity import independence
from .semantics import is_private, resolve

POLICY = "NEXO_PUBLIC_CAMPAIGNS_V1"
REGISTRY = "evolution/public_campaign_approvals.json"


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def commitment(value):
    raw = encoded(value)
    return {"json": raw, "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest()}


def public(source):
    return (source.get("visibility") == "PUBLIC" and source.get("private") is not True
            and not is_private(resolve(source, entity_id=str(source.get("id") or source.get("roadmap_id") or ""))))


def normalized_test(source):
    from .public_projection import _public_test_entity
    output = _public_test_entity(source)
    output.update(id=source["id"], visibility=source["visibility"])
    if re.fullmatch(r"[A-Za-z0-9_:-]{3,120}", str(source.get("question_id") or "")):
        output["question_id"] = source["question_id"]
    if re.fullmatch(r"actions/runs/[0-9]+", str(source.get("run_ref") or "")):
        output["run_ref"] = source["run_ref"]
    if autonomy.timestamp(source.get("executed_at")):
        output["executed_at"] = source["executed_at"]
    if source.get("execution_pending_reason") == "EXTERNAL_RUN_RECONCILIATION_REQUIRED":
        output["execution_pending_reason"] = source["execution_pending_reason"]
    if (source.get("execution_observation") in {"GITHUB_JOB_STEP", "GITHUB_RUN_AND_ARTIFACT"}
            and autonomy.timestamp(source.get("started_at"))):
        output.update(execution_observation=source["execution_observation"], started_at=source["started_at"])
    if isinstance(source.get("mechanical_contest_verdict"), dict):
        output["mechanical_contest_verdict"] = {key: source["mechanical_contest_verdict"].get(key)
                                                for key in ("contest_test_id", "outcome", "rule", "at")}
    if isinstance(source.get("review_validation"), dict):
        output["review_validation"] = {key: source["review_validation"].get(key) for key in ("policy", "eligible")}
    output["reviews"] = [{key: review.get(key) for key in ("referee", "outcome", "contest_test_id", "at")}
                         for review in source.get("reviews") or [] if isinstance(review, dict)]
    output["contests"] = [{"contest_test_id": contest.get("contest_test_id")}
                          for contest in source.get("contests") or [] if isinstance(contest, dict)]
    if source.get("contests_test_id"):
        output["contests_test_id"] = source["contests_test_id"]
    return output


def source_records(root):
    """Expose only source records explicitly authorized for public presentation."""
    from .public_projection import _public_roadmaps
    raw_tests = {path.stem: autonomy.read(root, path.relative_to(root).as_posix())
                 for path in (Path(root) / "entities/test").glob("*.json")}
    tests = {tid: normalized_test(dict(source, id=source.get("id") or tid))
             for tid, source in raw_tests.items() if public(source)}
    raw_roadmaps = {path.stem: autonomy.read(root, path.relative_to(root).as_posix())
                    for path in (Path(root) / "roadmaps").glob("*.json")}
    roadmaps = []
    for record in _public_roadmaps(Path(root), list(tests.values()), []):
        source = raw_roadmaps.get(record["id"], {})
        if not public(source) or not source.get("question_id"):
            continue
        record.update(visibility="PUBLIC", question_id=source["question_id"])
        closure = source.get("closure")
        if isinstance(closure, dict):
            record["closure"] = {key: closure.get(key) for key in ("status", "receipt_id", "closed_at", "reason", "outcome")}
        roadmaps.append(record)
    return {"campaigns": [], "roadmaps": roadmaps, "tests": list(tests.values())}, raw_roadmaps, raw_tests


def independent_proof(root, source, normalized):
    """Freshly evaluate the existing scientific predicate over canonical evidence."""
    if source.get("review_state") not in {"CONFIRMED", "REFUTED"}:
        return None
    entries = list(source.get("reviews") or [])
    mechanical = source.get("mechanical_contest_verdict")
    if isinstance(mechanical, dict):
        entries.append(mechanical)
    for entry in reversed(entries):
        attack_id = str(entry.get("contest_test_id") or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", attack_id):
            continue
        attack = autonomy.read(root, "entities/test/" + attack_id + ".json")
        if (not public(attack) or attack.get("contests_test_id") != source.get("id")
                or not autonomy.timestamp(attack.get("executed_at")) or not autonomy.timestamp(entry.get("at"))):
            continue
        validation = independence(source, attack, Path(root))
        if not validation["eligible"]:
            continue
        attack_record = normalized_test(attack)
        return {"policy": "NEXO_SCIENTIFIC_INDEPENDENCE_V1", "eligible": True,
                "writerParentSha256": commitment(normalized)["sha256"], "attackId": attack_id,
                "writerAttackSha256": commitment(attack_record)["sha256"], "reviewedAt": entry["at"]}
    return None


def publication_requests(root):
    """Automatic policy approvals only for prospective mandate-backed public work."""
    if not autonomy.active(root):
        return []
    records, roadmaps, tests = source_records(root)
    current = autonomy.read(root, REGISTRY)
    old = {entry.get("sourceId"): entry for entry in current.get("approvals") or []}
    approvals = []
    campaigns = {record["id"]: record for record in records["roadmaps"]}
    for source_id, record in campaigns.items():
        source = roadmaps[source_id]
        presentation = source.get("public_presentation")
        if not autonomy.active(root, source.get("mandate_id")) or not isinstance(presentation, dict):
            continue
        identity = str(source.get("public_id") or source_id)
        entry = {"kind": "CAMPAIGN", "sourceId": source_id, "writerSourceSha256": commitment(record)["sha256"],
                 "publicId": identity, "questionId": source["question_id"], "presentation": presentation,
                 "publication": {"policy": POLICY, "status": "APPROVED",
                                 "receiptId": "PUB-" + hashlib.sha256(encoded(record).encode()).hexdigest()[:32]}}
        approvals.append(entry)
    admitted = {entry["sourceId"] for entry in approvals}
    for record in records["tests"]:
        source = tests[record["id"]]
        presentation = source.get("public_presentation")
        campaign_id = str(source.get("roadmap_id") or source.get("campaign_id") or "")
        if campaign_id not in admitted or not isinstance(presentation, dict):
            continue
        proof = independent_proof(root, source, record)
        entry = {"kind": "TEST", "sourceId": record["id"], "writerSourceSha256": commitment(record)["sha256"],
                 "publicId": str(source.get("public_id") or record["id"]), "campaignSourceId": campaign_id,
                 "presentation": presentation, "publication": {"policy": POLICY, "status": "APPROVED",
                 "receiptId": "PUB-" + commitment(record)["sha256"][:32]}}
        if proof:
            entry["independence"] = proof
        else:
            entry["presentation"] = {key: value for key, value in presentation.items() if key != "result"}
        approvals.append(entry)
    # Historical mappings remain byte-bound and explicitly approved; no text
    # similarity or stale approval can create or silently regroup a campaign.
    touched = {entry["sourceId"] for entry in approvals}
    approvals.extend(entry for source_id, entry in old.items() if source_id not in touched)
    approvals.sort(key=lambda entry: (entry.get("kind") or "", entry.get("sourceId") or ""))
    if approvals == current.get("approvals") or not approvals:
        return []
    delivery = dict(current.get("delivery") or {})
    delivery.update(status="PENDING_PUBLICATION", approved_content_sha256=autonomy.digest(approvals),
                    pending_reason="PUBLICATION_READBACK_REQUIRED",
                    pending_since=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    return [{"request_id": "REQ-PUBLIC-CAMPAIGNS-" + autonomy.digest(approvals)[:32], "document": REGISTRY,
             "merge": {"policy": POLICY, "approvals": approvals, "delivery": delivery},
             "_autonomy_authority": autonomy.WRITER_AUTHORITY}]


def export(root, source_revision=None):
    """Private projector input, including exact bytes to bridge number encodings."""
    from .live_tower import build_live_tower_payload
    records, roadmaps, raw_tests = source_records(root)
    by_id = {record["id"]: record for record in [*records["roadmaps"], *records["tests"]]}
    registry = autonomy.read(root, REGISTRY)
    approvals = []
    if registry.get("policy") == POLICY:
        for entry in registry.get("approvals") or []:
            source = by_id.get(entry.get("sourceId"))
            if not source or entry.get("writerSourceSha256") != commitment(source)["sha256"]:
                continue
            value = dict(entry)
            if value.get("kind") == "TEST":
                proof = independent_proof(root, raw_tests[source["id"]], source)
                value.pop("independence", None)
                if proof:
                    value["independence"] = proof
                else:
                    value["presentation"] = {key: field for key, field in value.get("presentation", {}).items() if key != "result"}
            approvals.append(value)
    return {"records": records, "approvals": approvals,
            "source_commitments": {key: commitment(value) for key, value in by_id.items()},
            "meta": {"sourceRevision": source_revision or build_live_tower_payload(root)["state_fingerprint"],
                     "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--root", type=Path)
    source.add_argument("--tower", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.root:
        value = export(args.root)
    else:
        from .live_tower import materialize_live_tower, read_live_tower_bytes, verify_live_tower
        raw = args.tower.read_bytes()
        revision = verify_live_tower(read_live_tower_bytes(raw))
        with tempfile.TemporaryDirectory(prefix="nexo-public-input-") as work:
            root, _ = materialize_live_tower(raw, Path(work) / "tower")
            value = export(root, revision)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded(value) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PRIVATE_PROJECTOR_INPUT_READY", "approvals": len(value["approvals"]),
                      "source_revision": value["meta"]["sourceRevision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
