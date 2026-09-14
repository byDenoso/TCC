from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import validate_snapshot

SECTIONS=("projects","work","tests","knowledge","relations","decisions","olympus_summary")

def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")

def materialize_view(snapshot: dict[str,Any], output_dir: str|Path) -> dict[str,Any]:
    errors=validate_snapshot(snapshot)
    if errors: raise ValueError("; ".join(errors))
    root=Path(output_dir)/"api"/"v1"
    write_json(root/"snapshot.json",snapshot)
    write_json(root/"health.json",{"ok":True,"schema_version":snapshot["schema_version"],"ssot_revision":snapshot["ssot_revision"],"state_hash":snapshot["state_hash"],"generated_at":snapshot["generated_at"]})
    for name in SECTIONS:
        write_json(root/f"{name.replace('_','-')}.json",snapshot.get(name,[]))
    catalog={"graphs":[{"graph_id":"science","data_ref":"/api/v1/graphs/science.json"},{"graph_id":"clients","data_ref":"/api/v1/graphs/clients.json"},{"graph_id":"relations","data_ref":"/api/v1/graphs/relations.json"}]}
    write_json(root/"graphs"/"catalog.json",catalog)
    return {"state_hash":snapshot["state_hash"],"ssot_revision":snapshot["ssot_revision"]}
