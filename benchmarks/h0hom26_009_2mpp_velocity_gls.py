from __future__ import annotations
import argparse, hashlib, json, os, subprocess, tempfile
from pathlib import Path
import numpy as np
from scipy.interpolate import RegularGridInterpolator
C=299792.458
def sha256(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def load_cov(path,n):
 a=np.loadtxt(path).ravel()
 if a.size==n*n+1:a=a[1:]
 if a.size!=n*n:raise ValueError(f'covariance size {a.size} != {n*n}')
 return a.reshape(n,n)
def worker(req,out):
 import camb
 r=json.loads(Path(req).read_text());ks=np.asarray(r['k_mpc']);z=np.array([0.0]);c=r['cosmology']
 p=camb.CAMBparams();p.set_cosmology(H0=c['H0'],ombh2=c['ombh2'],omch2=c['omch2'],mnu=c['mnu'],tau=c['tau']);p.InitPower.set_params(As=c['As'],ns=c['ns'])
 p.set_dark_energy(w=r['w0'],wa=0,cs2=r['cs2'],dark_energy_model='fluid');p.set_matter_power(redshifts=[0],kmax=max(.2,float(ks.max())*1.1));p.WantTransfer=True
 res=camb.get_transfer_functions(p,only_time_sources=True);ev=res.get_redshift_evolution(ks,z,vars=['delta_tot','v_newtonian_cdm'])[:,0,:]
 Path(out).write_text(json.dumps({'delta_tot':ev[:,0].tolist(),'v_newtonian_cdm':ev[:,1].tolist()}));return 0
def camb_ratio(launcher,script,ks,w0,cs2,cosmo):
 def one(cs):
  with tempfile.TemporaryDirectory() as d:
   q=Path(d)/'q.json';o=Path(d)/'o.json';q.write_text(json.dumps({'k_mpc':ks.tolist(),'w0':w0,'cs2':cs,'cosmology':cosmo}))
   p=subprocess.run([launcher,script,'--worker',str(q),str(o)],capture_output=True,text=True,timeout=180)
   if p.returncode:raise RuntimeError(p.stderr[-1000:])
   x=json.loads(o.read_text());return np.asarray(x['v_newtonian_cdm'])/np.asarray(x['delta_tot'])
 return one(cs2)-one(1.0)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--worker',action='store_true');ap.add_argument('worker_args',nargs='*');ap.add_argument('--density');ap.add_argument('--table');ap.add_argument('--cov');ap.add_argument('--launcher');ap.add_argument('--out',default='result.json');ap.add_argument('--seed',type=int,default=26009009);ap.add_argument('--nreal',type=int,default=2000);a=ap.parse_args()
 if a.worker:return worker(a.worker_args[0],a.worker_args[1])
 if a.nreal<2000:raise ValueError('frozen contract requires >=2000 realisations')
 expected={'table':'1cb0fc379ef066afdc2ffd1857681cc478024570d8a3eba284fb645775198cf8','cov':'abf806d966485e64afdb359c87bffc0ecc00d05eff0a31ced66f247385df0fdc'}
 if sha256(a.table)!=expected['table'] or sha256(a.cov)!=expected['cov']:raise ValueError('Pantheon input SHA mismatch')
 cube=np.load(a.density,mmap_mode='r')
 if cube.shape!=(257,257,257):raise ValueError('2M++ density grid shape mismatch')
 b=0.315**0.55/0.43;dm=np.asarray(cube,dtype=np.float32)/b;h=.674;spacing=1.5625/h;coords=(np.arange(257)-128)*spacing
 X,Y,Z=np.meshgrid(coords,coords,coords,indexing='ij',sparse=True);rr=np.sqrt(X*X+Y*Y+Z*Z);geom={}
 for R in [20,50,100,150,250]:
  m=rr<=R;vals=dm[m];xyz=(np.argwhere(m)-128).astype(float)*spacing;r=np.linalg.norm(xyz,axis=1);nz=r>0;u=np.zeros_like(xyz);u[nz]=xyz[nz]/r[nz,None];D=(vals[:,None]*u).sum(0);norm=float(np.linalg.norm(D));axis=(-D/norm).tolist() if norm>1e-12*float(np.abs(vals).sum()) else None;geom[str(R)]={'monopole':float(vals.mean()),'dipole':D.tolist(),'axis':axis}
 tab=np.genfromtxt(a.table,names=True,dtype=None,encoding=None);names=set(tab.dtype.names or []);need={'zHD','IS_CALIBRATOR','RA','DEC'}
 if not need<=names:raise ValueError('Pantheon table missing required footprint columns')
 sel=(tab['IS_CALIBRATOR']==0)&(tab['zHD']>=.023)&(tab['zHD']<=.15);idx=np.flatnonzero(sel);z=np.asarray(tab['zHD'][sel],float);ra=np.deg2rad(np.asarray(tab['RA'][sel],float));dec=np.deg2rad(np.asarray(tab['DEC'][sel],float));n=np.c_[np.cos(dec)*np.cos(ra),np.cos(dec)*np.sin(ra),np.sin(dec)]
 cov=load_cov(a.cov,len(tab))[np.ix_(idx,idx)];L=np.linalg.cholesky(cov);ci=np.linalg.inv(cov);xq=-(5/(2*np.log(10)))*z;A=np.c_[np.ones_like(z),xq];G=np.linalg.inv(A.T@ci@A)@A.T@ci
 wgrid=np.linspace(-1.2,-.8,5);csgrid=10.**np.arange(-6,1);radii=[50,100,150,250];N=257;k1=2*np.pi*np.fft.fftfreq(N,d=spacing);kx,ky,kz=np.meshgrid(k1,k1,k1,indexing='ij',sparse=True);kmag=np.sqrt(kx*kx+ky*ky+kz*kz);fk=np.fft.fftn(dm)
 cosmo={'H0':67.4,'ombh2':.0224,'omch2':.12,'mnu':.06,'tau':.054,'As':2.1e-9,'ns':.965};rows=[];rng=np.random.default_rng(a.seed);script=str(Path(__file__).resolve())
 for w0 in wgrid:
  for cs2 in csgrid:
   kval=np.unique(np.clip(kmag.ravel(),1e-4,.3));kval=np.quantile(kval,np.linspace(0,1,256));dr=camb_ratio(a.launcher,script,kval,w0,float(cs2),cosmo);ker=np.interp(kmag,kval,dr,left=dr[0],right=dr[-1]);ker[0,0,0]=0;phi=fk*ker;den=np.where(kmag==0,np.inf,kmag*kmag)
   vx=np.fft.ifftn(1j*kx/den*phi).real;vy=np.fft.ifftn(1j*ky/den*phi).real;vz=np.fft.ifftn(1j*kz/den*phi).real;interps=[RegularGridInterpolator((coords,coords,coords),v,bounds_error=False,fill_value=0) for v in (vx,vy,vz)]
   rcom=C*z/cosmo['H0'];pos=n*rcom[:,None];vs=np.column_stack([f(pos) for f in interps]);vo=np.array([f([[0,0,0]])[0] for f in interps]);dL=(C/cosmo['H0'])*z*(1+z);fac=(1+z)**2/(cosmo['H0']*dL);dd=(vs*n).sum(1)-fac*((vs-vo)*n).sum(1);dmu=(5/np.log(10))*dd/C;beta=G@dmu;dq=float(beta[1]);dh=float(-(np.log(10)/5)*beta[0]*cosmo['H0'])
   for R in radii:
    axis=geom[str(R)]['axis'];amp=float(np.mean(dmu*(n@np.asarray(axis)))) if axis else float('nan');rows.append({'w0':float(w0),'cs2':float(cs2),'R':R,'Delta_q0_DE':dq,'Delta_H0_DE':dh,'D_mu_DE':amp})
 maxstats=[]
 for _ in range(a.nreal):
  noise=L@rng.standard_normal(len(z));maxstats.append(float(np.max(np.abs(G@noise))))
 obs=max(max(abs(r['Delta_q0_DE']),abs(r['Delta_H0_DE'])/cosmo['H0']) for r in rows);gp=(1+sum(x>=obs for x in maxstats))/(a.nreal+1)
 out={'schema':'nexo.h0hom26-009.v1','status':'COMPLETE','n_selected':len(z),'n_realisations':a.nreal,'geometry':geom,'grid_results':rows,'global_p':gp,'input_sha256':{'density':sha256(a.density),**expected},'claim_boundary':'Velocity-mediated incremental DE-clustering mechanism test only; no real-Universe anisotropic-DE claim.'};Path(a.out).write_text(json.dumps(out,indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
