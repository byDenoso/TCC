from __future__ import annotations

from copy import deepcopy
from typing import Any

SUMMARY_FIELDS = ("id","record_id","label","title","status","program","detail","checkin_status","freshness","next_action")

def public_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out=[]
    for row in rows:
        item={k:row[k] for k in SUMMARY_FIELDS if row.get(k) not in (None,"")}
        item.setdefault("id", item.get("record_id"))
        item.setdefault("label", item.get("title"))
        item.pop("record_id",None); item.pop("title",None)
        out.append(item)
    return out

def project_public(snapshot: dict[str, Any]) -> dict[str, Any]:
    out=deepcopy(snapshot)
    private_rows=out.pop("olympus", [])
    if private_rows:
        out["olympus_summary"]=public_summary(private_rows)
    return out
