from __future__ import annotations

from typing import Any
from .schema import normalize_record

SECTIONS = ("projects","work","tests","events","knowledge","relations","decisions","olympus_summary")
VOLATILE = {"source","updated_at","generated_at"}

def _idx(rows: Any) -> dict[str, dict[str, Any]]:
    out = {}
    for raw in rows if isinstance(rows, list) else []:
        if not isinstance(raw, dict):
            continue
        row = normalize_record(raw)
        if row.get("id"):
            out[str(row["id"])] = row
    return out

def _version(row: dict[str, Any] | None) -> int:
    try:
        return max(int((row or {}).get("entity_version", 0)), 0)
    except (TypeError, ValueError):
        return 0

def _clean(row: dict[str, Any]) -> dict[str, Any]:
    return {k:v for k,v in row.items() if k not in VOLATILE}

def _merge(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    out = {**secondary, **primary}
    out.pop("source", None)
    return out

def _resolve(section: str, rid: str, drive: dict[str, Any] | None, git: dict[str, Any] | None) -> dict[str, Any]:
    if drive is None:
        return {"section":section,"record_id":rid,"status":"GIT_ONLY","reason":"GitHub only","resolved":_merge(git or {}, {})}
    if git is None:
        return {"section":section,"record_id":rid,"status":"DRIVE_ONLY","reason":"Drive only","resolved":_merge(drive, {})}
    if _clean(drive) == _clean(git):
        return {"section":section,"record_id":rid,"status":"EQUAL","reason":"materially equal","resolved":_merge(git, drive)}
    if section == "olympus_summary":
        return {"section":section,"record_id":rid,"status":"MERGED","reason":"Drive owns Olympus state","resolved":_merge(drive, git)}
    if section == "tests":
        dv = drive.get("status") == "VERIFIED" and drive.get("verification") in (None,"PASS")
        gv = git.get("status") == "VERIFIED" and git.get("verification") in (None,"PASS")
        if dv != gv:
            return {"section":section,"record_id":rid,"status":"MERGED","reason":"verified result wins","resolved":_merge(drive if dv else git, git if dv else drive)}
    if section in {"work","relations","tests"} and _version(drive) != _version(git):
        primary, secondary = (drive, git) if _version(drive) > _version(git) else (git, drive)
        return {"section":section,"record_id":rid,"status":"MERGED","reason":"higher entity_version wins","resolved":_merge(primary, secondary)}
    return {"section":section,"record_id":rid,"status":"CONFLICT","reason":"no safe precedence rule","drive":drive,"git":git,"resolved":None}

def reconcile_exports(drive_export: dict[str, Any], tower_export: dict[str, Any]) -> dict[str, Any]:
    candidate = {s:[] for s in SECTIONS}
    items = []
    for section in SECTIONS:
        d, g = _idx(drive_export.get(section, [])), _idx(tower_export.get(section, []))
        for rid in sorted(set(d) | set(g)):
            item = _resolve(section, rid, d.get(rid), g.get(rid))
            items.append(item)
            if item["resolved"] is not None:
                candidate[section].append(item["resolved"])
    conflicts = sum(1 for item in items if item["status"] == "CONFLICT")
    return {"candidate":candidate,"items":items,"material_conflict_count":conflicts,"status":"PASS" if conflicts == 0 else "CONFLICT"}
