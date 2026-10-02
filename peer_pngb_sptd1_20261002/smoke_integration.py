"""Explicit bounded integration checks only; this file never runs a sampler.

Writes incremental JSON. Run with the parent-provisioned Python environment.
"""
import argparse
from dataclasses import asdict
import hashlib
import importlib
import json
import math
import os
import resource
from pathlib import Path
import time

os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
os.environ.setdefault('JAX_ENABLE_X64','True')
os.environ.setdefault('JAX_PLATFORMS','cpu')

import numpy as np
from peer_integration.calibration import Target, calibrate
from peer_integration.class_backend import make_class_probe, scalar_args

ROOT=Path(__file__).resolve().parent
BAO_Z=[.295,.510,.706,.934,1.321,1.484,2.33]
CACHE_DERIVED=('H0','Omega_m','rs_drag')
BASE={'omega_b':.02279246091553037,'omega_cdm':.1314030233540993,
      'A_s':2.133190566796063e-9,'n_s':.9928140365018976,'tau_reio':.0566,
      'N_ncdm':1,'m_ncdm':.06,'T_ncdm':.71611,
      'N_ur':3.046-.71611**4/(4/11)**(4/3),
      'Omega_k':0.,'A_L':1.,'YHe':'BBN','recombination':'HyRec',
      'non_linear':'hmcode','hmcode_version':'2020','lensing':'yes',
      'output':'tCl,pCl,lCl,mPk','l_max_scalars':6600,'P_k_max_1/Mpc':20}


def identity():
    import classy
    binary=Path(importlib.import_module(classy.Class.__module__).__file__).resolve()
    return classy.Class, {'classy_version':str(classy.__version__),
                         'classy_extension':str(binary),
                         'classy_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}


def background_check(Class):
    target=Target(.09,1.041)
    start=time.perf_counter()
    result=make_class_probe(Class,BASE,target)(747.4451502175409,.12672536270923074,68.20874306622639)
    return {'summary':asdict(result),'seconds':time.perf_counter()-start,'base_args':BASE}


def calibration_check(Class,point):
    base=dict(BASE)
    cases={'central':(.09,1.041,.02279246091553037,.1314030233540993),
           'lowf':(.02,1.041,.02279246091553037,.1314030233540993),
           'shifted':(.09,1.042,.0233,.125),
           'highf':(.18,1.041,.02279246091553037,.1314030233540993),
           'smallf':(.001,1.041,.02279246091553037,.1314030233540993),
           'nearzero':(1e-6,1.041,.02279246091553037,.1314030233540993)}
    for label,f in (('f0001',1e-4),('f01',.01),('f06',.06),('f12',.12)):
        cases[label]=(f,1.041,.02279246091553037,.1314030233540993)
    fede,theta,base['omega_b'],base['omega_cdm']=cases[point]
    target=Target(fede,theta)
    start=time.perf_counter()
    result=calibrate(target,make_class_probe(Class,base,target))
    return {'target':asdict(target),'calibration':asdict(result),
            'seconds':time.perf_counter()-start,'base_args':base}


def spectrum_requirements(lmax,export_cache=False):
    """Register consumers explicitly, including metadata for standalone export.

    Declaring params as derived outputs does not register provider consumers in
    Cobaya. A dummy likelihood requests no H0, so cache export must do so itself.
    """
    requests={'Cl':{'tt':lmax,'te':lmax,'ee':lmax,'pp':lmax},'peer_diagnostics':None}
    if export_cache:
        requests.update({name:None for name in CACHE_DERIVED})
        requests.update(Hubble={'z':BAO_Z},angular_diameter_distance={'z':BAO_Z})
    return requests


def validated_cache_payload(cl,raw,bao_z,hubble,distances,metadata):
    """Validate every exported numeric product before writing any cache file."""
    ell=np.asarray(cl['ell'])
    if ell.ndim!=1 or len(ell)<3 or not np.array_equal(ell,np.arange(len(ell))):
        raise ValueError('Cache ell must be contiguous integers beginning at zero')
    if not np.array_equal(np.asarray(raw['ell']),ell):
        raise ValueError('Raw and lensed-Dl ell grids differ')
    for spectra,label in ((cl,'Dl'),(raw,'raw Cl')):
        if not {'tt','te','ee','pp'}.issubset(spectra):
            raise ValueError(f'Missing required spectra in {label}')
        for key,value in spectra.items():
            values=np.asarray(value)
            if values.shape!=ell.shape or not np.isfinite(values).all():
                raise ValueError(f'Invalid shape or non-finite {label} {key}')
    zz=np.asarray(bao_z,dtype=float)
    if zz.ndim!=1 or not np.isfinite(zz).all() or np.any(np.diff(zz)<=0):
        raise ValueError('Invalid BAO redshift grid')
    for name,value in (('Hubble',hubble),('angular diameter distance',distances)):
        values=np.asarray(value)
        if values.shape!=zz.shape or not np.isfinite(values).all() or np.any(values<=0):
            raise ValueError(f'Invalid cached {name}')
    for name in ('H0','Omega_m','rs_drag','rdrag'):
        value=float(metadata['derived'][name])
        if not math.isfinite(value) or value<=0:
            raise ValueError(f'Invalid derived cache metadata: {name}')
    metadata_json=json.dumps(metadata,allow_nan=False)
    return {**cl,**{'raw_'+k:v for k,v in raw.items() if k!='ell'},
            'bao_z':zz,'H_km_s_Mpc':np.asarray(hubble),'DA_Mpc':np.asarray(distances),
            'metadata_json':metadata_json}


def cobaya_check(identity_data, fede, lmax=100, spt=False, main_stack=False, packages=None, spectra_path=None):
    from cobaya.model import get_model
    from build_review import template_contract, make_review
    nuisance, priors=template_contract()
    params={'ombh2':.02279246091553037,'omch2':.1314030233540993,
            'logA':math.log(BASE['A_s']*1e10),'ns':BASE['n_s'],'tau':BASE['tau_reio'],
            'theta_s_100':1.041,'peer_fede':fede,'H0':{'derived':True},
            'Omega_m':{'derived':True},'rs_drag':{'derived':True}}
    extra={k:v for k,v in BASE.items() if k not in ('omega_b','omega_cdm','A_s','n_s','tau_reio')}
    extra['l_max_scalars']=lmax
    likes={'one':None}
    if spt:
        params.update({p:float(v['ref']) for p,v in nuisance.items()})
        likes={'candl_like':{'class':'candl.interface.CandlCobayaLikelihood',
                            'data_set_file':'spt_candl_data.SPT3G_D1_TnE',
                            'clear_internal_priors':True,'lensing':False,
                            'feedback':False,'stop_at_error':True}}
    if main_stack:
        likes=make_review('LCDM' if fede==0 else 'PNGB_ETA01','historical_with_shoes')['cobaya_preview']['likelihood']
        likes['candl_like']['feedback']=False
        params['A_planck']=1.0
    info={'params':params, 'likelihood':likes,
          'theory':{'peer_integration.cobaya_adapter.PEERClassy':{
              'path':'global','validation_mode':True,
              'expected_classy_sha256':identity_data['classy_sha256'],
              'stop_at_error':True,'extra_args':extra}},'debug':False}
    if main_stack: info['packages_path']=packages
    # Nuisances are fixed at the official reference for this numerical smoke;
    # evaluating a point must not be presented as a fit or model comparison.
    if spt: info['prior']=priors
    start=time.perf_counter()
    print('STAGE cobaya_model_initialization',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,flush=True)
    with get_model(info) as model:
        print('STAGE cobaya_model_loaded',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,flush=True)
        model.add_requirements(spectrum_requirements(lmax,export_cache=spectra_path is not None))
        posterior=model.logposterior({})
        cl=model.provider.get_Cl(ell_factor=True,units='muK2')
        if spectra_path is not None:
            spectra_path.parent.mkdir(parents=True,exist_ok=True)
            raw=model.provider.get_Cl(ell_factor=False,units='muK2')
            metadata={'schema':'peer-single-point-v1','fede':fede,'nonlinear':extra['non_linear'],
                      'T_cmb':2.7255,'classy_sha256':identity_data['classy_sha256'],
                      'derived':{'H0':float(model.provider.get_param('H0')),
                                 'rdrag':float(model.provider.get_param('rs_drag')),
                                 'rs_drag':float(model.provider.get_param('rs_drag')),
                                 'Omega_m':float(model.provider.get_param('Omega_m'))},
                      'input_cosmology':{k:v for k,v in params.items() if not isinstance(v,dict)},
                      'bao_redshift_source':'DESI DR2 official desi_gaussian_bao_ALL_GCcomb_mean.txt'}
            payload=validated_cache_payload(cl,raw,BAO_Z,
                model.provider.get_Hubble(BAO_Z,units='km/s/Mpc'),
                model.provider.get_angular_diameter_distance(BAO_Z),metadata)
            temporary=spectra_path.with_suffix('.partial.npz')
            np.savez(temporary,**payload)
            temporary.replace(spectra_path)
        report={'fede':fede,'logpost':float(posterior.logpost),
                'theory_extra_args':extra,
                'loglikes':[float(v) for v in posterior.loglikes],
                'loglikes_by_name':{str(k):float(v) for k,v in zip(model.likelihood,posterior.loglikes)},
                'logpriors':[float(v) for v in posterior.logpriors],
                'derived':[float(v) for v in posterior.derived],
                'spectra_finite':all(np.isfinite(cl[k]).all() for k in ('tt','te','ee')),
                'ell_max':int(cl['ell'][-1]),'seconds':time.perf_counter()-start,
                'calibration':model.provider.get_peer_diagnostics()}
        report['all_finite']=bool(np.isfinite([posterior.logpost,*posterior.loglikes,
                                                *posterior.logpriors,*posterior.derived]).all()
                                   and report['spectra_finite'])
        if not report['all_finite']:
            raise RuntimeError('Non-finite model outputs; this smoke failed')
        report['max_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if spt:
            report['likelihood_output_contract']='candl2.0.3 official wrapper casts logl to np.float32; JSON stores its Pythonfloat value'
        return report


def candl_file_check(path):
    """Evaluate an exported D_ell file in a fresh process without CLASS arrays."""
    import candl
    import candl.lib
    import spt_candl_data
    from scipy import stats
    from build_review import template_contract
    nuisance, priors=template_contract()
    values={p:float(v['ref']) for p,v in nuisance.items()}
    print('STAGE candl_initialization',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,flush=True)
    like=candl.Like(spt_candl_data.SPT3G_D1_TnE,feedback=False)
    print('STAGE candl_loaded',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,flush=True)
    like.priors=[]
    with np.load(path) as cl:
        ell=cl['ell']; use=(ell>=like.ell_min)&(ell<=like.ell_max)
        values['Dl']={k.upper():cl[k][use] for k in ('tt','te','ee')}
        values['Dl']['ell']=ell[use]
    value=float(like.log_like(values))
    if not math.isfinite(value): raise RuntimeError('Non-finite SPT likelihood')
    prior_terms={}
    for name,expression in priors.items():
        fn=eval(expression,{'stats':stats,'np':np,'__builtins__':{}})
        names=fn.__code__.co_varnames[:fn.__code__.co_argcount]
        prior_terms[name]=float(fn(**{p:values[p] for p in names}))
    return {'loglike_raw_float64':value,'loglike_official_wrapper_float32':float(np.float32(value)),
            'loglikes_by_name':{'candl_like':float(np.float32(value))},'all_finite':True,
            'logprior_external_total':sum(prior_terms.values()),'logprior_terms':prior_terms,
            'candl_backend':'jax' if candl.lib.JAX_IMPORT_SUCCEEDED else 'numpy',
            'spectrum_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'ell_min':int(like.ell_min),'ell_max':int(like.ell_max),
            'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'joint_model_memory_validated':False}


def block_file_check(path,block,packages):
    from cobaya.model import get_model
    from build_review import make_review,template_contract
    names={'lowtt':'planck_2018_lowl.TT','sroll2':'planck_2018_lowl.EE_sroll2',
           'lensing':'planck_2018_lensing.native','desi':'bao.desi_dr2.desi_bao_all',
           'shoes':'peer_integration.shoes.SH0ESGaussian','spt':'candl_like'}
    name=names[block]
    like=make_review('LCDM','historical_with_shoes')['cobaya_preview']['likelihood'][name]
    if block=='spt':
        nuisance,priors=template_contract()
        params={p:float(v['ref']) for p,v in nuisance.items()}
        like['feedback']=False
    else:
        params={'A_planck':1.0} if block in ('lowtt','lensing') else {}
        priors={}
    # Explicit even when this block has no nuisance parameters. An empty params
    # mapping can be normalized to None by Cobaya before component defaults merge.
    params['cache_point_id']=0
    info={'theory':{'peer_integration.cached_theory.CachedPoint':{'cache_file':str(path)}},
          'likelihood':{name:like},'params':params,'packages_path':packages,'prior':priors}
    print('STAGE cached_block_initialization',block,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,flush=True)
    with get_model(info) as model:
        posterior=model.logposterior({})
        if not np.isfinite([posterior.logpost,*posterior.loglikes,*posterior.logpriors]).all():
            raise RuntimeError('Non-finite cached block')
        return {'block':block,'loglikes_by_name':{str(k):float(v) for k,v in zip(model.likelihood,posterior.loglikes)},
                'logpriors':[float(v) for v in posterior.logpriors],
                'all_finite':True,'spectrum_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'joint_model_memory_validated':False}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('mode',choices=('background','calibration','cobaya','spectra','candl-file','block-file','spt','main'))
    ap.add_argument('--point',default='central')
    ap.add_argument('--fede',type=float,default=.09)
    ap.add_argument('--packages')
    ap.add_argument('--spectra',type=Path)
    ap.add_argument('--block',choices=('lowtt','sroll2','lensing','desi','shoes','spt'))
    ap.add_argument('--nonlinear',choices=('hmcode','halofit','none'),default='hmcode',
                    help='Explicit scientific setting; no fallback is performed')
    ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args()
    BASE['non_linear']=args.nonlinear
    if args.nonlinear!='hmcode':
        BASE.pop('hmcode_version',None)
        print(f'EXPLICIT NONLINEAR SETTING: {args.nonlinear}; not equivalent to historical HMcode2020',flush=True)
    if ROOT not in args.output.resolve().parents:
        raise ValueError('All outputs must stay inside peer_pngb_mcmc_review')
    Class,ident=identity()
    report={**ident,'mode':args.mode,'mcmc_executed':False,'passed':False}
    try:
        if args.mode=='block-file':
            if not args.spectra or not args.block or not args.packages:
                raise ValueError('--spectra --block --packages are required')
            result=block_file_check(args.spectra,args.block,args.packages)
        elif args.mode=='candl-file':
            if not args.spectra: raise ValueError('--spectra is required')
            result=candl_file_check(args.spectra)
        elif args.mode=='background': result=background_check(Class)
        elif args.mode=='calibration': result=calibration_check(Class,args.point)
        else:
            if args.mode=='main' and not args.packages: raise ValueError('--packages is required for main')
            if args.mode=='spectra' and (not args.spectra or ROOT not in args.spectra.resolve().parents):
                raise ValueError('--spectra must be within the review directory')
            result=cobaya_check(ident,args.fede,6600 if args.mode in ('spt','main','spectra') else 100,
                                args.mode in ('spt','main'),args.mode=='main',args.packages,args.spectra if args.mode=='spectra' else None)
        report.update(result=result,passed=True)
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
        raise
    finally:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=='__main__': main()
