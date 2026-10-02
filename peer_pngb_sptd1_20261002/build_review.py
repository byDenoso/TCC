"""Build local review envelopes only. Does not call Cobaya or CLASS."""
import copy
import hashlib
import json
from pathlib import Path
import re
import yaml

ROOT = Path(__file__).resolve().parent
SPT_COMMIT = 'f22611a9671d50af6135f048a2ea3f43ef4c2f62'
SPT_TEMPLATE_SHA256 = '67850f20e2b3f53530e7f47ef78e24f21ea20b5e69c95730409530490f1f344e'
COSMO = set('A As DHBBN YHe Y_p age clamp cosmomc_theta logA H0 ns ombh2 omch2 omega_de omegam omegamh2 rdrag s8h5 s8omegamp25 s8omegamp5 sigma8 tau theta_MC_100 zrei'.split())
BOUNDS = {'ombh2': (.017,.027), 'omch2': (.09,.15), 'theta_s_100': (1.030,1.050),
          'logA': (2.6,3.5), 'ns': (.90,1.10), 'tau': (0.,.10), 'peer_fede': (0.,.18)}
REFS = {'ombh2': .0226, 'omch2': .12, 'theta_s_100': 1.041, 'logA': 3.06,
        'ns': .98, 'tau': .06, 'peer_fede': .08}
PROPOSAL = {'ombh2': 6.5e-5, 'omch2': .0011, 'theta_s_100': .001,
            'logA': .0036, 'ns': .0033, 'tau': .005, 'peer_fede': .008}
STACKS = {
    'spt_only': [],
    'spt_lowell': ['planck_2018_lowl.TT', 'planck_2018_lowl.EE_sroll2'],
    'external_no_shoes': ['planck_2018_lowl.TT', 'planck_2018_lowl.EE_sroll2',
                          'planck_2018_lensing.native', 'bao.desi_dr2.desi_bao_all'],
    'historical_with_shoes': ['planck_2018_lowl.TT', 'planck_2018_lowl.EE_sroll2',
                             'planck_2018_lensing.native', 'bao.desi_dr2.desi_bao_all',
                             'peer_integration.shoes.SH0ESGaussian'],
}


def template_contract():
    path = ROOT / 'reference/spt_cobaya_ttteee.yaml'
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != SPT_TEMPLATE_SHA256:
        raise ValueError('Official template hash mismatch')
    text = re.sub(r"!!python/name:([^\s]+)\s+''", r"'\1'", data.decode())
    template = yaml.safe_load(text)
    if template['likelihood']['candl_like']['data_set_file'] != 'spt_candl_data.SPT3G_D1_TnE':
        raise ValueError('Wrong dataset')
    return {p: v for p,v in template['params'].items() if p not in COSMO}, template['prior']


def make_review(model, stack):
    if model not in ('LCDM', 'PNGB_ETA01') or stack not in STACKS:
        raise ValueError('Unrecognized comparison')
    nuisance, priors = template_contract()
    params = {k: {'prior': {'min':lo,'max':hi},
                  'ref': {'dist':'norm','loc':REFS[k],'scale':PROPOSAL[k]*3},
                  'proposal':PROPOSAL[k]}
              for k,(lo,hi) in BOUNDS.items()}
    if model == 'LCDM':
        params['peer_fede'] = {'value':0.0}
    if stack == 'spt_only':
        params['tau'] = {'prior':{'dist':'norm','loc':.051,'scale':.006},
                         'ref':.051,'proposal':.003}
    params.update(copy.deepcopy(nuisance))
    for name in ('H0','Omega_m','sigma8','rs_drag'):
        params[name] = {'derived':True}
    params['S8'] = {'derived':'lambda sigma8, Omega_m: sigma8*(Omega_m/0.3)**0.5'}
    likes = {'candl_like': {'class':'candl.interface.CandlCobayaLikelihood',
                          'data_set_file':'spt_candl_data.SPT3G_D1_TnE',
                          'clear_internal_priors':True, 'lensing':False,
                          'feedback':True, 'stop_at_error':True}}
    for name in STACKS[stack]:
        likes[name] = {'stop_at_error':True}
    if any(name.startswith('planck_') for name in likes):
        params['A_planck'] = {'prior':{'dist':'norm','loc':1.,'scale':.0025},
                             'ref':1.,'proposal':.0005,'renames':'calPlanck'}
    if 'peer_integration.shoes.SH0ESGaussian' in likes:
        likes['peer_integration.shoes.SH0ESGaussian'].update(python_path=str(ROOT),
                                              mean=73.04, sigma=1.04)
    # Copy the SPT prior exactly once. Do not inherit its cosmological tau prior.
    cfg = {'theory':{'peer_integration.cobaya_adapter.PEERClassy':{
        'python_path':str(ROOT), 'path':'REQUIRES_PATCHED_CLASSY_BUILD',
        'execution_review_passed':False, 'expected_classy_sha256':'',
        'stop_at_error':True, 'peer_eta':.1, 'peer_log10_zc':3.81,'peer_theta_i':2.89155,
        'extra_args':{'N_ncdm':1, 'm_ncdm':.06, 'T_ncdm':.71611,
                      'N_ur':3.046-.71611**4/(4/11)**(4/3),
                      'Omega_k':0., 'A_L':1., 'recombination':'HyRec',
                      'YHe':'BBN', 'non_linear':'hmcode', 'hmcode_version':'2020',
                      'lensing':'yes', 'output':'tCl,pCl,lCl,mPk', 'l_max_scalars':6600, 'P_k_max_1/Mpc':20}}},
        'likelihood':likes, 'params':params, 'prior':copy.deepcopy(priors),
        'sampler':{'mcmc':{'Rminus1_stop':.01, 'Rminus1_cl_stop':.05,
                            'burn_in':50, 'learn_proposal':True,
                            'learn_proposal_Rminus1_max':30., 'max_samples':50000,
                            'proposal_scale':1.2, 'output_every':'60s',
                            'measure_speeds':True, 'oversample_power':.4,
                            'oversample_thin':False, 'drag':False}},
        'force':False, 'resume':False, 'timing':True,
        'output':f'REQUIRES_APPROVED_OUTPUT/{stack}/{model}/chain'}
    return {'status':'LOCAL_REVIEW_ONLY_NOT_RUNNABLE', 'model':model, 'stack':stack,
            'approvals':{'data_stack':stack in ('spt_only','historical_with_shoes'),
                         'angular_coordinate_change':True,
                         'CLASS_recombination_and_precision_contract':False,
                         'campaign_requested':True,'resources_and_physical_gates':False,
                         'publication_by_parent_only':True},
            'software':{'class_base':'3.3.4 patched exact KG pNGB eta',
                        'cobaya':'3.6.2','candl':'2.0.3','spt_candl_data':'3.0.1',
                        'spt_commit':SPT_COMMIT,'spt_template_sha256':SPT_TEMPLATE_SHA256},
            'spt_nuisance_count':len(nuisance),'spt_external_prior_count':len(priors),
            'angular_warning':'theta_s_100 is exact CLASS theta_s, NOT CAMB cosmomc_theta or theta_star; change requires approval',
            'cobaya_preview':cfg}


def main():
    dest = ROOT / 'configs_review'
    dest.mkdir(exist_ok=True)
    for stack in STACKS:
        for model in ('LCDM','PNGB_ETA01'):
            (dest/f'{stack}_{model}.review.json').write_text(
                json.dumps(make_review(model,stack),indent=2)+'\n')
    nuisance, priors = template_contract()
    (ROOT/'nuisance_contract.json').write_text(json.dumps({'params':nuisance,'prior':priors},indent=2)+'\n')
    print('Wrote eight local review envelopes; no sampler or CLASS was called')

if __name__ == '__main__':
    main()
