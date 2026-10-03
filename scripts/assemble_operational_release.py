"""One-time exact integration of the reviewed operational runtime into PR128.

Runs only on the authorized release branch. No Drive, Tower, or credential I/O.
"""
from pathlib import Path
import hashlib


def load(name, expected):
    path=Path(name);raw=path.read_bytes()
    actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if actual!=expected:raise RuntimeError('SOURCE_DRIFT:'+name)
    return path,raw.decode()


def replace(text,old,new):
    if text.count(old)!=1:raise RuntimeError('PATCH_ANCHOR_MISMATCH:'+old[:80])
    return text.replace(old,new,1)

p,s=load('runtime/nexo_agent_api/gpt_writer.py','e62dcb62e4a0136a7ea9015af783662a6926bde7')
s=replace(s,'                       operational_receipt_validated: bool = False) -> dict:', '''                       operational_receipt_validated: bool = False,
                       operational_work_authorized: bool = False) -> dict:
    changes = request.get("changes") or {}
    reserved = (changes.get("kind") == "NEXO_OPERATIONAL_WORK_V1"
                or str(request.get("entity_name") or "").startswith("OPERATIONAL-CONTROL-"))
    if reserved and not operational_work_authorized:
        return {"accepted": False, "issue": {"code": "OPERATIONAL_WORK_REQUIRES_WRITER_SERVICE"}}''')
s=replace(s,'def apply_to_tower(tower_raw: bytes, items: list[dict], *, readiness_evaluator=None) -> tuple[bytes | None, dict]:',
 'def apply_to_tower(tower_raw: bytes, items: list[dict], *, readiness_evaluator=None, operational_work_authorized: bool = False) -> tuple[bytes | None, dict]:')
s=replace(s,'                    operational_receipt_validated=operational_receipt_validated,','                    operational_receipt_validated=operational_receipt_validated,\n                    operational_work_authorized=operational_work_authorized,')
s=replace(s,'        dispatch_dir = os.environ.get("NEXO_BATTERY_DIR", "")', '''        # Operational work shares the existing Writer, credential and concurrency.
        try:
            from .operational_tick import tick_existing_writer
            operational_report = tick_existing_writer(tower, os.environ)
            print(json.dumps({"operational_worker": operational_report}, ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"operational_worker": "ITEMS_DEFERRED",
                              "error_type": type(exc).__name__,
                              "code": getattr(exc, "code", type(exc).__name__)}))
        items = [item for item in items if item.get("contract") != "NEXO_OPERATIONAL_INTENT_V1"]
        dispatch_dir = os.environ.get("NEXO_BATTERY_DIR", "")''')
p.write_text(s,encoding='utf-8',newline='\n')

p,s=load('runtime/nexo_agent_api/inbox_apply.py','4f4355358e605506f79833c1def33a3f072288d5')
s=replace(s,'    """Admit one runner-bound engineering receipt without creating a TEST."""','    """Admit one runner-bound engineering receipt without creating a TEST."""\n    from .operational_prompts import EXECUTOR_PROMPT_HASHES')
s=replace(s,'session.get("prompt_sha256") != "47fe9079dc26f58ef206be163edb963c572199e923218bc79984172787520484"','session.get("prompt_sha256") not in EXECUTOR_PROMPT_HASHES')
p.write_text(s,encoding='utf-8',newline='\n')

p=Path('runtime/nexo_agent_api/operational_control.py');s=p.read_text()
s=replace(s,'        verify_live_tower(data)\n        return raw, head, data', '''        fingerprint = verify_live_tower(data)
        require(data.get("revision") == data.get("state_fingerprint") == fingerprint, "OPERATIONAL_TOWER_HASH_MISMATCH")
        require(data.get("stable_file_id") == "1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z", "OPERATIONAL_TOWER_ID_MISMATCH")
        return raw, head, data''')
p.write_text(s,encoding='utf-8',newline='\n')
print('Integrated reserved operational state and short prompts; scientific criteria unchanged.')
