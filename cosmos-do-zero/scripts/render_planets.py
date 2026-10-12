#!/usr/bin/env python3
"""Gera as ilustrações artísticas dos oito planetas (procedurais, sem fotografia).
Saída: src/assets/planets/<id>.webp (RGBA, fundo transparente) + saturno-globo.webp (sem anéis, usado no comparador).
Determinístico (semente fixa). Uso: python3 scripts/render_planets.py"""
import numpy as np, sys, os
from PIL import Image
S=1100  # lado do quadro das esferas
OUT=os.path.join(os.path.dirname(__file__),'..','src','assets','planets')
os.makedirs(OUT,exist_ok=True)

def hash3(ix,iy,iz,seed):
    h=(ix.astype(np.uint32)*np.uint32(73856093))^(iy.astype(np.uint32)*np.uint32(19349663))^(iz.astype(np.uint32)*np.uint32(83492791))^np.uint32(seed*2654435761%2**32)
    h=(h^(h>>np.uint32(13)))*np.uint32(1274126177)
    h=h^(h>>np.uint32(16))
    return (h&np.uint32(0xffff)).astype(np.float32)/65535.0
def vnoise(p,seed):
    x,y,z=p[0],p[1],p[2]
    xi,yi,zi=np.floor(x),np.floor(y),np.floor(z)
    xf,yf,zf=x-xi,y-yi,z-zi
    u=xf*xf*(3-2*xf); v=yf*yf*(3-2*yf); w=zf*zf*(3-2*zf)
    xi,yi,zi=xi.astype(np.int64),yi.astype(np.int64),zi.astype(np.int64)
    def c(dx,dy,dz): return hash3(xi+dx,yi+dy,zi+dz,seed)
    x00=c(0,0,0)*(1-u)+c(1,0,0)*u; x10=c(0,1,0)*(1-u)+c(1,1,0)*u
    x01=c(0,0,1)*(1-u)+c(1,0,1)*u; x11=c(0,1,1)*(1-u)+c(1,1,1)*u
    y0=x00*(1-v)+x10*v; y1=x01*(1-v)+x11*v
    return y0*(1-w)+y1*w
def fbm(p,seed,oct=6,lac=2.0,gain=0.5):
    a=1.0; tot=0; norm=0; q=p.copy()
    for o in range(oct):
        tot=tot+a*vnoise(q,seed+o*17); norm+=a; a*=gain; q=q*lac+np.float32(3.1*(o+1))
    return tot/norm
def smooth(a,b,x):
    t=np.clip((x-a)/(b-a),0,1); return t*t*(3-2*t)
def mix(a,b,t): return a*(1-t[...,None])+b*t[...,None]
def col(h): h=h.lstrip('#'); return np.array([int(h[i:i+2],16)/255 for i in (0,2,4)],dtype=np.float32)

def sphere_grid(w,h,cx,cy,R):
    ys,xs=np.mgrid[0:h,0:w].astype(np.float32)
    x=(xs-cx)/R; y=-(ys-cy)/R
    r2=x*x+y*y
    return x,y,r2
def finish(rgb,alpha,path):
    im=np.dstack([np.clip(rgb,0,1),np.clip(alpha,0,1)])
    Image.fromarray((im*255+.5).astype(np.uint8),'RGBA').save(path,'WEBP',quality=90,method=6)

LIGHT=np.array([-0.5,0.36,0.79],dtype=np.float32); LIGHT/=np.linalg.norm(LIGHT)
def shade(nx,ny,nz,albedo,ambient=0.06,wrap=0.0,terminator=0.35):
    ambient=max(ambient,0.095); wrap=max(wrap,0.28)
    d=nx*LIGHT[0]+ny*LIGHT[1]+nz*LIGHT[2]
    lam=np.clip((d+wrap)/(1+wrap),0,1)
    lam=smooth(0,terminator+0.65,lam*1.0)**0.9 if terminator else lam
    return albedo*(ambient+(1-ambient)*lam)[...,None]

def render_globe(kind,name,rotate=(0.0,0.0),size=S):
    R=size*0.47; cx=cy=size/2
    x,y,r2=sphere_grid(size,size,cx,cy,R)
    inside=r2<1
    z=np.sqrt(np.clip(1-r2,0,1))
    # coordenadas na esfera, com inclinação do eixo para texturas
    tilt=rotate[0]; spin=rotate[1]
    ct,st=np.cos(tilt),np.sin(tilt)
    px=x; py=y*ct+z*st; pz=-y*st+z*ct
    cs,ss=np.cos(spin),np.sin(spin)
    qx=px*cs+pz*ss; qz=-px*ss+pz*cs; qy=py
    P=np.stack([qx,qy,qz]).astype(np.float32)
    lat=np.arcsin(np.clip(qy,-1,1)); lon=np.arctan2(qx,qz)
    mu=z  # cos do ângulo de visada
    aa=np.clip((1-np.sqrt(r2))*R,0,1)  # suavização da borda (1 px)
    rng=np.random.default_rng(7)
    if kind=='mercurio':
        base=fbm(P*2.2,11,6)
        alb=mix(col('#6f6a64'),col('#b3aca2'),smooth(.25,.8,base))
        # crateras
        n=520; c=rng.normal(size=(n,3)); c/=np.linalg.norm(c,axis=1)[:,None]
        rad=np.clip(rng.pareto(2.2,n)*0.022+0.012,0.012,0.22)
        height=np.zeros_like(qx)
        for i in range(n):
            d=np.arccos(np.clip(qx*c[i,0]+qy*c[i,1]+qz*c[i,2],-1,1))/rad[i]
            m=d<1.7
            if not m.any(): continue
            dd=d[m]
            prof=np.where(dd<1,-(1-dd**2)*0.6,0)+np.exp(-((dd-1.05)/0.12)**2)*0.5
            ray=np.exp(-np.clip(dd-1,0,None)*1.6)*0.12*(rad[i]>0.05)
            height[m]+=prof+ray
        alb=alb*(1+height[...,None]*0.55)
        nx=px;ny=py;nz=pz
        rgb=shade(nx,ny,nz,alb,ambient=0.035,terminator=0.0)
        rgb=rgb*(0.92+0.08*mu[...,None])
    elif kind=='venus':
        warp=fbm(P*1.6+5,21,4)
        a=fbm(np.stack([qx*1.2+warp*1.7,qy*3.2+warp*0.9,qz*1.2-warp*1.3]).astype(np.float32),23,6)
        b=fbm(P*5+warp*2,29,4)
        alb=mix(col('#d9bd84'),col('#f5e6bf'),smooth(.25,.75,a*.8+b*.3))
        alb=mix(alb,col('#b88d52'),smooth(.55,.95,fbm(P*2.5+9,31,5))*0.45)
        rgb=shade(px,py,pz,alb,ambient=0.05,wrap=0.55,terminator=0.0)
        rgb=rgb*(0.85+0.2*(1-mu[...,None]**0.6))
    elif kind=='terra':
        h=fbm(P*1.55+2,41,7)
        land=smooth(.505,.54,h)
        lat_abs=np.abs(lat)/(np.pi/2)
        veg=fbm(P*3.0+8,43,5)
        dry=smooth(.35,.7,veg)*(1-smooth(.3,.7,lat_abs))*.9+smooth(.55,.85,1-np.abs(lat_abs-.28)/.28*1.0)*0.0
        landc=mix(col('#3f6b33'),col('#9a8756'),np.clip(dry*1.1+smooth(.6,.8,h)*.4,0,1))
        landc=mix(landc,col('#e9efef'),smooth(.78,.9,lat_abs)*.9)
        depth=smooth(.3,.505,h)
        ocean=mix(col('#0b2a52'),col('#1f6f9c'),depth)
        ocean=mix(ocean,col('#eaf3f5'),smooth(.86,.93,lat_abs))
        alb=mix(ocean,landc,land)
        cl=fbm(np.stack([qx*1.7,qy*3.1,qz*1.7]).astype(np.float32)+np.float32(20)+fbm(P*2,47,3)[None]*1.6,49,6)
        cl=smooth(.52,.72,cl)*0.95
        alb=mix(alb,col('#ffffff'),cl*0.92)
        rgb=shade(px,py,pz,alb,ambient=0.035,terminator=0.2)
        # brilho especular no oceano
        hvec=LIGHT+np.array([0,0,1],dtype=np.float32); hvec/=np.linalg.norm(hvec)
        spec=np.clip(px*hvec[0]+py*hvec[1]+pz*hvec[2],0,1)**60*(1-land)*(1-cl)*0.55
        rgb=rgb+spec[...,None]*np.array([1,.97,.9],dtype=np.float32)
        lim=(1-mu)**2.6
        rgb=rgb+lim[...,None]*np.array([.18,.42,.85],dtype=np.float32)*np.clip((px*LIGHT[0]+py*LIGHT[1]+pz*LIGHT[2])*.6+.55,0,1)[...,None]*1.2
    elif kind=='marte':
        a=fbm(P*1.8+1,51,6); b=fbm(P*7,53,4)
        alb=mix(col('#9b4a2b'),col('#d58a55'),smooth(.3,.75,a))
        dark=smooth(.56,.7,fbm(P*2.1+13,55,5))
        alb=mix(alb,col('#4a2a22'),dark*.55)
        alb=alb*(0.9+0.2*b[...,None])
        la=np.abs(lat)/(np.pi/2)
        alb=mix(alb,col('#f3ece6'),smooth(.9,.95,la+0.02*(b-.5)))
        rgb=shade(px,py,pz,alb,ambient=0.035,terminator=0.15)
        rgb=rgb+((1-mu)**3)[...,None]*np.array([.35,.2,.12],dtype=np.float32)*.35
    elif kind in ('jupiter','saturno','saturno-globo'):
        sat=kind!='jupiter'
        turb=fbm(np.stack([qx*2.2,qy*7,qz*2.2]).astype(np.float32),61,5)
        la=lat+(turb-.5)*(0.07 if not sat else 0.035)
        if not sat:
            pal=[(-90,'#8a7458'),(-62,'#a4876a'),(-48,'#e6d6b8'),(-36,'#b78a63'),(-27,'#efe3cc'),(-18,'#b4704a'),(-9,'#f1e4cc'),(-2,'#c58a5e'),(6,'#f4e9d3'),(15,'#b9794f'),(23,'#efe2c8'),(32,'#a98160'),(45,'#e9dcc2'),(60,'#9b8264'),(90,'#7d6a55')]
        else:
            pal=[(-90,'#9c8b66'),(-60,'#b9a678'),(-45,'#d9c9a0'),(-32,'#c3ad7f'),(-20,'#e2d3ab'),(-8,'#cdb888'),(0,'#e8dab4'),(8,'#cdb888'),(20,'#e2d3ab'),(32,'#c3ad7f'),(45,'#d9c9a0'),(60,'#b9a678'),(90,'#a39270')]
        degs=np.degrees(la)
        xs_=np.array([p[0] for p in pal],dtype=np.float32)
        cols=np.array([col(p[1]) for p in pal])
        idx=np.clip(np.searchsorted(xs_,degs)-1,0,len(pal)-2)
        t=(degs-xs_[idx])/(xs_[idx+1]-xs_[idx]); t=smooth(0,1,t)
        alb=cols[idx]*(1-t[...,None])+cols[idx+1]*t[...,None]
        fine=fbm(np.stack([qx*3,qy*30,qz*3]).astype(np.float32),67,4)
        alb=alb*(0.93+0.14*fine[...,None]*(1.0 if not sat else 0.5))
        if not sat:
            # Grande Mancha Vermelha e ovais
            def spot(lat0,lon0,wlat,wlon,colr,amt):
                dl=(lon-np.radians(lon0)+np.pi)%(2*np.pi)-np.pi
                d=((lat-np.radians(lat0))/np.radians(wlat))**2+(dl/np.radians(wlon))**2
                m=np.exp(-d**1.4*1.5)
                return m*amt
            g=spot(-22,35,6.5,11,None,1)
            ring=np.exp(-((np.sqrt(((lat-np.radians(-22))/np.radians(6.5))**2+(((lon-np.radians(35)+np.pi)%(2*np.pi)-np.pi)/np.radians(11))**2)-1.25)/.22)**2)*.35
            alb=mix(alb,col('#b4452e'),np.clip(g*.85,0,1))
            alb=mix(alb,col('#f3e9d6'),np.clip(ring,0,1))
            for (a_,b_,c_) in [(-33,-60,2.2),(-33,-100,1.8),(34,80,2.0),(41,-20,1.6)]:
                alb=mix(alb,col('#f6efe0'),np.clip(spot(a_,b_,c_,c_*1.8,None,1)*.8,0,1))
        rgb=shade(px,py,pz,alb,ambient=0.03,wrap=0.1,terminator=0.2)
        rgb=rgb*(0.8+0.25*mu[...,None]**0.5)
        if kind=='saturno-globo': pass
    elif kind=='urano':
        la=lat
        b=fbm(np.stack([qx*1.2,qy*9,qz*1.2]).astype(np.float32),71,4)
        alb=mix(col('#7fc6c6'),col('#b9e6e2'),smooth(0,1,0.5+0.5*np.sin(la*5+ (b-.5)*3))*.35+.35)
        alb=mix(alb,col('#d2f1ec'),smooth(.55,1.0,(np.sin(la)+0.0))*.4)  # calota polar clara
        rgb=shade(px,py,pz,alb,ambient=0.05,wrap=0.35,terminator=0.0)
        rgb=rgb*(0.82+0.22*mu[...,None]**0.5)
    elif kind=='netuno':
        la=lat
        turb=fbm(np.stack([qx*1.8,qy*8,qz*1.8]).astype(np.float32),81,5)
        b=np.sin(la*7+(turb-.5)*5)*.5+.5
        alb=mix(col('#1b3f9a'),col('#3f78d6'),b*.7+turb*.3)
        def spot(lat0,lon0,wlat,wlon):
            dl=(lon-np.radians(lon0)+np.pi)%(2*np.pi)-np.pi
            return np.exp(-(((lat-np.radians(lat0))/np.radians(wlat))**2+(dl/np.radians(wlon))**2)**1.3*1.4)
        alb=mix(alb,col('#10245f'),np.clip(spot(-20,20,6,12)*.85,0,1))
        cir=fbm(np.stack([qx*2.5,qy*18,qz*2.5]).astype(np.float32)+4,83,4)
        alb=mix(alb,col('#e6f0ff'),np.clip(smooth(.64,.78,cir)*smooth(.5,1,spot(-30,-10,8,40)+spot(-45,50,5,22)),0,1)*.7)
        rgb=shade(px,py,pz,alb,ambient=0.04,wrap=0.3,terminator=0.0)
        rgb=rgb*(0.8+0.25*mu[...,None]**0.5)
    # halo atmosférico fino para planetas com atmosfera densa
    alpha=np.where(inside,aa,0)
    rgb=np.where(inside[...,None],rgb,0)
    return rgb,alpha,(x,y,z,R,size)

def save_globe(kind,name,rotate=(0,0)):
    rgb,alpha,_=render_globe(kind,name,rotate)
    # recorta bordas vazias (quadro final quadrado com ~3% de margem)
    finish(rgb,alpha,os.path.join(OUT,name+'.webp')); print('ok',name,flush=True)

def render_saturn(W=1500,H=1000):
    R=H*0.30; cx=W/2; cy=H/2
    x,y,r2=sphere_grid(W,H,cx,cy,R)
    # globo (reutiliza a rotina com quadro maior renderizando num quadrado e colando)
    size=int(R*2/0.94)
    rgbg,alphag,_=render_globe('saturno','saturno',rotate=(np.radians(-26),0),size=size)
    # cola no quadro
    G=np.zeros((H,W,3),np.float32); A=np.zeros((H,W),np.float32)
    ox=int(cx-size/2); oy=int(cy-size/2)
    G[oy:oy+size,ox:ox+size]=rgbg; A[oy:oy+size,ox:ox+size]=alphag
    # anéis: plano inclinado ι em relação à visada
    T=np.radians(26.0)   # elevação do observador sobre o plano
    # plano: normal n = (0, cos T, sin T)? câmera olha para -z: ponto p=(x,y,z) com p·n=0
    n=np.array([0,np.cos(T),np.sin(T)],dtype=np.float32)
    # raio ortográfico: (x,y,zt); y*n1 + zt*n2 = 0
    zt=-(y*n[1])/n[2]
    rr=np.sqrt(x*x+zt*zt*0+ (x**2) + (0)) # placeholder
    # coordenadas no plano do anel: eixo u=x, v ao longo da projeção no plano
    # ponto no espaço 3D: (x,y,zt); raio do anel = sqrt(x^2+y^2+zt^2)
    rad=np.sqrt(x*x+y*y+zt*zt)
    # perfil radial (unidades de raio planetário): C 1.24–1.53, B 1.53–1.95, Cassini 1.95–2.02, A 2.02–2.27, Encke 2.21–2.22
    def prof(r):
        o=np.zeros_like(r); c=np.zeros(r.shape+(3,),np.float32)
        def band(a,b,op,colr,edge=0.012):
            m=smooth(a-edge,a+edge,r)*(1-smooth(b-edge,b+edge,r)); return m*op
        v=np.zeros_like(r)
        grain=fbm(np.stack([r*55,np.zeros_like(r),np.zeros_like(r)+1]).astype(np.float32),91,4)
        gr2=fbm(np.stack([r*190,np.zeros_like(r),np.zeros_like(r)+2]).astype(np.float32),93,3)
        c1=band(1.24,1.53,0.16,None)
        b1=band(1.53,1.95,0.97,None)*(0.78+0.3*grain)
        a1=band(2.02,2.27,0.8,None)*(0.8+0.25*gr2)
        a1=a1*(1-np.exp(-((r-2.215)/0.005)**2)*0.9)
        o=np.clip(c1*(0.7+0.6*grain)+b1+a1,0,1)
        tone=mix(col('#9a8a73')*np.ones_like(r)[...,None],col('#efe1c3'),np.clip(smooth(1.5,1.95,r)*0.8+grain*0.3,0,1))
        tone=mix(tone,col('#d8c7a3'),smooth(2.0,2.25,r)*.5)
        return o,tone
    o,tone=prof(rad)
    ringmask=(rad>1.2)&(rad<2.3)
    o=np.where(ringmask,o,0)
    # oclusão: ponto do anel está em frente ao planeta (zt>sqrt(1-r2)) ou fora do disco
    surf_z=np.sqrt(np.clip(1-(x*x+y*y)/ (1.0),0,1))  # planeta de raio 1 no mesmo quadro
    r2p=x*x+y*y
    in_disc=r2p<1
    front=zt>surf_z
    ring_vis=np.where(in_disc,np.where(front,o,0),o)
    # sombra do planeta nos anéis: do ponto do anel em direção à luz
    Lv=LIGHT
    # distância do raio (ponto + t*L) ao centro: mínima t>0
    px_,py_,pz_=x,y,zt
    tproj=-(px_*Lv[0]+py_*Lv[1]+pz_*Lv[2])
    dmin2=(px_**2+py_**2+pz_**2)-(px_*Lv[0]+py_*Lv[1]+pz_*Lv[2])**2
    shadow=((tproj>0)&(dmin2<1.0)).astype(np.float32)
    shadow=smooth(1.0,0.9,dmin2)*(tproj>0)
    lit=1-0.88*shadow
    # a luz vem de cima à esquerda e atrás: a face visível do anel recebe luz
    ringrgb=tone*(0.18+0.82*lit)[...,None]*1.08
    # sombra dos anéis sobre o globo (faixa escura no hemisfério iluminado)
    # ponto da superfície p=(x,y,z); em direção à luz cruza o plano em t=-(p·n)/(L·n)
    zs=surf_z
    pn=y*n[1]+zs*n[2]; ln=Lv[1]*n[1]+Lv[2]*n[2]
    tt=-pn/ln
    hx=x+tt*Lv[0]; hy=y+tt*Lv[1]; hz=zs+tt*Lv[2]
    hr=np.sqrt(hx*hx+hy*hy+hz*hz)
    ro,_=prof(hr)
    rsh=np.where((tt>0)&in_disc,ro*((hr>1.2)&(hr<2.3)),0)
    G=G*(1-0.55*rsh[...,None])
    # composição: globo sob anel (parte da frente) e anel da parte de trás sob globo
    outA=np.maximum(A,ring_vis)
    comp=G*A[...,None]*(1-ring_vis[...,None])+ringrgb*ring_vis[...,None]
    rgb=np.where(outA[...,None]>0,comp/np.maximum(outA[...,None],1e-4),0)
    # recorte final
    im=np.dstack([np.clip(rgb,0,1),np.clip(outA,0,1)])
    ys_,xs_=np.nonzero(outA>0.01)
    x0,x1,y0,y1=xs_.min(),xs_.max(),ys_.min(),ys_.max()
    pad=18
    im=im[max(0,y0-pad):y1+pad,max(0,x0-pad):x1+pad]
    Image.fromarray((im*255+.5).astype(np.uint8),'RGBA').save(os.path.join(OUT,'saturno.webp'),'WEBP',quality=90,method=6)
    print('ok saturno',im.shape,flush=True)

if __name__=='__main__':
    todo=sys.argv[1:] or ['mercurio','venus','terra','marte','jupiter','saturno-globo','saturno','urano','netuno']
    for k in todo:
        if k=='saturno': render_saturn()
        elif k=='saturno-globo': save_globe('saturno-globo','saturno-globo',(np.radians(-26),0))
        elif k=='urano': save_globe('urano','urano',(np.radians(-80),0))
        elif k=='terra': save_globe('terra','terra',(np.radians(-18),np.radians(20)))
        elif k=='jupiter': save_globe('jupiter','jupiter',(np.radians(-3),0))
        elif k=='mercurio': save_globe('mercurio','mercurio',(np.radians(-5),np.radians(40)))
        elif k=='venus': save_globe('venus','venus',(np.radians(-3),0))
        elif k=='marte': save_globe('marte','marte',(np.radians(-25),np.radians(-60)))
        elif k=='netuno': save_globe('netuno','netuno',(np.radians(-28),0))
