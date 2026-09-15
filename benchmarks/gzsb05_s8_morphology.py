#!/usr/bin/env python3
from __future__ import annotations
import json, math
from pathlib import Path

OUT=Path('benchmark_result.json')
BINS=[
(0.1375,0.83,0.02),(0.2095,0.82,0.07),(0.2870,0.86,0.06),(0.3910,0.84,0.03),(0.6260,0.94,0.04)]

def wls(X,y,s):
    p=len(X[0]); A=[[0.0]*p for _ in range(p)]; b=[0.0]*p
    for row,yi,si in zip(X,y,s):
        w=1/(si*si)
        for j in range(p):
            b[j]+=w*row[j]*yi
            for k in range(p): A[j][k]+=w*row[j]*row[k]
    for i in range(p):
        q=max(range(i,p),key=lambda r:abs(A[r][i])); A[i],A[q]=A[q],A[i]; b[i],b[q]=b[q],b[i]
        d=A[i][i]
        for k in range(i,p): A[i][k]/=d
        b[i]/=d
        for r in range(p):
            if r==i: continue
            f=A[r][i]
            for k in range(i,p): A[r][k]-=f*A[i][k]
            b[r]-=f*b[i]
    beta=b
    chi2=sum(((yi-sum(v*c for v,c in zip(row,beta)))/si)**2 for row,yi,si in zip(X,y,s))
    return beta,chi2

def student_t_nll(mu,nu=3.0):
    nll=0.0
    for _,y,s in BINS:
        r=(y-mu)/s
        nll += math.log(s)+0.5*(nu+1)*math.log1p(r*r/nu)
    return nll

def main():
    z=[r[0] for r in BINS]; y=[r[1] for r in BINS]; s=[r[2] for r in BINS]
    const_b,const_chi=wls([[1] for _ in z],y,s)
    lin_b,lin_chi=wls([[1,x] for x in z],y,s)
    step_b,step_chi=wls([[1,1 if i==4 else 0] for i in range(5)],y,s)
    # Robust Student-t location: bounded deterministic grid, nu=3 frozen.
    grid=[0.78+i*0.0001 for i in range(1801)]
    t_mu=min(grid,key=student_t_nll); t_nll=student_t_nll(t_mu)
    # Gaussian NLL terms common across Gaussian models cancel, so AIC differences use chi2+2k.
    models={
      'constant':{'k':1,'chi2':const_chi,'aic_rel':const_chi+2,'params':{'S8':const_b[0]}},
      'smooth_linear':{'k':2,'chi2':lin_chi,'aic_rel':lin_chi+4,'params':{'intercept':lin_b[0],'slope_per_z':lin_b[1]}},
      'fixed_highz_step':{'k':2,'chi2':step_chi,'aic_rel':step_chi+4,'params':{'low_baseline':step_b[0],'highz_offset':step_b[1]}},
      'student_t_location_nu3':{'k':1,'nll_reduced':t_nll,'params':{'S8':t_mu,'nu':3.0}},
    }
    best=min(('constant','smooth_linear','fixed_highz_step'),key=lambda m:models[m]['aic_rel'])
    delta_linear=models['smooth_linear']['aic_rel']-models['fixed_highz_step']['aic_rel']
    verdict='LOCALIZED_S8_MORPHOLOGY' if best=='fixed_highz_step' and delta_linear>=2 else 'NO_DECISIVE_LOCALIZATION'
    result={
      'schema':'nexo.gzsb05.s8-morphology.v1','test_id':'GZSB-05A-EROSITA-S8-MORPHOLOGY-STANDALONE','status':'PASS',
      'input':{'source':'Artis et al. eRASS1 growth redshift-bin published S8 summaries','arxiv':'2410.09499','bins':BINS,'covariance':'UNAVAILABLE_SUMMARY_BOUNDARY'},
      'models':models,'best_gaussian_aic_model':best,'delta_aic_linear_minus_step':delta_linear,'verdict':verdict,
      'claim_boundary':'Standalone S8-summary morphology discriminant only. It does not jointly model sigma_X or B_X and does not satisfy full GZSB-05. Bin covariance is unavailable here, so this result may prioritize but cannot close the parent test.',
      'next_test':'Run full GZSB-05 jointly across S8, sigma_X and B_X with official covariance when available.'}
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True),encoding='utf-8')
    print(json.dumps({'status':'PASS','test_id':result['test_id'],'verdict':verdict,'best':best,'output':str(OUT)},sort_keys=True))

if __name__=='__main__': main()
