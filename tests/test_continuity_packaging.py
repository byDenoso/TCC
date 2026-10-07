"""Bundle and cache compatibility on isolated synthetic Tower bytes."""
import ast
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
import pytest
from test_continuity_enxame import Lab, AT
from runtime.nexo_agent_api.retrieval_cli import MEMORY_CACHE_SUFFIX, memory_cache_path

ROOT=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build_gpt_writer_bundle.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

@pytest.fixture
def bundle(tmp_path,monkeypatch):
    destination=tmp_path/'bundle.py'
    monkeypatch.setattr(builder,'OUT',destination)
    builder.build()
    return destination


def test_bundle_rebuild_is_deterministic_and_contains_context(bundle):
    before=bundle.read_bytes()
    builder.build()
    assert bundle.read_bytes()==before
    tree=ast.parse(before)
    payload=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=='_BUNDLE' for t in n.targets))
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(payload))) as z:
        name='runtime/nexo_agent_api/continuity_context.py'
        assert z.read(name)==(ROOT/name).read_bytes()
        assert not any('NEXO_TOWER_LIVE' in n for n in z.namelist())


def test_missing_context_source_fails_before_bundle_write(tmp_path,monkeypatch):
    src=tmp_path/'runtime/nexo_agent_api';src.mkdir(parents=True)
    for name in builder._REQUIRED_EXTENSION_SOURCES:
        if name!='continuity_context.py':(src/name).write_text('')
    destination=tmp_path/'bundle.py';destination.write_text('previous bundle')
    monkeypatch.setattr(builder,'REPO',tmp_path);monkeypatch.setattr(builder,'OUT',destination)
    with pytest.raises(RuntimeError,match='continuity_context'):
        builder.build()
    assert destination.read_text()=='previous bundle'


def call(bundle,args,cwd):
    env={k:v for k,v in os.environ.items() if k not in {'PYTHONPATH','PYTHONHOME'}}
    # -S proves owner context needs no third-party site packages.
    result=subprocess.run([sys.executable,'-S',str(bundle),*map(str,args)],cwd=cwd,
                          env=env,capture_output=True,text=True,timeout=30,check=True)
    return json.loads(result.stdout)


def test_standalone_writer_apply_readback_context_and_idempotent_retry(bundle,tmp_path):
    lab=Lab(tmp_path/'root')
    original=tmp_path/'input.json';original.write_bytes(lab.raw)
    before=hashlib.sha256(original.read_bytes()).hexdigest()
    proposal=tmp_path/'proposal.json'
    envelope={'kind':'NEXO_MEMORY_ENTRY','source':'CHATGPT','intent_id':'standalone-fixture',
              'created_at':AT,'payload':{'event_id':'standalone','scope':'WORK',
              'category':'USER_PREFERENCE','text':'Synthetic standalone delivery','sources':[]},
              # Metadata injected only by this offline loader fixture, never a remote client grant.
              '_inbox_source':'DRIVE','_inbox_name':'standalone-fixture.json','_inbox_id':'fixture-only'}
    proposal.write_text(json.dumps([envelope]))
    out=tmp_path/'out.json'
    report=call(bundle,['apply',original,proposal,out],tmp_path)
    assert not report['rejected'] and out.is_file()
    verify=call(bundle,['verify',out],tmp_path);assert verify['readback']=='PASS'
    result=call(bundle,['continuity','context',out,'--scope','WORK'],tmp_path)
    assert len(result['hits'])==1 and result['hits'][0]['text']=='Synthetic standalone delivery'
    retry_out=tmp_path/'retry.json'
    replay=call(bundle,['apply',out,proposal,retry_out],tmp_path)
    assert not replay['rejected']
    final=retry_out if retry_out.exists() else out
    assert len(call(bundle,['continuity','context',final,'--scope','WORK'],tmp_path)['hits'])==1
    assert hashlib.sha256(original.read_bytes()).hexdigest()==before


@pytest.mark.parametrize('old_suffix',['','.retrieval-1.1','.retrieval-1.1-security-20261006',
                                      '.retrieval-1.1-continuity-20261007',MEMORY_CACHE_SUFFIX])
def test_cache_selection_preserves_old_namespace_without_suffix_stacking(tmp_path,old_suffix):
    original=tmp_path/('index.db'+old_suffix);original.write_text('previous index sentinel')
    selected=memory_cache_path(str(original))
    assert selected==str(tmp_path/'index.db')+MEMORY_CACHE_SUFFIX
    assert memory_cache_path(selected)==selected
    assert original.read_text()=='previous index sentinel'
