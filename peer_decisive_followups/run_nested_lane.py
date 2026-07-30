#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, os, shutil, subprocess, sys, tarfile
from pathlib import Path

REPO='byDenoso/TCC'
SOURCE_RUN='30455821484'
ACT_COMMIT='627aeafb88ae5ad1aa66b406bea2d65cfa66a27d'

def run(cmd, *, cwd=None, timeout=None, check=True, stdout=None, stderr=None):
    print('+', ' '.join(map(str, cmd)), flush=True)
    return subprocess.run(cmd, cwd=cwd, timeout=timeout, check=check, text=True, stdout=stdout, stderr=stderr)

def install_runtime(work: Path, packages: Path) -> None:
    run(['gh','run','download',SOURCE_RUN,'--repo',REPO,'--name','validated-act-cosmorec-runtime-gslfix','--dir',str(work/'validated')])
    run(['gh','run','download',SOURCE_RUN,'--repo',REPO,'--name','official-likelihood-packages-v3','--dir',str(work/'payload')])
    sums=work/'payload'/'official-likelihood-packages-v3.tar.gz.sha256'
    run(['sha256sum','-c',sums.name],cwd=sums.parent)
    with tarfile.open(work/'payload'/'official-likelihood-packages-v3.tar.gz','r:gz') as tf:
        tf.extractall(work)
    wheels=list((work/'validated').rglob('camb-*.whl'))
    dbs=list((work/'validated').rglob('Rec_database'))
    devs=list((work/'validated').rglob('Development'))
    if not wheels or not dbs or not devs: raise RuntimeError('validated CAMB payload incomplete')
    shutil.rmtree(packages/'code'/'CAMB',ignore_errors=True)
    run([sys.executable,'-m','pip','install','--force-reinstall','--no-deps',str(wheels[0])])
    for name, src in [('Rec_database',dbs[0]),('Development',devs[0])]:
        dst=work/name
        if dst.exists() or dst.is_symlink(): dst.unlink()
        dst.symlink_to(src.resolve(),target_is_directory=True)
    act=work/'act-lite'
    run(['git','clone','https://github.com/ACTCollaboration/DR6-ACT-lite.git',str(act)])
    run(['git','checkout',ACT_COMMIT],cwd=act)
    run([sys.executable,'-m','pip','install','-e',str(act)])

def parse_status(root: Path, code: int) -> dict:
    import re
    stats=list(root.rglob('*.stats'))+list(root.rglob('*stats*.txt'))
    text='\n'.join(p.read_text(errors='replace') for p in stats)
    vals=[]
    for pat in [r'log\(Z\)\s*=\s*([-+0-9.eE]+)\s*\+/-\s*([-+0-9.eE]+)',r'logZ\s*[:=]\s*([-+0-9.eE]+).*?([-+0-9.eE]+)']:
        for m in re.finditer(pat,text,re.S):
            try: vals.append({'logZ':float(m.group(1)),'logZstd':float(m.group(2))})
            except ValueError: pass
    return {'status':'COMPLETE' if code==0 and vals else 'INCOMPLETE','exit_code':code,'stats_files':[str(p) for p in stats],'evidence':vals[-1] if vals else None}

def timed_run(config: Path, logroot: Path, seconds: int) -> tuple[int,dict]:
    logroot.mkdir(parents=True,exist_ok=True)
    with (logroot/'stdout.log').open('w') as out,(logroot/'stderr.log').open('w') as err:
        try:
            p=run(['mpirun','--oversubscribe','-np','4','cobaya-run',str(config)],cwd=Path.cwd(),timeout=seconds,check=False,stdout=out,stderr=err)
            code=p.returncode
        except subprocess.TimeoutExpired:
            code=124
    (logroot/'exit_code.txt').write_text(str(code)+'\n')
    status=parse_status(logroot,code)
    (logroot/'nested_status.json').write_text(json.dumps(status,indent=2))
    return code,status

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--model',choices=['M0','M1','M2','M3'],required=True); ap.add_argument('--science',type=Path,required=True); ap.add_argument('--work',type=Path,required=True); ap.add_argument('--packages',type=Path,required=True)
    a=ap.parse_args(); a.work=a.work.resolve(); a.packages=a.packages.resolve(); a.work.mkdir(parents=True,exist_ok=True)
    install_runtime(a.work,a.packages)
    idx=['M0','M1','M2','M3'].index(a.model)
    run([sys.executable,'peer_decisive_followups/build_nested_config.py','--science',str(a.science.resolve()),'--model',a.model,'--packages',str(a.packages),'--root',str(a.work/f'nested_{a.model}'),'--seed',str(2026076100+idx)])
    root=a.work/f'nested_{a.model}'
    _,data=timed_run(root/'data.yaml',root/'data',15000)
    _,prior=timed_run(root/'prior_volume.yaml',root/'prior_volume',4200)
    complete=data['status']=='COMPLETE' and prior['status']=='COMPLETE'
    normalized=None
    if complete:
        normalized={'logZ':data['evidence']['logZ']-prior['evidence']['logZ'],'logZstd':math.hypot(data['evidence']['logZstd'],prior['evidence']['logZstd'])}
    result={'model':a.model,'status':'COMPLETE' if complete else 'INCOMPLETE','data':data,'prior_volume':prior,'normalized':normalized}
    (root/'normalized_evidence.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
