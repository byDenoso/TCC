"""Read/proposal entry point for the materialized, authorized Tower. No delivery."""
import argparse,json,tempfile
from pathlib import Path, PurePosixPath
from .memory import Snapshot,digest,canonical
from .live_tower import materialize_live_tower
from . import enxame,continuity
from .inbox_client import prepare


def _snapshot_view(snapshot, scope, scope_version):
    """Read protocol data directly when no registered test needs filesystem readiness.

    Unsupported representations use the existing materialized reader. There is
    no cache, second source or partial Tower available for writing.
    """
    files = snapshot.payload["files"]
    if files["CONTROL.json"].get("encoding") != "json":
        return None
    events, records = [], []
    prefixes = (enxame.EVENT_ROOT + "/", "entities/artifact/", "entities/test/")
    for path, entry in files.items():
        if "\\" in path or str(PurePosixPath(path)) != path:
            return None
        prefix = next((p for p in prefixes if path.startswith(p)
                       and path.endswith(".json") and "/" not in path[len(p):]), None)
        if prefix is None:
            continue
        if not isinstance(entry, dict) or entry.get("encoding") != "json":
            return None
        value = entry.get("value")
        if not isinstance(value, dict):
            return None
        if prefix == prefixes[0]:
            events.append(value)
        elif prefix == prefixes[1]:
            if value.get("kind") in {"NEXO_MEMORY_ENTRY", "NEXO_PROJECT_EVENT"} and value.get("payload", {}).get("contract") == continuity.CONTRACT:
                records.append(value)
        elif value.get("enxame", {}).get("contract") == enxame.CONTRACT:
            return None
    return enxame.validate_events(events, scope, scope_version), records


def inspect(tower_path, *, scope=None, scope_version=None, after=0, limit=100, expected_revision=None):
    if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("PAGINATION_BOUNDS_INVALID")
    if after > 0 and expected_revision is None:
        raise ValueError("PAGINATION_REVISION_REQUIRED")
    snapshot=Snapshot.read(tower_path)
    if expected_revision is not None and expected_revision != snapshot.revision:
        raise ValueError("PAGINATION_REVISION_CHANGED")
    fast = _snapshot_view(snapshot, scope, scope_version)
    with tempfile.TemporaryDirectory(prefix='nexo-continuity-read-') as tmp:
        if fast is None:
            root,_=materialize_live_tower(canonical(snapshot.payload),Path(tmp)/'Tower')
            events=enxame.load_events(root,scope,scope_version)
            records=continuity.records(root)
            test_paths=(root/'entities/test').glob('*.json')
        else:
            events,records=fast
            test_paths=()
        groups={}
        for e in events:groups.setdefault((e['scope_id'],e['scope_version']),[]).append(e)
        views=[]
        for key, rows in sorted(groups.items()):
            view=enxame.derive(rows)
            view.pop('events')
            views.append({'scope_id':key[0],'scope_version':key[1],**view})
        page=events[after:after+limit]
        prepared=[]
        from . import scientific_integrity
        for path in test_paths:
            test=json.loads(path.read_bytes())
            if test.get('enxame',{}).get('contract')==enxame.CONTRACT:
                prepared.append({'test_id':test['id'],'entity_version':test['entity_version'],'content_sha256':digest(test),'spec_sha256':test['enxame']['spec_sha256'],'recipe':test.get('recipe'),'params':test.get('recipe_params'),'data_binding':test.get('data_binding'),'preparation':test.get('preparation'),'current_readiness':scientific_integrity.readiness(root,test),'execution':test.get('execution'),'review_state':test.get('review_state'),'scientific_evidence':test.get('scientific_evidence')})
        return {'contract':continuity.CONTRACT,'access':'PRIVATE','source_id':snapshot.source_id,'source_revision':snapshot.revision,'protocols':views,'records':records,'prepared_tests':prepared,'events':page,'total_events':len(events),'next_offset':after+limit if after+limit<len(events) else None,'page_context':{'scope':scope,'scope_version':scope_version,'expected_revision':snapshot.revision},'scheduler_mutation':False,'scientific_execution':False,'logical_roles_one_owner':True,'delivery_operations':['ENXAME_EVENT','ENXAME_REGISTER_TEST','NEXO_MEMORY_ENTRY','NEXO_PROJECT_EVENT'],'transport':'EXISTING_PRIVATE_DRIVE_INBOX_SINGLE_WRITER'}

def main(argv):
    parser=argparse.ArgumentParser(description='NEXO private continuity over the canonical Tower')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('inspect');p.add_argument('tower');p.add_argument('--scope');p.add_argument('--scope-version',type=int);p.add_argument('--after',type=int,default=0);p.add_argument('--limit',type=int,default=100);p.add_argument('--expected-revision')
    p=sub.add_parser('context');p.add_argument('tower');p.add_argument('--scope',required=True);p.add_argument('--query',default='');p.add_argument('--at');p.add_argument('--limit',type=int,default=20);p.add_argument('--include-history',action='store_true');p.add_argument('--expected-revision')
    p=sub.add_parser('prepare');p.add_argument('envelope');p.add_argument('--role',required=True)
    args=parser.parse_args(argv)
    if args.command=='inspect':
        if not 1<=args.limit<=1000 or args.after<0:parser.error('Pagination bounds exceeded')
        result=inspect(args.tower,scope=args.scope,scope_version=args.scope_version,after=args.after,limit=args.limit,expected_revision=args.expected_revision)
    elif args.command=='context':
        from .continuity_context import context
        result=context(Snapshot.read(args.tower),scope=args.scope,query=args.query,at=args.at,limit=args.limit,include_history=args.include_history,expected_revision=args.expected_revision)
    else:
        envelope=json.loads(Path(args.envelope).read_text())
        result=prepare(envelope,runtime_role=args.role,allowed_kinds={'ENXAME_EVENT','ENXAME_REGISTER_TEST','NEXO_MEMORY_ENTRY','NEXO_PROJECT_EVENT'})
        result.pop('raw',None)
        result['envelope']=envelope;result['delivered']=False;result['applied']=False
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0
