"""Small derived CONTROL view during migration; never a second authority.

Legacy CONTROL remains supported. Its physical removal is a separate reviewed
migration. Rehearsals preserve the full old bytes in private history and route
mandates/revocations to a protected document, identity to the Tower header and
only consumed operational fields to a small policy record.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

POLICY_PATH = 'runtime/executor_policy.json'
AUTHORITY_PATH = 'evolution/autonomy_authority.json'
SOURCE_HEADER = 'LIVE_TOWER_HEADER_LOCAL.json'
POLICY_SCHEMA = 'NEXO_EXECUTOR_POLICY_V1'
AUTHORITY_SCHEMA = 'NEXO_AUTONOMY_AUTHORITY_V1'
IDENTITY_FIELDS = {'truth_owner', 'write_model', 'drive_live_tower_file_id'}
AUTHORITY_FIELDS = {'autonomy_mandate', 'revoked_autonomy_mandates'}
POLICY_FIELDS = frozenset({
    'mode', 'write_guard', 'derived_indexes_authority', 'atlas_role', 'drive_role',
    'runtime_revision', 'scientific_runtime', 'github_actions_science_role',
    'git_operational_write_state', 'canonical_read_policy', 'sol_context_policy',
})
BOOTSTRAP_FIELDS = IDENTITY_FIELDS | POLICY_FIELDS


class ControlCompatibilityError(ValueError):
    pass


def _read(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ControlCompatibilityError('CONTROL_COMPAT_READ_FAILED') from exc
    if not isinstance(value, dict):
        raise ControlCompatibilityError('CONTROL_COMPAT_NOT_OBJECT')
    return value


def _identity(header):
    if (header.get('contract') != 'NEXO_TOWER_LIVE_V1' or header.get('authority') != 'TOWER_V06'
            or header.get('storage') != 'GOOGLE_DRIVE_PRIVATE'
            or header.get('truth_owner') != 'TOWER_V06@GOOGLE_DRIVE_PRIVATE'
            or header.get('write_model') != 'IN_PLACE_FILE_REVISION_CAS_READBACK'
            or header.get('stable_file_id') != '1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z'):
        raise ControlCompatibilityError('CONTROL_COMPAT_AUTHORITY_INVALID')
    return {'truth_owner': header['truth_owner'], 'write_model': header['write_model'],
            'drive_live_tower_file_id': header['stable_file_id']}


def _derived(header, policy, authority):
    identity = _identity(header)
    if (policy.get('schema') != POLICY_SCHEMA or authority.get('schema') != AUTHORITY_SCHEMA
            or set(policy) - {'schema', 'fields', 'legacy_sha256'}
            or set(authority) - {'schema', 'legacy_sha256', *AUTHORITY_FIELDS}
            or not isinstance(policy.get('fields'), dict)
            or set(policy['fields']) - POLICY_FIELDS
            or not isinstance(policy.get('legacy_sha256'), str)
            or len(policy['legacy_sha256']) != 64
            or policy['legacy_sha256'] != authority.get('legacy_sha256')
            or not isinstance(authority.get('revoked_autonomy_mandates'), list)
            or any(not isinstance(v, str) for v in authority['revoked_autonomy_mandates'])
            or not isinstance(authority.get('autonomy_mandate'), dict)):
        raise ControlCompatibilityError('CONTROL_COMPAT_COMPONENT_INVALID')
    return {**policy['fields'], **identity,
            **{key: copy.deepcopy(authority[key]) for key in AUTHORITY_FIELDS}}


def _verify_history(entry, legacy_sha256):
    if (not isinstance(entry, dict) or entry.get('encoding') != 'json'
            or not isinstance(entry.get('value'), dict)
            or hashlib.sha256(json.dumps(entry,ensure_ascii=False,sort_keys=True,
                                         separators=(',', ':')).encode()).hexdigest() != legacy_sha256):
        raise ControlCompatibilityError('CONTROL_COMPAT_HISTORY_INVALID')


def control_from_bundle(bundle):
    files = bundle.get('files') or {}
    entry = files.get('CONTROL.json')
    if entry is not None:
        control = entry.get('value') if isinstance(entry, dict) and entry.get('encoding') == 'json' else None
        if not isinstance(control, dict) or control.get('truth_owner') != bundle.get('truth_owner'):
            raise ControlCompatibilityError('CONTROL_AND_TOWER_AUTHORITY_DISAGREE')
        if AUTHORITY_PATH in files or POLICY_PATH in files:
            raise ControlCompatibilityError('CONTROL_COMPAT_DUAL_AUTHORITY')
        return copy.deepcopy(control)
    def value(path):
        entry = files.get(path)
        if not isinstance(entry, dict) or entry.get('encoding') != 'json' or not isinstance(entry.get('value'), dict):
            raise ControlCompatibilityError('CONTROL_COMPAT_COMPONENT_MISSING')
        return entry['value']
    policy, authority = value(POLICY_PATH), value(AUTHORITY_PATH)
    control = _derived(bundle, policy, authority)
    historical = 'events/migrations/control-' + policy['legacy_sha256'] + '.json'
    _verify_history(files.get(historical), policy['legacy_sha256'])
    return control


def read_control_compat(root):
    root = Path(root)
    path = root / 'CONTROL.json'
    if path.exists():
        if (root / AUTHORITY_PATH).exists() or (root / POLICY_PATH).exists():
            raise ControlCompatibilityError('CONTROL_COMPAT_DUAL_AUTHORITY')
        return _read(path)
    policy, authority = _read(root / POLICY_PATH), _read(root / AUTHORITY_PATH)
    control = _derived(_read(root / SOURCE_HEADER), policy, authority)
    historical = 'events/migrations/control-' + policy['legacy_sha256'] + '.json'
    _verify_history({'encoding':'json','value':_read(root / historical)}, policy['legacy_sha256'])
    return control


def authority_document(root):
    return AUTHORITY_PATH if not (Path(root) / 'CONTROL.json').exists() else 'CONTROL.json'


def bootstrap_control(root):
    control = read_control_compat(root)
    return {key: control[key] for key in sorted(BOOTSTRAP_FIELDS) if key in control}


def prepare_migration(raw):
    """Offline compatibility rehearsal only; never activates physical retirement."""
    from .live_tower import read_live_tower_bytes, verify_live_tower
    bundle = read_live_tower_bytes(raw)
    before = verify_live_tower(bundle)
    control = control_from_bundle(bundle)
    if 'CONTROL.json' not in bundle['files']:
        return raw, {'status': 'NO_OP', 'before': before, 'after': before}
    old_entry = bundle['files']['CONTROL.json']
    original = json.dumps(old_entry, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    digest = hashlib.sha256(original).hexdigest()
    candidate = copy.deepcopy(bundle)
    historical = 'events/migrations/control-' + digest + '.json'
    if historical in candidate['files'] and candidate['files'][historical] != old_entry:
        raise ControlCompatibilityError('CONTROL_HISTORY_COLLISION')
    candidate['files'][historical] = copy.deepcopy(old_entry)
    candidate['files'][POLICY_PATH] = {'encoding':'json','value':{
        'schema': POLICY_SCHEMA, 'legacy_sha256':digest,
        'fields':{key:copy.deepcopy(control[key]) for key in sorted(POLICY_FIELDS) if key in control}}}
    candidate['files'][AUTHORITY_PATH] = {'encoding':'json','value':{
        'schema':AUTHORITY_SCHEMA,'legacy_sha256':digest,
        'autonomy_mandate':copy.deepcopy(control.get('autonomy_mandate') or {}),
        'revoked_autonomy_mandates':copy.deepcopy(control.get('revoked_autonomy_mandates') or [])}}
    candidate['files'].pop('CONTROL.json')
    actual = control_from_bundle(candidate)
    for key in AUTHORITY_FIELDS | POLICY_FIELDS | IDENTITY_FIELDS:
        if key in control and actual.get(key) != control[key]:
            raise ControlCompatibilityError('CONTROL_MIGRATION_PARITY_FAILED')
    files_raw = json.dumps(candidate['files'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    after = 'sha256:' + hashlib.sha256(files_raw).hexdigest()
    candidate.update(file_count=len(candidate['files']),revision=after,state_fingerprint=after)
    result = json.dumps(candidate,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()+b'\n'
    verify_live_tower(candidate)
    return result, {'status':'REHEARSAL_NOT_ACTIVE','before':before,'after':after,
                    'retained_history':historical,'legacy_fields':len(control),'policy_fields':len(candidate['files'][POLICY_PATH]['value']['fields']),
                    'unmapped_legacy_keys':sorted(set(control)-AUTHORITY_FIELDS-POLICY_FIELDS-IDENTITY_FIELDS),
                    'promotion':'REQUIRES_CONSUMER_COVERAGE_AND_INDEPENDENT_REVIEW'}


def inventory_consumers(raw, source_roots):
    """Static hints with file hashes; zero matches never prove a key unused."""
    import ast
    from collections import defaultdict
    from .live_tower import read_live_tower_bytes, verify_live_tower
    bundle=read_live_tower_bytes(raw)
    revision=verify_live_tower(bundle)
    control=control_from_bundle(bundle)
    hints=defaultdict(list)
    sources=[]
    for source_root in source_roots:
        root=Path(source_root)
        for path in sorted(root.rglob('*')):
            if not path.is_file() or path.suffix not in {'.py','.js','.ts','.tsx'} or any(p in {'.git','node_modules','__pycache__'} for p in path.parts):
                continue
            body=path.read_bytes()
            source={'root':root.name,'path':path.relative_to(root).as_posix(),'sha256':hashlib.sha256(body).hexdigest()}
            sources.append(source)
            text=body.decode('utf-8')
            if path.suffix=='.py':
                try:tree=ast.parse(text)
                except SyntaxError:continue
                references=[(node.value,node.lineno) for node in ast.walk(tree) if isinstance(node,ast.Constant) and isinstance(node.value,str)]
            else:
                import re
                references=[(m.group(2),text.count('\n',0,m.start())+1) for m in re.finditer(r'([\'\"])([^\'\"\n]+)\1',text)]
            for value,line in references:
                if value in control:
                    hints[value].append({**source,'line':line,'kind':'STATIC_HINT_NOT_COMPLETE_COVERAGE'})
    return {'schema':'NEXO_CONTROL_CONSUMER_INVENTORY_V1','tower_revision':revision,
            'sources':sources,'complete_consumer_coverage':False,
            'keys':[{'key':key,'destination':('TOWER_HEADER' if key in IDENTITY_FIELDS else
                                             'PROTECTED_AUTHORITY' if key in AUTHORITY_FIELDS else
                                             'EXECUTOR_POLICY' if key in POLICY_FIELDS else 'UNRESOLVED_RETAIN_HISTORY'),
                     'static_hints':hints[key], 'retirement_authorized':False} for key in sorted(control)],
            'limits':['dynamic consumers, deployed bundles and external clients need live reconciliation',
                      'absence of a static hit does not establish an unused key']}
