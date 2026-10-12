"""Read-only, private per-role context deltas; no queue/execution authority."""
from __future__ import annotations

import json
from pathlib import PurePosixPath

from .memory import Snapshot, digest
from .control_compat import control_from_bundle, BOOTSTRAP_FIELDS

SCHEMA = 'NEXO_ROLE_CONTEXT_DELTA_V1'
ALIASES = {'ENGINEER':'ADVISOR','REFEREE_1':'REFUTADOR'}
ROLES = {'DAILY','ADVISOR','EXECUTOR','LEARNER','EMERGENT','ENGINEER','REFEREE_1','REFUTADOR','GUARDIAO','PITIA','SENTINEL'}


def _path(path):
    if (not isinstance(path,str) or not path or PurePosixPath(path).is_absolute() or '\\' in path
            or any(part in {'','..','.'} for part in path.split('/'))):
        raise ValueError('CONTEXT_PATH_INVALID')
    return path


def prepare_context(snapshot: Snapshot, role: str, *, cursor: dict | None = None,
                    target_refs: list[str] | None = None) -> dict:
    role = role.upper()
    if role not in ROLES:
        raise ValueError('CONTEXT_ROLE_INVALID')
    control = control_from_bundle(snapshot.payload)
    files = snapshot.payload['files']
    selected = {}
    handoffs = {}
    aliases = {role, ALIASES.get(role,role), *[key for key,value in ALIASES.items() if value==role]}
    locations = {}
    def add(path, item, source_path=None):
        selected[path] = item
        locations[path] = source_path or path
    board = files.get('evolution/board.json',{}).get('value',{})
    for post in board.get('posts') or []:
        if isinstance(post,dict) and post.get('id') and str(post.get('to') or '').upper() in aliases | {'ALL'}:
            add('board:'+str(post['id']),post,'evolution/board.json')
    for path in sorted(files):
        entry = files[path]
        if not isinstance(entry,dict) or entry.get('encoding')!='json' or not isinstance(entry.get('value'),dict):
            continue
        value=entry['value']
        if path.startswith('events/') and value.get('handoff_id'):
            handoffs[str(value['handoff_id'])] = (path,value)
        elif path.startswith('entities/handoff/'):
            recipient=str(value.get('recipient_role') or value.get('recipient') or '').upper()
            if recipient in aliases:
                add(path,value)
        elif path.startswith('entities/work/') and str(value.get('owner_role') or '').upper() in aliases:
            if value.get('status') in {'READY','RUNNING','CHECKPOINTED','WAIT_DEPENDENCY','VERIFIED'}:
                add(path,value)
    # Canonical handoffs live in events, not just entity-shaped compatibility
    # records. Match the existing protocol's logical-path ordering and include
    # terminal changes so cursors cannot hide ACK/DONE/FAILED transitions.
    for identity,(source_path,value) in handoffs.items():
        if str(value.get('to_role') or '').upper() in aliases:
            add('handoff:'+identity,value,source_path)
    for path in sorted(set(target_refs or [])):
        _path(path)
        entry=files.get(path)
        if not isinstance(entry,dict):
            raise ValueError('CONTEXT_TARGET_UNAVAILABLE')
        add(path,entry)
    # This fingerprint invalidates deltas when security-relevant compatibility
    # fields or authority change; it does not authorize execution or a write.
    authority={key:control[key] for key in sorted(BOOTSTRAP_FIELDS | {'autonomy_mandate','revoked_autonomy_mandates'}) if key in control}
    hashes={key:digest(value) for key,value in sorted(selected.items())}
    scope=digest({'role':role,'target_refs':sorted(set(target_refs or []))})
    prior={}
    cursor_valid=(isinstance(cursor,dict) and cursor.get('schema')==SCHEMA
                  and cursor.get('source_id')==snapshot.source_id and cursor.get('scope')==scope
                  and cursor.get('authority_sha256')==digest(authority)
                  and isinstance(cursor.get('hashes'),dict))
    if cursor_valid:
        prior=cursor['hashes']
    changed={}
    for key,value in sorted(selected.items()):
        if prior.get(key)==hashes[key]:
            continue
        if key.startswith(('handoff:','entities/handoff/')):
            fields=('handoff_id','event_id','state','from_role','to_role','handoff_type','entity_ref',
                    'entity_version','opened_at','created_at','recovery_fingerprint','request_id')
            payload={field:value[field] for field in fields if field in value}
        elif key.startswith('entities/work/') and key not in set(target_refs or []):
            fields=('id','status','owner_role','priority','entity_version','title','kind','target_domain')
            payload={field:value[field] for field in fields if field in value}
        else:
            payload=value
        changed[key]={'value':payload,'source_path':locations[key],'content_sha256':hashes[key],
                      'full_payload':payload is value}

    removed=sorted(set(prior)-set(hashes))
    next_cursor={'schema':SCHEMA,'source_id':snapshot.source_id,'scope':scope,
                 'authority_sha256':digest(authority),'hashes':hashes}
    return {'schema':SCHEMA,'visibility':'PRIVATE','role':role,'source_id':snapshot.source_id,
            'tower_revision':snapshot.revision,'changed':changed,'removed':removed,
            'cursor_reset':not cursor_valid,'cursor':next_cursor,
            'control_reference':{'source':'CANONICAL_COMPAT_VIEW','authority_sha256':digest(authority)},
            'context_changed':bool(changed or removed or not cursor_valid),
            'execution_authorization':False,'absence_proof':False,
            'mcp_required':False,'writes_canonical_state':False}


def main(argv):
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser(description='Private role context deltas, not execution authorization')
    parser.add_argument('tower');parser.add_argument('role');parser.add_argument('output')
    parser.add_argument('--cursor');parser.add_argument('--target',action='append',default=[])
    args=parser.parse_args(argv)
    cursor=json.loads(Path(args.cursor).read_text()) if args.cursor else None
    if isinstance(cursor,dict) and isinstance(cursor.get('cursor'),dict):
        cursor=cursor['cursor']
    result=prepare_context(Snapshot.read(args.tower),args.role,cursor=cursor,target_refs=args.target)
    from .tower_gc_cli import _write_private
    _write_private(args.output,json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2).encode()+b'\n')
    print(json.dumps({'status':'CONTEXT_DELTA','changed':len(result['changed']),'removed':len(result['removed']),
                      'cursor_reset':result['cursor_reset'],'execution_authorization':False}))
    return 0
