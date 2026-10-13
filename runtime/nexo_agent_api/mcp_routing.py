"""Scoped, human-authenticated routing for four private LEARNER read tools.

Routing never changes scientific state, the primary MCP or the single Writer.
Endpoint/catalog/canary evidence must come from actual reads; preparation alone
does not authenticate a human or prove that ChatGPT has connected the new MCP.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlsplit

from .control_compat import POLICY_PATH, SOURCE_HEADER, control_from_bundle, read_control_compat
from .memory import Snapshot, digest
from .live_tower import LIVE_TOWER_NAME

ACTION = 'SET_MCP_ROUTE'
SCHEMA = 'NEXO_SCIENTIFIC_READ_MCP_ROUTE_V1'
SOURCE_ID = '1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z'
TOOLS = frozenset({'nexo_capabilities', 'nexo_search', 'nexo_neighbors', 'nexo_trace'})
SCOPED_FIELDS = frozenset({'mcp_tool_routes', 'hosted_mcp_scientific_read_endpoint',
                           'hosted_mcp_scientific_read_route'})
BASE_FIELDS = frozenset({'hosted_mcp_current_endpoint', 'hosted_mcp_current_storage_backend',
                        'hosted_mcp_cutover_requirements', 'hosted_mcp_migration_target',
                        'mcp_runtime_model', 'mcp_spec_storage', 'mcp_tower_resolution'})
class _RouteAuthority:
    def __deepcopy__(self,memo):
        return self

ROUTE_AUTHORITY = _RouteAuthority()


def route_fingerprint(control):
    return digest({key:control[key] for key in sorted(BASE_FIELDS | SCOPED_FIELDS) if key in control})


def _need(condition, code):
    from .inbox_apply import ProposalError
    if not condition:
        raise ProposalError(code)


def _endpoint(value):
    _need(isinstance(value,str) and 0 < len(value) <= 2048, 'MCP_ENDPOINT_INVALID')
    try:
        parsed=urlsplit(value)
    except ValueError:
        _need(False,'MCP_ENDPOINT_INVALID')
    _need(parsed.scheme=='https' and bool(parsed.hostname) and not parsed.username
          and not parsed.password and not parsed.query and not parsed.fragment,
          'MCP_ENDPOINT_INVALID')
    return value


def _time(value):
    from .autonomy import timestamp
    parsed=timestamp(value)
    _need(parsed is not None,'MCP_EVIDENCE_TIMESTAMP_INVALID')
    return parsed


def _catalog(value, endpoint, created_at):
    _need(isinstance(value,dict),'MCP_CATALOG_REQUIRED')
    _need(set(value)=={'endpoint','source_file_id','role','tools','sha256','observed_at'},
          'MCP_CATALOG_FIELDS_INVALID')
    _need(value['endpoint']==endpoint and value['source_file_id']==SOURCE_ID
          and value['role']=='LEARNER','MCP_CATALOG_SCOPE_MISMATCH')
    tools=value['tools']
    _need(isinstance(tools,list) and len(tools)==len(TOOLS)
          and all(isinstance(tool,dict) and tool.get('name') in TOOLS
                  and isinstance(tool.get('inputSchema'),dict)
                  and tool['inputSchema'].get('type')=='object'
                  and isinstance(tool.get('annotations'),dict)
                  and tool['annotations'].get('readOnlyHint') is True
                  and tool['annotations'].get('destructiveHint') is False for tool in tools)
          and {tool['name'] for tool in tools}==TOOLS,'MCP_CATALOG_NOT_SCOPED_READ_ONLY')
    _need(value['sha256']==digest(tools),'MCP_CATALOG_HASH_MISMATCH')
    _need(_time(value['observed_at'])<=_time(created_at),'MCP_EVIDENCE_FROM_FUTURE')
    return value


def _now():
    return datetime.now(timezone.utc)


def _canary(value, endpoint, catalog, created_at, source_read):
    _need(isinstance(value,dict),'MCP_CONNECTED_CANARY_REQUIRED')
    _need(set(value)=={'runtime','endpoint','source_file_id','role','tool','catalog_sha256',
                      'observed_at','receipt_ref','readback','capabilities','capabilities_sha256'},
          'MCP_CANARY_FIELDS_INVALID')
    _need(value['runtime']=='CHATGPT_CONNECTED_MCP' and value['endpoint']==endpoint
          and value['source_file_id']==SOURCE_ID and value['role']=='LEARNER'
          and value['tool']=='nexo_capabilities' and value['catalog_sha256']==catalog['sha256']
          and value['readback']=='PASS' and isinstance(value['receipt_ref'],str)
          and 0<len(value['receipt_ref'])<=512,'MCP_CONNECTED_CANARY_UNVERIFIED')
    _need(_time(catalog['observed_at'])<=_time(value['observed_at'])<=_time(created_at),
          'MCP_CANARY_TIMESTAMP_INVALID')
    # Match the real adapter's authenticated capabilities response. A discovery
    # page, binding error or INDEX_REFRESHING body cannot prove usable access,
    # even when client-supplied summary labels say PASS.
    caps=value['capabilities']
    _need(isinstance(caps,dict) and caps.get('status')=='AUTHENTICATED'
          and caps.get('roles')==['LEARNER']
          and caps.get('source_mode')=='DRIVE_REVISION_VERIFIED_PRIVATE_SCOPED_D1'
          and caps.get('read_only') is True and caps.get('writes_enabled') is False
          and caps.get('external_model_calls') is False
          and caps.get('other_runtimes_authorized') is False
          and caps.get('connection_scope')=='this_authenticated_runtime_only',
          'MCP_CANARY_CAPABILITIES_NOT_AUTHENTICATED')
    supported=caps.get('supported_tools')
    _need(isinstance(supported,list) and len(supported)==len(TOOLS)
          and all(isinstance(name,str) for name in supported) and set(supported)==TOOLS,
          'MCP_CANARY_CAPABILITIES_SCOPE_MISMATCH')
    source=caps.get('source')
    _need(isinstance(source,dict) and source.get('source_id')==SOURCE_ID
          and source.get('revision')==source_read['tower_revision']
          and source.get('source_sha256')==source_read['tower_sha256']
          and caps.get('authorization_revision')==source_read['tower_revision'],
          'MCP_CANARY_CAPABILITIES_SOURCE_MISMATCH')
    _need(value['capabilities_sha256']==digest(caps),'MCP_CANARY_CAPABILITIES_HASH_MISMATCH')
    now=_now()
    _need(_time(caps.get('validity_start'))<=_time(value['observed_at'])
          and _time(caps.get('validity_start'))<=now<_time(caps.get('validity_end'))
          and _time(created_at)<_time(caps.get('validity_end'))
          and _time(created_at)<=now+timedelta(seconds=60),
          'MCP_CANARY_CAPABILITIES_EXPIRED')


def operator_requests(item, body, root):
    """Dedicated converter; never reaches the autonomy approval branch."""
    if body.get('action')!=ACTION:
        return None
    from .autonomy import HUMAN_AUTHORITY, envelope_hash
    _need(item.get('_autonomy_human_authority') is HUMAN_AUTHORITY,
          'AUTHENTICATED_HUMAN_MCP_ROUTE_REQUIRED')
    allowed={'action','endpoint','role','tool_names','source_read','catalog','canary','approval_ref'}
    _need(set(body)==allowed,'MCP_ROUTE_FIELDS_INVALID')
    _need(body['role']=='LEARNER' and isinstance(body['tool_names'],list)
          and len(body['tool_names'])==len(TOOLS)
          and all(isinstance(name,str) for name in body['tool_names']) and set(body['tool_names'])==TOOLS,
          'MCP_ROUTE_SCOPE_INVALID')
    endpoint=_endpoint(body['endpoint'])
    at=item.get('created_at');_time(at)
    _need(isinstance(body['approval_ref'],str) and 0<len(body['approval_ref'])<=512,
          'MCP_ROUTE_APPROVAL_REF_REQUIRED')
    catalog=_catalog(body['catalog'],endpoint,at)
    control=read_control_compat(root)
    proposal=envelope_hash(item)
    previous=control.get('hosted_mcp_scientific_read_route') or {}
    if isinstance(previous,dict) and previous.get('last_proposal_sha256')==proposal:
        return []
    source=body['source_read']
    _need(isinstance(source,dict) and set(source)=={'file_id','tower_revision','tower_sha256','route_sha256','tower_updated_at'}
          and source['file_id']==SOURCE_ID and isinstance(source['tower_revision'],str)
          and re.fullmatch('sha256:[0-9a-f]{64}',source['tower_revision'])
          and isinstance(source['tower_sha256'],str) and re.fullmatch('[0-9a-f]{64}',source['tower_sha256']),
          'MCP_ROUTE_SOURCE_READ_INVALID')
    _need(source['route_sha256']==route_fingerprint(control),'MCP_ROUTE_REVISION_CONFLICT')
    _need(_time(source['tower_updated_at'])<=_time(at),'MCP_EVIDENCE_FROM_FUTURE')
    try:
        header=json.loads((Path(root)/SOURCE_HEADER).read_text(encoding='utf-8'))
        raw_hash=hashlib.sha256((Path(root)/LIVE_TOWER_NAME).read_bytes()).hexdigest()
    except (OSError,ValueError):
        _need(False,'MCP_ROUTE_CANONICAL_SOURCE_UNAVAILABLE')
    _need(header.get('stable_file_id')==SOURCE_ID and header.get('revision')==source['tower_revision']
          and raw_hash==source['tower_sha256']
          and header.get('updated_at')==source['tower_updated_at']
          and header.get('storage')=='GOOGLE_DRIVE_PRIVATE'
          and header.get('truth_owner')=='TOWER_V06@GOOGLE_DRIVE_PRIVATE',
          'MCP_ROUTE_CANONICAL_SOURCE_MISMATCH')
    _canary(body['canary'],endpoint,catalog,at,source)
    routes=control.get('mcp_tool_routes') or {}
    _need(isinstance(routes,dict),'MCP_EXISTING_ROUTES_INVALID')
    updated=copy.deepcopy(routes);updated.update({name:endpoint for name in sorted(TOOLS)})
    proof={'schema':SCHEMA,'role':'LEARNER','read_only':True,'endpoint':endpoint,
           'tool_names':sorted(TOOLS),'catalog_sha256':catalog['sha256'],
           'source_read':copy.deepcopy(source),'connected_canary':copy.deepcopy(body['canary']),
           'approval_ref':body['approval_ref'],'migrated_at':at,'last_proposal_sha256':proposal,
           'previous_endpoint':control.get('hosted_mcp_scientific_read_endpoint'),
           'previous_tool_routes':{name:copy.deepcopy(routes[name]) for name in sorted(TOOLS) if name in routes}}
    changes={'mcp_tool_routes':updated,'hosted_mcp_scientific_read_endpoint':endpoint,
             'hosted_mcp_scientific_read_route':proof}
    target='CONTROL.json' if (Path(root)/'CONTROL.json').exists() else POLICY_PATH
    merge=changes if target=='CONTROL.json' else {'fields':changes}
    return [{'request_id':'REQ-MCP-ROUTE-'+proposal[:32],'document':target,'merge':merge,
             'expected_mcp_route_sha256':source['route_sha256'],'_mcp_route_authority':ROUTE_AUTHORITY}]


def guard_request(root, request):
    """Only the authenticated converter may merge these scoped route fields."""
    def refuse(code):
        return {'accepted':False,'request_id':request.get('request_id'),'issue':{'code':code}}
    target='CONTROL.json' if (Path(root)/'CONTROL.json').exists() else POLICY_PATH
    if request.get('_mcp_route_authority') is not ROUTE_AUTHORITY or request.get('document')!=target:
        return refuse('MCP_ROUTE_PROTECTED_DOCUMENT')
    patch=request.get('merge') or {}
    if target==POLICY_PATH:
        if set(patch)!={'fields'} or not isinstance(patch['fields'],dict):
            return refuse('MCP_ROUTE_PATCH_SCOPE_INVALID')
        patch=patch['fields']
    if set(patch)!=SCOPED_FIELDS:
        return refuse('MCP_ROUTE_PATCH_SCOPE_INVALID')
    control=read_control_compat(root)
    if request.get('expected_mcp_route_sha256')!=route_fingerprint(control):
        return refuse('MCP_ROUTE_REVISION_CONFLICT')
    return None


def prepare(snapshot: Snapshot, endpoint: str, *, catalog=None, canary=None,
            created_at: str, approval_ref: str) -> dict:
    """Prepare an exact proposed envelope; never manufacture missing evidence."""
    endpoint=_endpoint(endpoint);_time(created_at)
    control=control_from_bundle(snapshot.payload)
    _need(snapshot.source_id==SOURCE_ID,'MCP_ROUTE_CANONICAL_SOURCE_MISMATCH')
    _need(isinstance(approval_ref,str) and 0<len(approval_ref)<=512,'MCP_ROUTE_APPROVAL_REF_REQUIRED')
    source_read={'file_id':snapshot.source_id,'tower_revision':snapshot.revision,
                 'tower_sha256':snapshot.raw_sha256,'route_sha256':route_fingerprint(control),
                 'tower_updated_at':snapshot.observed_at}
    blockers=[]
    if catalog is None:
        blockers.append('MCP_CATALOG_REQUIRED')
    else:
        _catalog(catalog,endpoint,created_at)
    if canary is None:
        blockers.append('MCP_CONNECTED_CANARY_REQUIRED')
    elif catalog is not None:
        _canary(canary,endpoint,catalog,created_at,source_read)
    body={'action':ACTION,'endpoint':endpoint,'role':'LEARNER','tool_names':sorted(TOOLS),
          'source_read':source_read,
          'catalog':copy.deepcopy(catalog),'canary':copy.deepcopy(canary),'approval_ref':approval_ref}
    envelope=None if blockers else {'kind':'OPERATOR_INTENT','source':'DENER','created_at':created_at,'payload':body}
    return {'status':'PENDING_CONNECTION' if blockers else 'PREPARED_PENDING_HUMAN_AUTHENTICATION',
            'blockers':blockers,'candidate':body,'envelope':envelope,
            'endpoint_observed':catalog is not None,'human_authenticated':False,
            'writes_canonical_state':False,'execution_authorization':False}


def main(argv):
    import argparse
    from datetime import datetime,timezone
    parser=argparse.ArgumentParser(description='Prepare scoped MCP route; no writes to Tower')
    parser.add_argument('command',choices=['prepare']);parser.add_argument('tower')
    parser.add_argument('endpoint');parser.add_argument('output')
    parser.add_argument('--catalog');parser.add_argument('--canary');parser.add_argument('--approval-ref',required=True)
    args=parser.parse_args(argv)
    read=lambda path:json.loads(Path(path).read_text(encoding='utf-8')) if path else None
    result=prepare(Snapshot.read(args.tower),args.endpoint,catalog=read(args.catalog),canary=read(args.canary),
                   created_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),approval_ref=args.approval_ref)
    from .tower_gc_cli import _write_private
    _write_private(args.output,json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2).encode()+b'\n')
    print(json.dumps({'status':result['status'],'blockers':result['blockers'],'writes_canonical_state':False}))
    return 0
