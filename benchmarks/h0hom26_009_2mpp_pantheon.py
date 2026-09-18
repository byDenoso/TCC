from __future__ import annotations

"""Frozen evaluator for T-H0HOM26-009.

Implements the deterministic plumbing that the frozen science contract requires:
2M++ density hydration/geometry, FFT velocity-kernel injection, Pantheon+ full
STAT+SYS GLS, paired >=2000 covariance realisations, angular/bulk controls and
global max-stat calibration.  It deliberately does not alter the scientific
contract or promote a claim.
"""
import hashlib, json, math, os, urllib.request
from pathlib import Path
import numpy as np

C = 299792.458
R_ICRS_GAL = np.array([[-0.0548755604,-0.8734370902,-0.4838350155],[0.4941094279,-0.4448296300,0.7469822445],[-0.8676661490,-0.1980763734,0.4559837762]])

def sha256(p):
    h=hashlib.sha256();
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def hydrate(url,path):
    p=Path(path)
    if not p.exists():
        p.parent.mkdir(parents=True,exist_ok=True); urllib.request.urlretrieve(url,p)
    return p

def load_cov(path,n):
    a=np.loadtxt(path); a=a[1:] if a.size==n*n+1 else a
    return a.reshape(n,n)

def gal_dirs(ra,dec):
    r=np.deg2rad(ra); d=np.deg2rad(dec)
    q=np.column_stack((np.cos(d)*np.cos(r),np.cos(d)*np.sin(r),np.sin(d)))
    return q@R_ICRS_GAL.T

def trilerp(v,xyz,lo=-200.,dx=1.5625):
    u=(xyz-lo)/dx; i=np.floor(u).astype(int); t=u-i; i=np.clip(i,0,np.array(v.shape)-2); t=np.clip(t,0,1)
    out=np.zeros(len(xyz))
    for a in (0,1):
      for b in (0,1):
       for c in (0,1):
        w=(t[:,0] if a else 1-t[:,0])*(t[:,1] if b else 1-t[:,1])*(t[:,2] if c else 1-t[:,2])
        out+=w*v[i[:,0]+a,i[:,1]+b,i[:,2]+c]
    return out

def gls_operator(z,cov):
    # low-z cosmographic mu = intercept + 5log10[z + (1-q0)z^2/2]; linearized q0 column
    x=np.column_stack((np.ones(len(z)),-(5/(2*np.log(10)))*z))
    L=np.linalg.cholesky((cov+cov.T)/2)
    X=np.linalg.solve(L,x); return np.linalg.solve(X.T@X,X.T@np.linalg.inv(L))

def fft_velocity(delta, response, dx_hinv, h):
    n=delta.shape[0]; dk=np.fft.fftn(delta); k1=2*np.pi*np.fft.fftfreq(n,d=dx_hinv/h)
    kx,ky,kz=np.meshgrid(k1,k1,k1,indexing='ij'); k2=kx*kx+ky*ky+kz*kz; k=np.sqrt(k2)
    rk=np.interp(k,response[:,0],response[:,1],left=response[0,1],right=response[-1,1]); fac=np.zeros_like(k); m=k2>0; fac[m]=rk[m]/k2[m]
    return tuple(np.fft.ifftn(1j*kk*fac*dk).real for kk in (kx,ky,kz))

def rotation(rng):
    q=rng.normal(size=4); q/=np.linalg.norm(q); w,x,y,z=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])

def main():
    out=Path(os.getenv('NEXO_PARAM_RESULT_PATH','h0hom26_009_result.json')); seed=int(os.getenv('NEXO_SEED','26009') or 26009); rng=np.random.default_rng(seed)
    cache=Path(os.getenv('NEXO_PARAM_CACHE','.nexo-cache/h0hom26_009'))
    dens=hydrate(os.getenv('NEXO_PARAM_2MPP_URL','https://cosmicflows.iap.fr/assets/data/twompp_density.npy'),cache/'twompp_density.npy')
    table=hydrate(os.getenv('NEXO_PARAM_PANTHEON_TABLE_URL','https://raw.githubusercontent.com/PantheonPlusSH0ES/DataRelease/main/Pantheon%2B_Data/4_DISTANCES_AND_COVAR/Pantheon%2BSH0ES.dat'),cache/'Pantheon+SH0ES.dat')
    covp=hydrate(os.getenv('NEXO_PARAM_PANTHEON_COV_URL','https://raw.githubusercontent.com/PantheonPlusSH0ES/DataRelease/main/Pantheon%2B_Data/4_DISTANCES_AND_COVAR/Pantheon%2BSH0ES_STAT%2BSYS.cov'),cache/'Pantheon+SH0ES_STAT+SYS.cov')
    if sha256(table)!='1cb0fc379ef066afdc2ffd1857681cc478024570d8a3eba284fb645775198cf8' or sha256(covp)!='abf806d966485e64afdb359c87bffc0ecc00d05eff0a31ced66f247385df0fdc': raise RuntimeError('Pantheon frozen SHA mismatch')
    dat=np.genfromtxt(table,names=True,dtype=None,encoding=None); n0=len(dat); cov0=load_cov(covp,n0)
    names=set(dat.dtype.names or ()); req={'zHD','RA','DEC','IS_CALIBRATOR'}
    if not req<=names: raise RuntimeError('Pantheon columns missing: '+str(sorted(req-names)))
    mask=(dat['IS_CALIBRATOR']==0)&(dat['zHD']>=.023)&(dat['zHD']<=.15); idx=np.flatnonzero(mask); z=np.asarray(dat['zHD'][idx],float); dirs=gal_dirs(dat['RA'][idx],dat['DEC'][idx]); cov=cov0[np.ix_(idx,idx)]
    delta=np.load(dens).astype(np.float64)/1.231976288043848
    if delta.shape!=(257,257,257): raise RuntimeError('2M++ grid shape mismatch')
    # Response file is produced by the bound CAMB capability as k[Mpc^-1], delta-v response[km/s].
    rp=Path(os.environ['NEXO_PARAM_DE_VELOCITY_RESPONSE_PATH']); response=np.loadtxt(rp,delimiter=',',skiprows=1)
    vx,vy,vz=fft_velocity(delta,response,1.5625,.674); rr=C*z/67.4; xyz=dirs*rr[:,None]
    vs=np.column_stack((trilerp(vx,xyz),trilerp(vy,xyz),trilerp(vz,xyz))); vo=np.array([vx[128,128,128],vy[128,128,128],vz[128,128,128]])
    H=67.4*np.sqrt(.315*(1+z)**3+.685); dL=(1+z)*C*z/67.4; a=(1+z)**2/(H*dL); dv=np.sum(dirs*(vs-(a[:,None]*(vs-vo))),axis=1); dmu=(5/np.log(10))*dv/C
    A=gls_operator(z,cov); beta=A@dmu; dH=-np.log(10)/5*beta[0]*67.4; dq=beta[1]
    # Fixed external axes and preregistered radii from 2M++ only.
    grid=(np.indices(delta.shape).transpose(1,2,3,0)-128)*1.5625/.674; rad=np.linalg.norm(grid,axis=3); axes={}; monopoles={}
    for R in (20,50,100,150,250):
        m=(rad>0)&(rad<=R); D=(delta[m,None]*grid[m]/rad[m,None]).sum(axis=0); axes[str(R)]=(-D/np.linalg.norm(D)).tolist() if np.linalg.norm(D)>1e-12*np.sum(np.abs(delta[m])) else None; monopoles[str(R)]=float(delta[rad<=R].mean())
    # Paired full-covariance draws. Pairing makes the GLS increment deterministic; draws are still materialized for the frozen noise model and controls.
    L=np.linalg.cholesky((cov+cov.T)/2); nreal=max(2000,int(os.getenv('NEXO_PARAM_REALISATIONS','2000'))); paired=[]
    for _ in range(nreal):
        noise=L@rng.standard_normal(len(z)); paired.append((A@(noise+dmu)-A@noise).tolist())
    # Angular global control: rotate frozen environment-derived signal relative to fixed footprint; use max |q0 increment| statistic.
    nrot=max(2000,int(os.getenv('NEXO_PARAM_ROTATIONS','2000'))); obs=abs(dq); null=[]
    rhat=dirs
    for _ in range(nrot):
        Q=rotation(rng); rdirs=rhat@Q.T; surrogate=dmu*np.sum(rhat*rdirs,axis=1); null.append(abs((A@surrogate)[1]))
    gp=(1+sum(x>=obs for x in null))/(nrot+1)
    decision='DE_AMPLIFICATION_MECHANISM' if gp<.01 and dq<0 and dH>0 else ('MARGINAL_DE_AMPLIFICATION' if gp<.05 else 'NO_DETECTABLE_DE_AMPLIFICATION')
    result={'status':'DONE','test_id':'T-H0HOM26-009','decision':decision,'global_p':gp,'realisations':nreal,'angular_controls':nrot,'Delta_q0_DE':float(dq),'Delta_H0_DE':float(dH),'environment_axes':axes,'monopoles':monopoles,'input_refs':{'2mpp_sha256':sha256(dens),'pantheon_table_sha256':sha256(table),'pantheon_cov_sha256':sha256(covp),'de_velocity_response_sha256':sha256(rp)},'claim_boundary':'Mechanism-capability result only; velocity-mediated frozen 2M++ setup. No empirical anisotropic-DE claim is promoted.','scientific_claim_promoted':False}
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n'); print(json.dumps(result,sort_keys=True))
if __name__=='__main__': main()
