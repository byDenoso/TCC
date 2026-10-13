#!/usr/bin/env python3
"""Reproducible private search comparison. No Tower writes or scientific runs.

The manifest is external so a private corpus and its questions need not be
committed. Relevance judgments are fixed before running the compared engines.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.nexo_agent_api.memory import Memory, Snapshot, digest
from runtime.nexo_agent_api.retrieval import Retrieval, resolve_pointer

def citation_valid(snapshot, hit):
    """Verify source identity, revision and exact object, including JSON pointers."""
    try:
        citation = hit['citation']
        entry = snapshot.payload['files'].get(citation.get('path'))
        if not isinstance(entry, dict) or entry.get('encoding') != 'json':
            return False
        if (citation.get('source_id') != snapshot.source_id or
                citation.get('tower_revision', citation.get('revision')) != snapshot.revision):
            return False
        pointer = citation.get('json_pointer', citation.get('pointer', ''))
        if not isinstance(pointer, str):
            return False
        target = resolve_pointer(entry['value'], pointer)
        expected_version = str(target.get('entity_version') or target.get('version') or 'unversioned') if isinstance(target, dict) else 'unversioned'
        return (digest(target) == citation.get('content_sha256', citation.get('content_hash')) and
                str(citation.get('entity_version')) == expected_version)
    except (KeyError, TypeError, IndexError, ValueError, AttributeError):
        return False

def run(tower, manifest, out, cache):
    snapshot=Snapshot.read(tower)
    cases=json.loads(Path(manifest).read_text())
    if not isinstance(cases,list) or not cases or any(not isinstance(c,dict) or not {'query','relevant','stratum'}<=set(c) for c in cases):
        raise ValueError('Invalid externally reviewed query manifest')
    engines={'legacy_hybrid':Memory(Path(cache)/'legacy.db'),'retrieval_lexical':Retrieval(Path(cache)/'retrieval.db')}
    sync={name:engine.sync(snapshot) for name,engine in engines.items()}
    engines.update({name:engines['retrieval_lexical'] for name in ('retrieval_auto','retrieval_hybrid','retrieval_rerank')})
    modes={'legacy_hybrid':'hybrid','retrieval_lexical':'lexical','retrieval_auto':'auto','retrieval_hybrid':'hybrid','retrieval_rerank':'rerank'}
    results={}
    for name,engine in engines.items():
        rows=[]
        for case in cases:
            start=time.perf_counter()
            answer=engine.search(case['query'],case.get('role','LEARNER'),k=5,mode=modes[name],expected_revision=snapshot.revision,include_inactive=case.get('include_inactive',False))
            search_elapsed=time.perf_counter()-start
            hits=answer['hits'];ids=[h['id'] for h in hits];relevant=set(case['relevant'])
            ranks=[n for n,i in enumerate(ids,1) if i in relevant]
            checked_citations=[citation_valid(snapshot, h) for h in hits]
            rows.append({'query':case['query'],'stratum':case['stratum'],'include_inactive':case.get('include_inactive',False),'relevant':case['relevant'],'hits':ids,'mode':answer.get('mode',modes[name]),'elapsed_s':search_elapsed,'hit_at_5':bool(ranks) if relevant else None,'reciprocal_rank':1/min(ranks) if ranks else 0,'negative_abstained':not ids if not relevant else None,'citation_valid':all(checked_citations),'citation_count':len(checked_citations),'valid_citation_count':sum(checked_citations)})
        positive=[r for r in rows if r['hit_at_5'] is not None];negative=[r for r in rows if r['negative_abstained'] is not None]
        results[name]={'hit_at_5':statistics.mean(r['hit_at_5'] for r in positive) if positive else None,'mrr_at_5':statistics.mean(r['reciprocal_rank'] for r in positive) if positive else None,'negative_abstention_rate':statistics.mean(r['negative_abstained'] for r in negative) if negative else None,'citation_validation_rate':sum(r['valid_citation_count'] for r in rows)/sum(r['citation_count'] for r in rows) if sum(r['citation_count'] for r in rows) else None,'citation_count':sum(r['citation_count'] for r in rows),'valid_citation_count':sum(r['valid_citation_count'] for r in rows),'latency_median_s':statistics.median(r['elapsed_s'] for r in rows),'latency_max_s':max(r['elapsed_s'] for r in rows),'rows':rows}
    report={'contract':'NEXO_PRIVATE_RETRIEVAL_BENCHMARK_V2','citation_validation':'RESOLVED_JSON_POINTER_CONTENT_AND_VERSION','latency_basis':'Search call only; excludes citation validation and index construction','implementation_sha256':{label:hashlib.sha256(Path(cls.sync.__code__.co_filename).read_bytes()).hexdigest() for label,cls in [('memory',Memory),('retrieval',Retrieval)]},'benchmark_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'source_revision':snapshot.revision,'source_sha256':snapshot.raw_sha256,'source_file_count':snapshot.payload['file_count'],'query_manifest_sha256':digest(cases),'cases':len(cases),'judgment':'Fixed target-set coverage, not blinded semantic relevance assessment; exact identifiers are reported separately.','strata':{s:sum(c['stratum']==s for c in cases) for s in sorted({c['stratum'] for c in cases})},'sync':sync,'results':results,'scheduler_mutation':False,'tower_mutation':False,'scientific_execution':False}
    Path(out).write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({n:{k:v for k,v in r.items() if k!='rows'} for n,r in results.items()},ensure_ascii=False,indent=2))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('tower');p.add_argument('manifest');p.add_argument('out');p.add_argument('--cache',required=True);a=p.parse_args();run(a.tower,a.manifest,a.out,a.cache)
