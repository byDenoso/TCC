#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,pandas as pd
from astropy.io import fits
from scipy.integrate import cumulative_trapezoid
from scipy.spatial import cKDTree
H0=67.66;OM=.3111;OL=1-OM;C=299792.458;RNG=np.random.default_rng(82620261251)
ZG=np.linspace(0,1.6,30000);DCG=(C/H0)*cumulative_trapezoid(1/np.sqrt(OM*(1+ZG)**3+OL),ZG,initial=0)
def dc(z):return np.interp(z,ZG,DCG)
def xyz(ra,dec,z):
 r=dc(np.asarray(z,float));a=np.deg2rad(np.asarray(ra,float));d=np.deg2rad(np.asarray(dec,float));cd=np.cos(d);return np.c_[r*cd*np.cos(a),r*cd*np.sin(a),r*np.sin(d)]
def load(path,zmin=.4,zmax=1.1):
 with fits.open(path,memmap=True) as h:
  t=h[1].data;n=set(t.names);ra=np.asarray(t['RA'],float);de=np.asarray(t['DEC'],float);z=np.asarray(t['Z'],float);m=np.isfinite(z)&(z>=zmin)&(z<=zmax);o={'ra':ra[m],'dec':de[m],'z':z[m]}
  for k in ['WEIGHT','FRAC_TLOBS_TILES','PHOTSYS']:
   if k in n:o[k.lower()]=np.asarray(t[k])[m]
  return o
def center(ra,de,z):return xyz([ra],[de],[z])[0]
def calc(cat,c,R,n=40,mask=None,weighted=False,local=False):
 if mask is None:mask=np.ones(len(cat['z']),bool)
 ra,de,z=cat['ra'][mask],cat['dec'][mask],cat['z'][mask];w=np.asarray(cat.get('weight',np.ones(len(cat['z']))))[mask].astype(float);tr=cKDTree(xyz(ra,de,z));ids=tr.query_ball_point(c,R);obs=w[ids].sum() if weighted else len(ids);null=[]
 for _ in range(n):
  z2=z.copy()
  if local:
   b=np.floor(z/.05).astype(int)
   for bb in np.unique(b):
    ii=np.where(b==bb)[0];z2[ii]=z[RNG.permutation(ii)]
  else:z2=z[RNG.permutation(len(z))]
  mt=cKDTree(xyz(ra,de,z2));jj=mt.query_ball_point(c,R);null.append(w[jj].sum() if weighted else len(jj))
 q=np.array(null,float);mu=q.mean();sd=max(q.std(ddof=1),1);p=(np.sum(q<=obs)+1)/(len(q)+1)
 return obs/mu,(obs-mu)/sd,p,obs,mu
def pcs(c,off=25):
 o=[c]
 for j in range(3):
  for s in [-1,1]:q=c.copy();q[j]+=s*off;o.append(q)
 return o
def shape(P):
 if len(P)<20:return [np.nan]*4
 X=P-np.median(P,0);v,e=np.linalg.eigh(np.cov(X,rowvar=False));e=e[:,np.argsort(v)[::-1]];pr=X@e;ext=np.percentile(pr,95,0)-np.percentile(pr,5,0);a,b,c=ext;return a,b,c,b/max(c,1e-9)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--v12',required=True);ap.add_argument('--cand',required=True);ap.add_argument('--out',default='battery');a=ap.parse_args();out=Path(a.out);out.mkdir(exist_ok=True);cs=pd.read_csv(a.cand);cats={}
 for tr,zmin in [('LRG',.4),('ELG',.8)]:
  for reg in ['NGC','SGC']:cats[(tr,reg)]=load(f'{a.root}/{tr}_{reg}.fits',zmin,1.1)
 v12={reg:load(f'{a.v12}/LRG_{reg}.fits') for reg in ['NGC','SGC']};rows=[]
 for _,r in cs.iterrows():
  reg='NGC' if r.dec_deg>-10 else 'SGC';c=center(r.ra_deg,r.dec_deg,r.z);kind=r.kind;R=float(r.R_mpc);res=dict(candidate_id=r.candidate_id,kind=kind,ra_deg=r.ra_deg,dec_deg=r.dec_deg,z=r.z,R_mpc=R)
  for tr in ['LRG','ELG']:
   if tr=='ELG' and not(.8<=r.z<=1.1):continue
   cat=cats[(tr,reg)];q,zs,p,_,_=calc(cat,c,R,60);qw,zsw,_,_,_=calc(cat,c,R,60,weighted=True);ql,zsl,_,_,_=calc(cat,c,R,60,local=True);res.update({f'{tr}_ratio':q,f'{tr}_z':zs,f'{tr}_p':p,f'{tr}_wratio':qw,f'{tr}_wz':zsw,f'{tr}_local_ratio':ql,f'{tr}_local_z':zsl})
   pr=[calc(cat,pc,R,20)[0] for pc in pcs(c)];res[f'{tr}_center_med']=float(np.median(pr));res[f'{tr}_center_worst']=float(max(pr) if kind=='VOID' else min(pr))
   th=[]
   for _ in range(20):
    m=RNG.random(len(cat['z']))<.5;th.append(calc(cat,c,R,8,mask=m)[0])
   res[f'{tr}_thin_med']=float(np.median(th));res[f'{tr}_thin_worst']=float(np.quantile(th,.9 if kind=='VOID' else .1))
   if 'frac_tlobs_tiles' in cat:
    for cut in [.5,.8]:
     m=np.asarray(cat['frac_tlobs_tiles'],float)>=cut
     if m.sum()>10000:
      qc,zc,_,_,_=calc(cat,c,R,30,mask=m);res[f'{tr}_frac{int(cut*10)}_ratio']=qc;res[f'{tr}_frac{int(cut*10)}_z']=zc
   if 'photsys' in cat:
    ph=np.asarray(cat['photsys']).astype(str)
    for ps in np.unique(ph):
     m=ph==ps
     if m.sum()>10000:
      qp,zp,_,_,_=calc(cat,c,R,25,mask=m);res[f'{tr}_ph_{ps}_ratio']=qp;res[f'{tr}_ph_{ps}_z']=zp
  q12,z12,p12,_,_=calc(v12[reg],c,R,60);res.update(LRG_v12_ratio=q12,LRG_v12_z=z12,LRG_v12_p=p12)
  for RR in [50,75,100,130,160,200]:
   qr,zr,_,_,_=calc(cats[('LRG',reg)],c,RR,30);res[f'LRG_R{RR}_ratio']=qr;res[f'LRG_R{RR}_z']=zr
  if kind=='WALL':
   tr=cKDTree(xyz(cats[('LRG',reg)]['ra'],cats[('LRG',reg)]['dec'],cats[('LRG',reg)]['z']));ids=tr.query_ball_point(c,140);aa,bb,cc,pl=shape(tr.data[np.asarray(ids)]);res.update(axis1=aa,axis2=bb,axis3=cc,planarity=pl);pls=[]
   for pc in pcs(c):ids=tr.query_ball_point(pc,140);pls.append(shape(tr.data[np.asarray(ids)])[3])
   res['planarity_perturb_min']=float(np.nanmin(pls));res['planarity_perturb_med']=float(np.nanmedian(pls))
  rows.append(res)
 df=pd.DataFrame(rows);ver=[]
 for _,r in df.iterrows():
  if r.kind=='VOID':
   t=[r.LRG_ratio<.8,r.LRG_wratio<.82,r.LRG_local_ratio<.82,r.LRG_center_worst<.9,r.LRG_thin_worst<.9,r.LRG_v12_ratio<.85,r.ELG_ratio<.8,r.ELG_wratio<.82,r.ELG_local_ratio<.82,r.ELG_center_worst<.9,r.ELG_thin_worst<.9]
  else:t=[r.LRG_ratio>1.15,r.LRG_wratio>1.15,r.LRG_local_ratio>1.12,r.LRG_center_worst>1.10,r.LRG_thin_worst>1.10,r.LRG_v12_ratio>1.10,r.ELG_ratio>1.10,r.ELG_wratio>1.10,r.planarity>1.4,r.planarity_perturb_min>1.25]
  ver.append('SURVIVES' if all(t) else 'FAIL')
 df['verdict']=ver;df.to_csv(out/'results.csv',index=False);s={'survives':int((df.verdict=='SURVIVES').sum()),'fail':int((df.verdict=='FAIL').sum())};(out/'summary.json').write_text(json.dumps(s,indent=2));print(df[['candidate_id','kind','verdict']].to_string(index=False));print(json.dumps(s,indent=2))
if __name__=='__main__':main()
