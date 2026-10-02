"""Finite GitHub integration and nonlinear-sensitivity checks; never samples."""
import hashlib
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'validation'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    report={'stage':'validation_only','mcmc_started':False,
            'interpretation':'numerical viability and nonlinear sensitivity at fixed points; not model ranking',
            'contract':{'eta':.1,'log10_zc':3.81,'theta_i':2.89155,
                        'nonlinear_status':'halofit vs linear diagnostic; production prescription not selected'},
            'checks':{}}
    path=OUT/'validation_index.json'
    packages=os.environ['COBAYA_PACKAGES_PATH']
    source_files=[ROOT/'pure_pngb_from_upstream.patch',ROOT/'build_review.py',ROOT/'smoke_integration.py',
                  ROOT/'run_validation.py',ROOT/'bootstrap.sh',ROOT/'VALIDATION_SCOPE.md',
                  *sorted((ROOT/'peer_integration').glob('*.py')),ROOT/'reference/spt_cobaya_ttteee.yaml']
    report['source_sha256']={str(p.relative_to(ROOT)):digest(p) for p in source_files}
    workflow=ROOT.parent/'.github/workflows/peer-pngb-sptd1-validation.yml'
    if not workflow.is_file():
        raise RuntimeError('Missing exact workflow source for provenance')
    report['workflow_sha256']=digest(workflow)
    report['resources']={'cpu_count':os.cpu_count(),'meminfo':Path('/proc/meminfo').read_text()}

    def check(name,args):
        target=OUT/f'{name}.json'
        command=[sys.executable,str(ROOT/'smoke_integration.py'),*args,'--output',str(target)]
        start=time.monotonic()
        log=OUT/f'{name}.log'
        with log.open('w') as output:
            try:
                proc=subprocess.Popen(['/usr/bin/time','-v',*command],cwd=ROOT,stdout=output,
                                      stderr=subprocess.STDOUT,start_new_session=True)
                code=proc.wait(timeout=900)
            except subprocess.TimeoutExpired:
                # Kill the wrapper and its entire Python/CLASS process group.
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait()
                code=124
        record={'command':command,'exit_code':code,'wall_seconds':time.monotonic()-start,
                'log':str(log.relative_to(ROOT)),'passed':False}
        if target.exists():
            record['result_sha256']=digest(target)
            data=json.loads(target.read_text())
            record['passed']=code==0 and data.get('passed') is True
            record['result']=str(target.relative_to(ROOT))
        report['checks'][name]=record
        path.write_text(json.dumps(report,indent=2)+'\n')
        print(name,record,flush=True)
        return record['passed']

    # Each check runs in a fresh process so its allocations cannot accumulate.
    for point in ('central','highf','nearzero','shifted'):
        if not check(f'calibration_{point}',['calibration','--point',point]):
            raise SystemExit('Calibration gate failed; no likelihood or sampler launched')

    for model,fede in (('LCDM','0'),('PNGB_ETA01','.09')):
        for nonlinear in ('halofit','none'):
            name=f'{model}_{nonlinear}'
            spectrum=OUT/f'{name}_spectra.npz'
            args=['--fede',fede,'--nonlinear',nonlinear]
            exported=check(name+'_spectra',['spectra',*args,'--spectra',str(spectrum)])
            if exported:
                check(name+'_spt_separate',['candl-file','--spectra',str(spectrum)])
                for block in ('lowtt','sroll2','lensing','desi','shoes','spt'):
                    check(name+'_'+block+'_cached',['block-file','--spectra',str(spectrum),
                          '--block',block,'--packages',packages])
            # Joint evaluation is independent of the cache/export diagnostic.
            check(name+'_main',['main',*args,'--packages',packages])

    # HMcode is only a supported LCDM reference; never bypass its scalar guard.
    check('LCDM_hmcode_main',['main','--fede','0','--nonlinear','hmcode','--packages',packages])
    required=[f'{m}_{n}_main' for m in ('LCDM','PNGB_ETA01') for n in ('halofit','none')]
    report['integration_pair_passed']=all(report['checks'].get(k,{}).get('passed') is True for k in required)
    report['validation_complete']=bool(report['checks']) and all(v['passed'] for v in report['checks'].values())
    report['production_mcmc_approved_by_this_stage']=False
    report['nonlinear_sensitivity']={}
    for model in ('LCDM','PNGB_ETA01'):
        paths=[OUT/f'{model}_{n}_main.json' for n in ('halofit','none')]
        if all(p.exists() and json.loads(p.read_text()).get('passed') for p in paths):
            a,b=(json.loads(p.read_text())['result']['loglikes_by_name'] for p in paths)
            if set(a)!=set(b): raise RuntimeError('Likelihood names differ between prescriptions')
            report['nonlinear_sensitivity'][model]={'delta_chi2_halofit_minus_linear_by_block':
                {k:-2*(a[k]-b[k]) for k in a}}
    path.write_text(json.dumps(report,indent=2)+'\n')
    if not report['integration_pair_passed'] or not report['validation_complete']:
        raise SystemExit('Incomplete integration; inspect recorded blockers')


if __name__=='__main__':
    main()
