from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import validate_snapshot

SECTIONS=("projects","work","tests","knowledge","relations","decisions","olympus_summary")

def write_json(path: Path,payload: Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")

def _nodes(rows:list[dict[str,Any]])->list[dict[str,str]]:
    out=[]
    for row in rows:
        rid=str(row.get("id") or row.get("record_id") or row.get("work_id") or row.get("relation_id") or "")
        if rid: out.append({"id":rid,"label":str(row.get("label") or row.get("title") or row.get("question") or rid)})
    return out

def materialize_view(snapshot:dict[str,Any],output_dir:str|Path)->dict[str,Any]:
    errors=validate_snapshot(snapshot)
    if errors: raise ValueError("; ".join(errors))
    root=Path(output_dir)/"api"/"v1"
    write_json(root/"snapshot.json",snapshot)
    write_json(root/"health.json",{"ok":True,"schema_version":snapshot["schema_version"],"ssot_revision":snapshot["ssot_revision"],"state_hash":snapshot["state_hash"],"generated_at":snapshot["generated_at"]})
    for name in SECTIONS: write_json(root/f"{name.replace('_','-')}.json",snapshot.get(name,[]))
    graphs={"science":{"graph_id":"science","nodes":_nodes(snapshot.get("projects",[])),"edges":[]},"clients":{"graph_id":"clients","nodes":_nodes(snapshot.get("olympus_summary",[])),"edges":[]},"relations":{"graph_id":"relations","nodes":_nodes(snapshot.get("relations",[])),"edges":[]}}
    write_json(root/"graphs"/"catalog.json",{"graphs":[{"graph_id":k,"data_ref":f"/api/v1/graphs/{k}.json"} for k in graphs]})
    for key,payload in graphs.items(): write_json(root/"graphs"/f"{key}.json",payload)
    return {"state_hash":snapshot["state_hash"],"ssot_revision":snapshot["ssot_revision"],"graph_count":len(graphs)}
