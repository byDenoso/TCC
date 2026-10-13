"""Read-only, private per-role context deltas; no queue/execution authority."""
from __future__ import annotations

import json
import re
import time
from pathlib import PurePosixPath

from .memory import Snapshot, digest, clean
from .control_compat import control_from_bundle, BOOTSTRAP_FIELDS
from .work_queue import derive_work_queue

SCHEMA = 'NEXO_ROLE_CONTEXT_DELTA_V1'
ALIASES = {'ENGINEER':'ADVISOR','REFEREE_1':'REFUTADOR'}
ROLES = {'DAILY','ADVISOR','EXECUTOR','LEARNER','EMERGENT','ENGINEER','REFEREE_1','REFUTADOR','GUARDIAO','PITIA','SENTINEL'}


def _path(path):
    if (not isinstance(path,str) or not path or PurePosixPath(path).is_absolute() or '\\' in path
            or any(part in {'','..','.'} for part in path.split('/'))):
        raise ValueError('CONTEXT_PATH_INVALID')
    return path


def _acl_allows(value, aliases):
    acl = value.get('allowed_roles')
    if acl is None:
        return True
    if not isinstance(acl, list) or any(not isinstance(item, str) for item in acl):
        raise ValueError('CONTEXT_ACL_INVALID')
    return bool(aliases.intersection(item.upper() for item in acl))


def _target_entry(path, entry, aliases):
    value = entry.get('value')
    if entry.get('encoding') != 'json' or not isinstance(value, dict):
        raise ValueError('CONTEXT_TARGET_FORBIDDEN')
    if path == 'evolution/board.json':
        posts = [clean(post) for post in value.get('posts') or []
                 if isinstance(post, dict) and str(post.get('to') or '').upper() in aliases | {'ALL'}
                 and _acl_allows(post, aliases)]
        return {'encoding': 'json', 'value': {'posts': posts}}
    parts = path.split('/')
    entity = len(parts) == 3 and parts[0] == 'entities' and parts[1] in {
        'test', 'run', 'result', 'evidence', 'artifact', 'work', 'handoff', 'recipe'}
    scientific = len(parts) == 3 and parts[:2] in [
        ['runtime', 'runs'], ['runtime', 'results'], ['runtime', 'evidence'], ['runtime', 'artifacts']]
    recipe = len(parts) == 2 and parts[0] == 'recipes'
    handoff_event = path.startswith('events/') and bool(value.get('handoff_id'))
    if not (entity or scientific or recipe or handoff_event) or not _acl_allows(value, aliases):
        raise ValueError('CONTEXT_TARGET_FORBIDDEN')
    recipient = str(value.get('to_role') or value.get('recipient_role') or value.get('recipient') or '').upper()
    if handoff_event or entity and parts[1] == 'handoff':
        if recipient not in aliases:
            raise ValueError('CONTEXT_TARGET_FORBIDDEN')
    elif entity and parts[1] == 'work':
        if str(value.get('owner_role') or '').upper() not in aliases:
            raise ValueError('CONTEXT_TARGET_FORBIDDEN')
    elif value.get('private') is True and value.get('allowed_roles') is None:
        recipient = str(value.get('to') or value.get('owner_role') or value.get('writer_role') or '').upper()
        if recipient not in aliases:
            raise ValueError('CONTEXT_TARGET_FORBIDDEN')
    return {'encoding': 'json', 'value': clean(value)}


def prepare_context(snapshot: Snapshot, role: str, *, cursor: dict | None = None,
                    target_refs: list[str] | None = None) -> dict:
    started = time.perf_counter()
    role = role.upper()
    if role not in ROLES:
        raise ValueError('CONTEXT_ROLE_INVALID')
    control = control_from_bundle(snapshot.payload)
    files = snapshot.payload['files']
    selected = {}
    handoffs = {}
    work_files = {}
    aliases = {role, ALIASES.get(role,role), *[key for key,value in ALIASES.items() if value==role]}
    locations = {}
    def add(path, item, source_path=None):
        selected[path] = item
        locations[path] = source_path or path
    board = files.get('evolution/board.json',{}).get('value',{})
    for post in board.get('posts') or []:
        if isinstance(post,dict) and post.get('id') and str(post.get('to') or '').upper() in aliases | {'ALL'} and _acl_allows(post, aliases):
            add('board:'+str(post['id']),clean(post),'evolution/board.json')
    for path in sorted(files):
        entry = files[path]
        if not isinstance(entry,dict) or entry.get('encoding')!='json' or not isinstance(entry.get('value'),dict):
            continue
        value=entry['value']
        if path.startswith('events/') and value.get('handoff_id'):
            handoffs[str(value['handoff_id'])] = (path,value)
        elif path.startswith('entities/handoff/'):
            recipient=str(value.get('recipient_role') or value.get('recipient') or '').upper()
            if recipient in aliases and _acl_allows(value, aliases):
                add(path,value)
        elif path.startswith('entities/work/'):
            work_files[path]=value
            if (str(value.get('owner_role') or '').upper() in aliases
                    and value.get('status') in {'READY','RUNNING','CHECKPOINTED','WAIT_DEPENDENCY'} and _acl_allows(value, aliases)):
                add(path,value)
    # Canonical handoffs live in events, not just entity-shaped compatibility
    # records. Match the existing protocol's logical-path ordering and include
    # terminal changes so cursors cannot hide ACK/DONE/FAILED transitions.
    for identity,(source_path,value) in handoffs.items():
        if str(value.get('to_role') or '').upper() in aliases and _acl_allows(value, aliases):
            add('handoff:'+identity,value,source_path)
    # WORK entities outlive board retention. Derive obligations once with a
    # shared policy, then apply the same ownership and ACL boundary as context.
    event_by_id = {identity: value for identity, (_, value) in handoffs.items()}
    work_by_id = {str(value.get('id')):value for value in work_files.values()}
    for row in derive_work_queue(files, handoffs=handoffs, work_files=work_files):
        # Terminal rows remain available in the shared audit view, but their
        # removal from role cursors closes the obligation without reloading
        # all historic DONE/VERIFIED work on every recovery/bootstrap.
        if row['first_exclusion_reason']=='WORK_TERMINAL':
            continue
        work = files[row['source_path']]['value']
        recovery = work.get('recovery') or {}
        target = str(recovery.get('target_role') or '').upper() if isinstance(recovery,dict) else ''
        if (str(work.get('owner_role') or '').upper() in aliases or target in aliases) and _acl_allows(work, aliases):
            accepted_ids = row['accepted_handoff_ids']
            row['accepted_handoff_ids'] = [identity for identity in accepted_ids if _acl_allows(event_by_id[identity], aliases)]
            if accepted_ids and not row['accepted_handoff_ids']:
                row['acceptance']='UNAVAILABLE'
                row.update(actionable=False,first_exclusion_reason='ACCEPTANCE_CONTEXT_UNAVAILABLE')
            dependencies=[]
            for dependency in row['dependencies']:
                linked=work_by_id.get(dependency['ref'])
                if linked and (str(linked.get('owner_role') or '').upper() not in aliases or not _acl_allows(linked,aliases)):
                    dependencies.append({'visibility':'WITHHELD','satisfied':False})
                    row.update(actionable=False,first_exclusion_reason='DEPENDENCY_CONTEXT_UNAVAILABLE')
                else:
                    dependencies.append(dependency)
            row['dependencies']=dependencies
            add('work_queue:'+row['id'], clean(row), row['source_path'])
    for path in sorted(set(target_refs or [])):
        _path(path)
        entry=files.get(path)
        if not isinstance(entry,dict):
            raise ValueError('CONTEXT_TARGET_UNAVAILABLE')
        add(path,_target_entry(path,entry,aliases))
    # This fingerprint invalidates deltas when security-relevant compatibility
    # fields or authority change; it does not authorize execution or a write.
    authority={key:control[key] for key in sorted(BOOTSTRAP_FIELDS | {'autonomy_mandate','revoked_autonomy_mandates'}) if key in control}
    hashes={key:digest(value) for key,value in sorted(selected.items())}
    scope=digest({'role':role,'target_refs':sorted(set(target_refs or []))})
    prior={}
    cursor_valid=(isinstance(cursor,dict) and cursor.get('schema')==SCHEMA
                  and cursor.get('source_id')==snapshot.source_id and cursor.get('scope')==scope
                  and cursor.get('authority_sha256')==digest(authority)
                  and isinstance(cursor.get('hashes'),dict)
                  and all(isinstance(key,str) and isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value)
                          for key,value in cursor['hashes'].items())
                  and cursor.get('cursor_sha256')==digest({key:value for key,value in cursor.items() if key!='cursor_sha256'}))
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
    next_cursor['cursor_sha256']=digest(next_cursor)
    return {'schema':SCHEMA,'visibility':'PRIVATE','role':role,'source_id':snapshot.source_id,
            'tower_revision':snapshot.revision,'changed':changed,'removed':removed,
            'cursor_reset':not cursor_valid,'cursor':next_cursor,
            'control_reference':{'source':'CANONICAL_COMPAT_VIEW','authority_sha256':digest(authority)},
            'context_changed':bool(changed or removed or not cursor_valid),
            'metrics':{'source_files':len(files),'selected_items':len(selected),
                       'changed_items':len(changed),
                       'selected_bytes':len(json.dumps(selected,ensure_ascii=False,sort_keys=True).encode('utf-8')),
                       'changed_bytes':len(json.dumps(changed,ensure_ascii=False,sort_keys=True).encode('utf-8')),
                       'context_elapsed_ms':(time.perf_counter()-started)*1000},
            'execution_authorization':False,'absence_proof':False,
            'mcp_required':False,'writes_canonical_state':False}


def main(argv):
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser(description='Private role context deltas, not execution authorization')
    parser.add_argument('tower');parser.add_argument('role');parser.add_argument('output')
    parser.add_argument('--cursor');parser.add_argument('--target',action='append',default=[])
    args=parser.parse_args(argv)
    cursor=None
    cursor_recovery=None
    if args.cursor:
        try:
            cursor=json.loads(Path(args.cursor).read_text(encoding='utf-8'))
        except FileNotFoundError:
            cursor_recovery='CURSOR_UNAVAILABLE'
        except (ValueError,UnicodeError):
            cursor_recovery='CURSOR_INVALID'
    if isinstance(cursor,dict) and isinstance(cursor.get('cursor'),dict):
        cursor=cursor['cursor']
    result=prepare_context(Snapshot.read(args.tower),args.role,cursor=cursor,target_refs=args.target)
    if cursor_recovery:
        result['cursor_recovery']=cursor_recovery
    from .tower_gc_cli import _write_private
    _write_private(args.output,json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2).encode()+b'\n')
    print(json.dumps({'status':'CONTEXT_DELTA','changed':len(result['changed']),'removed':len(result['removed']),
                      'cursor_reset':result['cursor_reset'],'execution_authorization':False}))
    return 0
