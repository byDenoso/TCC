#!/usr/bin/env python3
from __future__ import annotations
import json, math
from pathlib import Path

OUT=Path('benchmark_result.json')
BINS=[(0.1375,0.83,0.02),(0.2095,0.82,0.07),(0.2870,0.86,0.06),(0.3910,0.84,0.03),(0.6260,0.94,0.04)]

def wls_line(rows):
    sw=sx=sy=sxx=sxy=0.0
    for z,y,s in rows:
        w=1/(s*s); sw+=w; sx+=w*z; sy+=w*y; sxx+=w*z*z; sxy+=w*z*y
    det=sw*sxx-sx*sx
    a=(sy*sxx-sx*sxy)/det; b=(sw*sxy-sx*sy)/det
    var_b=sw/det
    chi2=sum(((y-a-b*z)/s)**2 for z,y,s in rows)
    return {'intercept':a,'slope_per_z':b,'slope_sigma':math.sqrt(var_b),'slope_z':b/math.sqrt(var_b),'chi2':chi2}

def main():
    full=wls_line(BINS)
    loo=[]
    for i in range(len(BINS)):
        fit=wls_line(BINS[:i]+BINS[i+1:])
        fit.update({'omitted_bin':i+1,'omitted_z':BINS[i][0],'slope_change_sigma_full':abs(fit['slope_per_z']-full['slope_per_z'])/full['slope_sigma']})
        loo.append(fit)
    max_change=max(x['slope_change_sigma_full'] for x in loo)
    sign_stable=all((x['slope_per_z']>0)==(full['slope_per_z']>0) for x in loo)
    highz=next(x for x in loo if x['omitted_bin']==5)
    # Frozen standalone diagnostic rule: influence-dominated if any single-bin omission changes slope >=1 full-fit sigma,
    # flips sign, or omission of the highest-z bin reduces |slope z| below 1.
    fragile=(max_change>=1.0) or (not sign_stable) or (abs(highz['slope_z'])<1.0)
    verdict='SINGLE_BIN_INFLUENCE_DOMINATED' if fragile else 'BROAD_S8_TREND_DIAGNOSTIC'
    result={'schema':'nexo.gzsb06.s8-influence.v1','test_id':'GZSB-06A-EROSITA-S8-LOO-INFLUENCE-STANDALONE','status':'PASS','input':{'source':'Artis et al. eRASS1 published five-bin S8 summaries','arxiv':'2410.09499','bins':BINS,'covariance':'UNAVAILABLE_SUMMARY_BOUNDARY'},'full_linear_fit':full,'leave_one_bin_out':loo,'max_slope_change_sigma_full':max_change,'slope_sign_stable':sign_stable,'highz_omission_slope_z':highz['slope_z'],'verdict':verdict,'claim_boundary':'Retrospective five-bin S8 leave-one-out influence diagnostic. This is not the prospectively frozen threshold-grid/multiplicity test required to close full GZSB-06 and uses diagonal summary errors because native covariance is unavailable.','next_test':'If native covariance becomes available, run the predeclared threshold-grid GZSB-06 with multiplicity correction; otherwise prioritize an independent selection/calibrator lane.'}
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True),encoding='utf-8')
    print(json.dumps({'status':'PASS','test_id':result['test_id'],'verdict':verdict,'max_change_sigma':max_change,'highz_omission_slope_z':highz['slope_z'],'output':str(OUT)},sort_keys=True))

if __name__=='__main__': main()
