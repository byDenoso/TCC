import type { StagePaint } from '../stage-surface';

const dir = '/renders/formation/';
const names = ['mercurio','venus','terra','marte','jupiter','saturno','urano','netuno'];
const orbitalRadii = [48,73,97,120,156,194,232,269];
const diameters = [8,14,16,11,42,58,24,23];
const phases = [2.79,4.65,.46,1.98,3.22,.12,5.11,2.43];
const tau = Math.PI * 2;
const clamp = (n: number) => Math.max(0, Math.min(1,n));
const ease = (n: number) => { const x = clamp(n); return x*x*(3-2*x); };

function sun(c: CanvasRenderingContext2D, x: number, y: number, size: number) {
  const glow=c.createRadialGradient(x,y,0,x,y,size);
  glow.addColorStop(0,'#fffbdd'); glow.addColorStop(.075,'#fff6cc');
  glow.addColorStop(.14,'rgba(255,212,139,.96)'); glow.addColorStop(.25,'rgba(255,160,69,.46)');
  glow.addColorStop(.58,'rgba(236,105,41,.10)'); glow.addColorStop(1,'rgba(232,96,33,0)');
  c.fillStyle=glow; c.fillRect(x-size,y-size,size*2,size*2);
}

function drawCloud(s: StagePaint, t: number) {
  const c=s.ctx, clouds=s.image(dir+'cloud.webp'), stars=s.image(dir+'cloud-stars.webp');
  if (!clouds) return false;
  c.save(); c.translate(320,177);
  const zoom=1.11+.066*t;
  c.rotate(-.026+.043*t); c.scale(zoom,zoom);
  c.drawImage(clouds,-330,-186,660,372);
  if (stars) {
    c.globalCompositeOperation='screen'; c.rotate(-.022*t); c.translate(-4*t,2*t);
    c.drawImage(stars,-330,-186,660,372);
  }
  c.restore();
  const vignette=c.createRadialGradient(324,177,86,320,175,350);
  vignette.addColorStop(0,'rgba(5,10,15,0)'); vignette.addColorStop(1,'rgba(2,7,15,.67)');
  c.fillStyle=vignette; c.fillRect(0,0,640,360);
  // Two convergent streams trace gas flow. Depth and density grow toward the centre.
  for (let i=0;i<48;i++) {
    const d=(i*.61803+.11*t)%1, side=i%2===0?1:-1, a=side*(d*1.48+.10*t)+.37;
    const r=36+(1-d)*216, z=Math.sin(i*76.41);
    const x=322+side*r*Math.cos(a), y=174+side*.53*r*Math.sin(a)+z*21*(1-d);
    c.fillStyle=`rgba(218,178,138,${.16+.43*d})`;c.beginPath();c.arc(x,y,.65+(z+1)*.45,0,tau);c.fill();
  }
  s.label('Barnard 59',25,325,{size:21});
  return true;
}

function ringTexture(s: StagePaint, x: number, y: number, radius: number, tilt: number, t: number) {
  const c=s.ctx, disc=s.image(dir+'disc.webp'), inner=s.image(dir+'disc-inner.webp');
  if (!disc) return false;
  c.save(); c.translate(x,y); c.rotate(-.17); c.scale(1,tilt); c.rotate(.09*t);
  c.drawImage(disc,-radius,-radius,2*radius,2*radius);
  if (inner) { c.rotate(.22*t); c.drawImage(inner,-radius,-radius,2*radius,2*radius); }
  c.restore();
  return true;
}

function flattened(s: StagePaint, t: number) {
  const c=s.ctx;
  const inclination=.64-.24*ease(t);
  if (!ringTexture(s,320,174,322,inclination,t)) return false;
  sun(c,320,174,46);
  c.strokeStyle='rgba(224,234,241,.68)';c.lineWidth=1;
  c.beginPath();c.moveTo(325,158);c.lineTo(348,53);c.lineTo(370,53);c.stroke();
  s.label('Sol jovem',377,52,{size:18});
  return true;
}

function grains(s: StagePaint, t: number) {
  const c=s.ctx, observed=s.image(dir+'hl-tauri.webp');
  if (!observed) return false;
  const cx=191,cy=179,rot=-.28,tilt=.61;
  c.save();c.translate(cx,cy);c.rotate(rot);c.scale(1,tilt);
  c.save();c.rotate(t*.11);c.drawImage(observed,-198,-198,396,396);c.restore();
  c.strokeStyle='rgba(159,223,236,.80)';c.lineWidth=1.6;c.setLineDash([4,5]);
  c.beginPath();c.arc(0,0,105,0,tau);c.stroke();c.restore();
  const lineX=cx+104*Math.cos(rot),lineY=cy+104*Math.sin(rot);
  c.strokeStyle='#a2d5de';c.lineWidth=1;c.beginPath();c.moveTo(lineX,lineY);c.lineTo(318,98);c.lineTo(343,98);c.stroke();
  s.label('Linha do gelo',213,81,{size:18,color:'#c3eef0'});
  // Mark the schematic snow line independently from HL Tauri’s observed gaps.
  sun(c,cx,cy,23);
  for (const [idx,kind] of ['mineral','ice'].entries()) {
    const x=489,y=103+idx*157, rock=s.image(dir+kind+'.webp');
    if (rock) for (const [offset,dy,r,spin] of [[-47,-12,32,-.56],[44,15,23,1.1],[2,1,103,.2]]) {
      c.save();c.translate(x+offset*(1.21-.25*t),y+dy*(1.3-.35*t));c.rotate(spin+.32*t);
      c.drawImage(rock,-r/2,-r/2,r,r);c.restore();
    }
    s.label(idx?'Rocha e gelo':'Rocha e metal',x,y+57,{align:'center',size:17});
  }
  return true;
}

function planets(s: StagePaint, t: number) {
  const c=s.ctx, cx=316,cy=169, tilt=.435,rot=-.17;
  const position=(r:number,a:number) => {
    const x=r*Math.cos(a), y=r*Math.sin(a)*tilt;
    return {x:cx+x*Math.cos(rot)-y*Math.sin(rot),y:cy+x*Math.sin(rot)+y*Math.cos(rot),depth:Math.sin(a)};
  };
  c.save();c.translate(cx,cy);c.rotate(rot);
  orbitalRadii.forEach((r,i)=>{
    c.strokeStyle=i<4?'rgba(214,167,124,.28)':'rgba(139,173,199,.28)';
    c.lineWidth=.9;c.beginPath();c.ellipse(0,0,r,r*tilt,0,0,tau);c.stroke();
  });c.restore();
  const bodies=orbitalRadii.map((r,i)=>({...position(r,phases[i]+t*1.06*(90/r)**1.5),i}))
    .sort((a,b)=>a.depth-b.depth);
  const paint=(body: typeof bodies[number])=>{
    const d=diameters[body.i]*(1+.09*body.depth);
    s.sprite('/models/solar-turntable/'+names[body.i]+'/00.webp',body.x,body.y,d);
  };
  bodies.filter(b=>b.depth<0).forEach(paint);sun(c,cx,cy,80);bodies.filter(b=>b.depth>=0).forEach(paint);
  s.label('Sistema Solar em formação',24,326,{size:20});
  return true;
}

export function paint(s: StagePaint, id: string, value: number, phase: number): boolean {
  if (id !== 'sistema-solar-disco') return false;
  s.backdrop();
  const t=clamp(phase);
  switch (Math.round(value)) {
    case 0: return drawCloud(s,t);
    case 1: return flattened(s,t);
    case 2: return grains(s,t);
    default: return planets(s,t);
  }
}

