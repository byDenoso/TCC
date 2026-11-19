import type { StagePaint } from '../stage-surface';
import { planets } from '../../data/client';
import { atmosphereLayer, atmosphereProfile, atmosphereTemperatureC } from '../../lib/teaching-numerics';
import { cometPosition, ORBIT_DRAWN_CENTRAL_RADIUS, trajectory, trajectoryAt } from './sistema';

type Ctx = CanvasRenderingContext2D;
type Pt = [number, number];
type Plate = (stage: StagePaint, value: number, phase: number) => void;
const TAU = 2 * Math.PI;
const gold = '#ffcd79', blue = '#81d7ff', coral = '#ff9879', pale = '#dae8ee';
const clamp = (v: number, max = 1) => Math.max(0, Math.min(max, v));
const select = (v: number, last: number) => Math.round(clamp(v, last));
const number = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 });
const fmt = (n: number) => number.format(n);
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const unit = (x: number) => x - Math.floor(x);
const earth = planets.find(p => p.id === 'terra')!;
const rockyIds = ['mercurio', 'venus', 'terra', 'marte'];
const rocky = rockyIds.map(id => planets.find(p => p.id === id)!);

function line(c: Ctx, a: Pt, b: Pt, color: string, width = 1) {
  c.beginPath(); c.moveTo(...a); c.lineTo(...b); c.strokeStyle = color; c.lineWidth = width; c.stroke();
}
function ellipse(c: Ctx, x: number, y: number, rx: number, ry: number, fill: string | CanvasGradient) {
  c.beginPath(); c.ellipse(x, y, rx, ry, 0, 0, TAU); c.fillStyle = fill; c.fill();
}
function arrow(c: Ctx, a: Pt, b: Pt, color: string) {
  const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy);
  if (len < 1) return;
  const head = Math.min(7, len / 2), nx = dx / len, ny = dy / len;
  line(c, a, b, color, 2);
  for (const sign of [-1, 1]) line(c, b, [b[0]-head*(nx+sign*ny*.45), b[1]-head*(ny-sign*nx*.45)], color, 2);
}
function orb(c: Ctx, x: number, y: number, r: number, hi: string, lo: string) {
  const g = c.createRadialGradient(x-r*.35, y-r*.42, 0, x, y, r);
  g.addColorStop(0, hi); g.addColorStop(1, lo); ellipse(c, x, y, r, r, g);
}
function world(s: StagePaint, id: string, x: number, y: number, r: number, phase = 0) {
  const step = Math.floor(clamp(phase) * 10);
  const url = (n: number) => '/models/solar-turntable/'+id+'/'+String(n).padStart(2,'0')+'.webp';
  const current = url(step);
  // The Cycles camera spans 2.4 globe radii across the square crop.
  if (s.image(current)) s.sprite(current, x, y, r*2.4);
  else if (step && s.image(url(0))) s.sprite(url(0), x, y, r*2.4);
  else orb(s.ctx, x, y, r, '#9faeb1', '#1b2630');
}
function sun(s: StagePaint, x: number, y: number, r: number) {
  const c = s.ctx, glow = c.createRadialGradient(x,y,r*.75,x,y,r*2.9);
  glow.addColorStop(0,'#ffc360aa'); glow.addColorStop(1,'#ff9d2600');
  ellipse(c,x,y,2.9*r,2.9*r,glow); orb(c,x,y,r,'#fff6bc','#f8a835');
  const texture = s.image('/models/stellar/granulation.png');
  if (texture) {
    c.save(); c.beginPath(); c.arc(x,y,r,0,TAU); c.clip(); c.globalCompositeOperation='multiply';
    c.globalAlpha=.55; c.drawImage(texture,x-r,y-r,2*r,2*r); c.restore();
  }
}
function gauge(s: StagePaint, x: number, y: number, w: number, fraction: number, title: string, value: string, color: string) {
  s.label(title,x,y,{size:13}); s.label(value,x+w,y,{size:14,color,align:'right'});
  const c=s.ctx; c.fillStyle='#364659'; c.fillRect(x,y+10,w,4);
  c.fillStyle=color; c.fillRect(x,y+10,w*clamp(fraction),4);
  for (let i=0;i<=4;i++) line(c,[x+w*i/4,y+16],[x+w*i/4,y+20],'#728599');
}

const rockyWorld: Plate = (s,v,t) => {
  const i=select(v,3), p=rocky[i], flux=[6.7,1.9,1,.43][i];
  const c=s.ctx, x=201, y=166, radius=77;
  const air=[0,1,.35,.08][i];
  const halo=c.createRadialGradient(x,y,radius-2,x,y,radius+3+air*18);
  halo.addColorStop(0,'#ffd995af'); halo.addColorStop(1,'#ffa74a00');
  ellipse(c,x,y,radius+3+air*18,radius+3+air*18,halo);
  sun(s,12,118,25);
  for(let j=0;j<Math.ceil(flux*2);j++){
    const f=unit(t*.97+j*.618), yy=123+j*6;
    line(c,[38+78*f,yy],[44+78*f,yy+2],gold,2);
  }
  world(s,p.id,x,y,radius,t); s.label(p.name,x,282,{align:'center',size:22});
  gauge(s,322,83,286,flux/7,'Fluxo solar · Terra = 1',fmt(flux),gold);
  gauge(s,322,157,286,air,'Pressão · comparativa',['exosfera','92 bar','1 bar','0,006 bar'][i],blue);
  gauge(s,322,231,286,(p.temperature+100)/600,'Temperatura média',fmt(p.temperature)+' °C',coral);
  s.label('−100 °C',322,278,{size:12}); s.label('500 °C',608,278,{size:12,align:'right'});
};

const giant: Plate = (s,v,t) => {
  const depth=clamp(v), c=s.ctx, x=183, y=180, r=127;
  world(s,'jupiter',x,y,r,t);
  c.save(); c.beginPath(); c.moveTo(x,y); c.arc(x,y,r,-Math.PI/2,0); c.closePath(); c.clip();
  const g=c.createRadialGradient(x,y,0,x,y,r);
  for (const [f,color] of [[0,'#ffedaf'],[.07,'#c68664'],[.25,'#906269'],[.55,'#b88062'],[.88,'#deb582'],[1,'#eee3cc']] as const) g.addColorStop(f,color);
  ellipse(c,x,y,r,r,g); c.restore();
  const point=(d:number):Pt=>[x+(1-d)*r*Math.SQRT1_2,y-(1-d)*r*Math.SQRT1_2];
  line(c,point(0),point(1),'#fff4cd90'); ellipse(c,...point(.13),3,3,blue);
  ellipse(c,...point(depth),5,5,'#fff'); line(c,point(depth),[339,166],pale);
  const bands=['Nuvens','Hidrogênio gasoso','Hidrogênio líquido','Hidrogênio metálico','Possível núcleo difuso'];
  const idx=depth<.12?0:depth<.45?1:depth<.75?2:depth<.93?3:4;
  s.label('Júpiter · corte radial',345,99,{size:18});
  s.label(bands[idx],345,153,{size:18,color:gold});
  s.label(fmt(Math.round(100*depth))+'% até o centro',345,188,{size:16});
  s.label('● 1 bar · referência nas nuvens',345,230,{size:14,color:blue});
  s.label('Profundidades esquemáticas',345,253,{size:13});
};

const comet: Plate = (s,v) => {
  const c=s.ctx,f=clamp(v),[x,y,vx,vy]=cometPosition(f), sx=108, sy=135;
  const proj=(x:number,y:number):Pt=>[188+(x-108)*1.18,167+(y-135)*.75];
  c.beginPath();
  for(let i=0;i<=160;i++){const [a,b]=cometPosition(i/160); const q=proj(a,b); if(i)c.lineTo(...q);else c.moveTo(...q);}
  c.strokeStyle='#99b1ce88';c.lineWidth=1.3;c.stroke();
  sun(s,...proj(sx,sy),15);
  const d=Math.hypot(x-sx,y-sy), ux=(x-sx)/d,uy=(y-sy)/d;
  const speed=Math.hypot(vx,vy), L=Math.min(114,9e5/d**2);
  const [px,py]=proj(x,y);
  if(L>4){
    for(let i=0;i<60;i++){
      const k=unit(i*.618+f*5), dust=i%2===0, spread=Math.sin(i*27)*k*(dust?6:2);
      const bend=dust?.36*k*k*L:0;
      const q=proj(x+ux*k*L-vx/speed*bend-uy*spread,y+uy*k*L-vy/speed*bend+ux*spread);
      c.globalAlpha=1-k*.9; ellipse(c,...q,dust?2:1.5,dust?1.5:1, dust?gold:blue);
    }
    c.globalAlpha=1;
  }
  // A cropped lunar texture illustrates an irregular rocky nucleus.
  c.save(); c.translate(px,py); c.rotate(.5+f*TAU); c.scale(1.3,.72);
  world(s,'lua',0,0,7); c.restore();
  s.label('Gás ionizado',26,307,{color:blue}); s.label('Poeira',163,307,{color:gold});
  s.label('Fase orbital '+fmt(Math.round(f*100))+'%',604,307,{align:'right'});
};

let lastSpeed = -1;
let lastPath: ReturnType<typeof trajectory>;
const orbit: Plate = (s,v,t) => {
  const speed=clamp(v,1.6);
  if(lastSpeed!==speed){lastPath=trajectory(speed);lastSpeed=speed;}
  const c=s.ctx, path=lastPath, sample=trajectoryAt(path,t);
  const scale=72, cx=312,cy=164;
  const project=([x,y]:Pt):Pt=>[cx+x*scale,cy-y*scale*.62];
  function trail(end:number,color:string,tip?:Pt){
    c.beginPath();c.moveTo(...project(path.pts[0]));
    for(let i=1;i<=end;i++)c.lineTo(...project(path.pts[i]));
    if(tip)c.lineTo(...project(tip));
    c.strokeStyle=color;c.lineWidth=2;c.stroke();
  }
  trail(path.pts.length-1,'#8594a677');trail(sample.index,gold,sample.position);
  const pos=project(sample.position);
  const drawBody=()=>world(s,'marte',...pos,7,t);
  if(sample.position[1]>0)drawBody();
  sun(s,cx,cy,scale*ORBIT_DRAWN_CENTRAL_RADIUS);
  if(sample.position[1]<=0)drawBody();
  const prev=project(path.pts[sample.index]),next=project(path.pts[sample.index+1]);
  const dx=next[0]-prev[0],dy=next[1]-prev[1],n=Math.hypot(dx,dy);
  if(n && (t>0 || speed>0))arrow(c,pos,[pos[0]+31*dx/n,pos[1]+31*dy/n],blue);
  const d=Math.hypot(cx-pos[0],cy-pos[1])||1;
  arrow(c,pos,[pos[0]+(cx-pos[0])*24/d,pos[1]+(cy-pos[1])*24/d],coral);
  s.label('Velocidade',22,34,{color:blue});s.label('Gravidade',138,34,{color:coral});
  s.label('Lançamento · '+fmt(speed)+' × v circular',24,308,{size:15});
  s.label(({cai:'Cruza o limite central',orbita:'Órbita fechada',escapa:'Escape',longe:'Órbita além do quadro'})[path.kind],615,308,{align:'right',size:15});
};

const comparisonWorlds=['terra','jupiter','saturno'].map(id=>planets.find(p=>p.id===id)!);
const measure: Plate = (s,v,t) => {
  const k=select(v,3), titles=['Raio equatorial','Massa','Densidade média','Gravidade equatorial'];
  const units=['km','M⊕','g/cm³','m/s²'], max=[75000,330,6,26][k];
  s.label(titles[k]+' · escala linear',24,32,{size:19});
  comparisonWorlds.forEach((p,i)=>{
    const y=85+i*88, val=[p.radius,p.mass/earth.mass,[5.51,1.33,.69][i],p.gravity][k];
    world(s,p.id==='saturno'?'saturno-globo':p.id,71,y,30,t);
    gauge(s,131,y-7,457,val/max,p.name,fmt(val)+' '+units[k],[blue,coral,gold][i]);
  });
  s.label('0',131,325,{size:12});s.label(fmt(max)+' '+units[k],588,325,{size:12,align:'right'});
};


const formation: Plate = (s,v,t) => {
  const stage=select(v,3),c=s.ctx,x=184,y=172,r=127;
  world(s,stage===3?'terra':'lua',x,y,r,t);
  c.save();c.beginPath();c.arc(x,y,r,0,TAU);c.clip();
  if(stage<3){c.fillStyle='#b34c1ab5';c.fillRect(x-r,y-r,2*r,2*r);}
  if(stage<2){
    for(let i=0;i<105;i++){
      const metal=i%3===0, a=i*2.39996+.19*t, initial=Math.sqrt(unit(.17+i*.618));
      const end=metal ? initial*.31 : .39+initial*.58;
      const rr=(stage===1?mix(initial,end,t):initial)*r*.94;
      const depth=Math.cos(i*1.83+a), rad=(metal?3.8:2.4)*(1+.31*depth);
      orb(c,x+rr*Math.cos(a),y+rr*Math.sin(a),rad,metal?'#d09474':'#ffe7a8',metal?'#502c2c':'#b86e30');
    }
  }else{
    c.beginPath();c.rect(x,y-r,r,2*r);c.clip();
    for(const [rad,hi,lo] of [[r,'#cc9f73','#714532'],[r*.963,'#eb9a57','#965334'],[r*.51,'#ffe19b','#d58431']] as const) orb(c,x,y,rad,hi,lo);
    if(stage===3)orb(c,x,y,r*.21,'#fff4c1','#e9b368');
  }
  c.restore();
  if(stage<2){
    s.label(stage?'Diferenciação':'Mistura quente',343,109,{size:22});
    s.label('Ferro e níquel',343,158,{color:'#eba591'});s.label('Silicatos',343,191,{color:gold});
    if(stage)arrow(c,[x+82,y-62],[x+34,y-26],pale);
  }else{
    const names=stage===2?['Crosta','Manto','Núcleo']:['Crosta','Manto quase todo sólido','Núcleo externo líquido','Núcleo interno sólido'];
    names.forEach((name,i)=>{
      const rad=[.98,.73,.38,.1][i], yy=78+i*57;
      line(c,[x+r*rad*.88,y-r*rad*.47],[342,yy-3],'#e3d5b995');
      s.label(name,353,yy,{size:16,color:i>1?gold:pale});
    });
  }
  s.label('Corte esquemático · materiais fora de escala',24,333,{size:13});
};

const oxygenLevel=(ga:number)=>ga>2.4?.01:ga>.6?mix(.12,.2,(2.4-ga)/1.8):mix(.25,1,(.6-ga)/.6);
const ancientAir: Plate = (s,v) => {
  const f=clamp(v),ga=4.5*(1-f),c=s.ctx,air=oxygenLevel(ga);
  const sink=clamp((3-ga)/.6);
  // Clip a textured limb below the sampling column. Early geography is illustrative.
  c.save();c.beginPath();c.rect(0,28,279,262);c.clip();
  world(s,ga<.05?'terra':'lua',139,351,202,f);
  const ocean=c.createLinearGradient(0,143,0,280);
  ocean.addColorStop(0,'#23769b00');ocean.addColorStop(.45,'#246882b0');ocean.addColorStop(1,'#804f32e8');
  c.fillStyle=ocean;c.fillRect(0,150,279,140);
  for(let i=0;i<42;i++){
    const px=22+unit(Math.sin((i+1)*73.2)*4719)*238, wave=unit(i*.381+f*5);
    if(i<Math.round(air*30))ellipse(c,px,143-wave*94,2.7,2,blue);
    if(i<Math.round(sink*34))ellipse(c,px,201+wave*59,3,2,coral);
  }
  c.restore();
  s.label('O₂ no ar',22,55,{color:blue});s.label('Oxidação nas rochas e oceanos',18,286,{size:13,color:gold});
  const X=(time:number)=>310+(4.5-time)/4.5*294, Y=(level:number)=>249-level*140;
  line(c,[310,249],[604,249],pale);
  for(const mark of [4.5,2.4,.6,0]){
    line(c,[X(mark),249],[X(mark),255],pale);s.label(fmt(mark),X(mark),273,{size:12,align:'center'});
  }
  c.beginPath();
  const steps=Math.max(1,Math.ceil(f*220));
  for(let i=0;i<=steps;i++){const time=4.5*(1-f*i/steps);if(i)c.lineTo(X(time),Y(oxygenLevel(time)));else c.moveTo(X(time),Y(oxygenLevel(time)));}
  c.strokeStyle=blue;c.lineWidth=2.4;c.stroke();ellipse(c,X(ga),Y(air),4,4,gold);
  s.label('O₂ atmosférico · qualitativo',309,69,{size:16,color:blue});
  s.label('Bilhões de anos atrás',310,299,{size:13});
  s.label(ga<.05?'Hoje · cerca de 21% de O₂':'Há '+fmt(ga)+' bilhões de anos',24,332,{size:17});
};

function limb(s: StagePaint, phase:number){
  world(s,'terra',322,643,412,phase);
}
const presentAir: Plate = (s,v,t) => {
  const c=s.ctx;
  if(select(v,1)===0){
    world(s,'terra',124,167,83,t);
    s.label('Ar seco',124,283,{align:'center',size:18});
    for(let i=0;i<100;i++){
      const x=266+(i%10)*16,y=71+Math.floor(i/10)*19;
      const color=i<78?blue:i<99?coral:'#e7dfb5';
      c.globalAlpha=i<Math.round(100*t)?1:.28;
      orb(c,x,y,4.8,color,'#293647');
      if(i<99)orb(c,x+4.7,y-2,4,color,'#263345');
    }
    c.globalAlpha=1;
    ['78 N₂','21 O₂','≈ 1 Ar'].forEach((n,i)=>s.label(n,458,115+i*40,{color:[blue,coral,gold][i],size:18}));
    s.label('CO₂ ≈ 4 partes em 10.000',265,293,{size:16});
  }else{
    limb(s,t);
    sun(s,49,63,16);arrow(c,[73,85],[159,247],gold);
    s.label('Luz solar',19,31,{color:gold});
    const rays=[204,293,385,477,550];
    rays.forEach((x,i)=>{
      const surface=643-Math.sqrt(412**2-(x-322)**2),absorbed=i%2===0;
      const top=absorbed?123+i*6:46;
      const q=clamp(t/.62),head=mix(surface,top,q);
      c.setLineDash([4,5]);line(c,[x,surface],[x,head],coral,2);c.setLineDash([]);
      ellipse(c,x,head,3,3,coral);
      if(absorbed){
        for(const offset of [-6,0,6])orb(c,x+offset,top,4,offset?'#ffb493':'#92949a','#422d33');
        if(t>.62){
          const a=(t-.62)/.38;
          arrow(c,[x,top],[x-34*a,top+54*a],coral);arrow(c,[x,top],[x+39*a,top-48*a],coral);
        }
      }
    });
    s.label('Infravermelho da superfície',195,320,{color:'#fff3eb',size:17});
    s.label('Absorção e reemissão',365,31,{color:coral,size:14});
  }
};

const altitude: Plate = (s,v) => {
  const c=s.ctx,h=clamp(v,120),tc=atmosphereTemperatureC(h);
  const Y=(z:number)=>292-z*1.95, X=(temp:number)=>453+temp*1.28;
  c.save();c.beginPath();c.rect(0,43,284,264);c.clip();
  world(s,'terra',151,688,405,h/120);
  const air=c.createLinearGradient(0,60,0,288);air.addColorStop(0,'#20355400');air.addColorStop(1,'#619fc16b');
  c.fillStyle=air;c.fillRect(0,44,284,248);
  c.restore();
  for(const [z,feature] of [[4,'Nuvens'],[25,'Ozônio'],[80,'Meteoros'],[110,'Auroras']] as const)
    s.label(feature,37,Y(z)-3,{size:13,color:'#d1e3ee'});
  for(const z of [0,12,50,85,120]){
    line(c,[225,Y(z)],[598,Y(z)],'#8caaaf4d');
    s.label(z+' km',278,Y(z)-4,{size:11,align:'right'});
  }
  line(c,[X(0),Y(0)],[X(0),Y(120)],'#8092a9');
  c.beginPath();atmosphereProfile.forEach(([z,temp],i)=>{if(i)c.lineTo(X(temp),Y(z));else c.moveTo(X(temp),Y(z));});
  c.strokeStyle=coral;c.lineWidth=2.5;c.stroke();
  line(c,[15,Y(h)],[X(tc),Y(h)],blue);ellipse(c,X(tc),Y(h),5,5,gold);
  [-100,0,100].forEach(n=>s.label(fmt(n)+' °C',X(n),316,{size:12,align:'center'}));
  s.label(fmt(h)+' km · '+atmosphereLayer(h),19,30,{size:18,color:blue});
  s.label(fmt(Math.round(tc))+' °C',605,30,{size:18,color:coral,align:'right'});
};

const magnetism: Plate = (s,v,t) => {
  const c=s.ctx,field=select(v,1)===0,x=423,y=175,r=59;
  sun(s,36,y,18);
  if(field){
    for(const sign of [-1,1])for(let i=1;i<=3;i++){
      c.beginPath();c.moveTo(x,y-r*.86);
      const extent=sign<0?42+29*i:61+53*i;
      c.bezierCurveTo(x+sign*extent,y-97-i*11,x+sign*extent,y+97+i*11,x,y+r*.86);
      c.strokeStyle='#83cdef69';c.lineWidth=1.5;c.stroke();
    }
  }
  const atmosphere=c.createRadialGradient(x,y,r-1,x,y,r+9);
  atmosphere.addColorStop(0,'#79d0ffb0');atmosphere.addColorStop(1,'#81d6ff00');
  ellipse(c,x,y,r+9,r+9,atmosphere);world(s,'terra',x,y,r,t);
  for(let i=0;i<50;i++){
    const u=unit(t+i*.618), lane=(unit(Math.sin((i+1)*31.7)*4563)-.5)*165;
    const side=lane>=0?1:-1;
    const polar=field && i%6===0;
    const end=polar?x:field?605:x-Math.sqrt(Math.max(0,(r+9)**2-lane**2));
    if(!field && Math.abs(lane)>r+9)continue;
    const xx=mix(72,end,u), influence=Math.exp(-(((xx-x)/106)**2));
    const yy=y+(field?mix(lane,side*(polar?r*.94:r+42+Math.abs(lane)*.6),influence):lane);
    const size=1.4+unit(i*.73)*1.7;
    line(c,[xx-5,yy],[xx,yy],gold,size);
  }
  if(field)for(const sign of [-1,1]){
    c.beginPath();c.ellipse(x,y+sign*r*.89,18,4,0,0,TAU);
    c.strokeStyle='#77f7a7';c.globalAlpha=.48+.4*Math.sin(Math.PI*t);c.lineWidth=3;c.stroke();
  }
  c.globalAlpha=1;
  s.label('Vento solar →',22,42,{color:gold});
  s.label(field?'Com campo interno':'Sem campo interno',612,42,{align:'right',size:18});
  s.label(field?'Partículas desviadas · precipitação nos polos':'Partículas alcançam a alta atmosfera',25,325,{size:16});
};

const habitability: Plate = (s,v,t) => {
  const i=select(v,3), p=rocky[[1,2,3,2][i]], hypothetical=i===3;
  const temp=hypothetical?-18:p.temperature, bars=[92,1,.006,1][i],c=s.ctx;
  world(s,p.id,152,170,90,t);
  if(hypothetical){c.save();c.globalCompositeOperation='source-atop';ellipse(c,152,170,90,90,'#cbe7f766');c.restore();}
  s.label(hypothetical?'Terra sem efeito estufa':p.name,152,289,{align:'center',size:18});
  gauge(s,297,78,302,(Math.log10(bars)+2.5)/5,'Pressão · escala log',fmt(bars)+' bar',blue);
  gauge(s,297,154,302,(temp+100)/600,'Temperatura média',fmt(temp)+' °C',coral);
  const water=['Sem água líquida estável','Água líquida possível','Gelo ou vapor','Gelo em boa parte'][i];
  s.label(water,297,240,{size:19,color:blue});
  // Particle spacing illustrates the water state in each selected scenario.
  for(let j=0;j<24;j++){
    const col=j%8,row=Math.floor(j/8), vapor=i===0 || (i===2 && j%3===0);
    const x=310+col*25+(vapor?12*Math.sin(TAU*t+j):0);
    const y=291+row*9+(vapor?-30*unit(t+j*.618):i===1?4*Math.sin(5*t+col):0);
    orb(c,x,y,3.4,vapor?'#c6e5e9':blue,'#285575');
  }
};

const plates: Record<string, Plate> = {
  'sistema-solar-sol-e-planetas': rockyWorld,
  'sistema-solar-gigantes': giant,
  'sistema-solar-pequenos-corpos': comet,
  'sistema-solar-orbitas': orbit,
  'sistema-solar-medindo-mundos': measure,
  'terra-e-atmosfera-formacao-da-terra': formation,
  'terra-e-atmosfera-atmosfera-primitiva': ancientAir,
  'terra-e-atmosfera-ar-atual': presentAir,
  'terra-e-atmosfera-camadas': altitude,
  'terra-e-atmosfera-campo-magnetico': magnetism,
  'terra-e-atmosfera-habitabilidade': habitability
};

/** A pure frame renderer; the shared transport owns time, visibility and motion preferences. */
export function paint(canvas: StagePaint, id: string, value: number, phase: number): boolean {
  if (!Object.hasOwn(plates,id)) return false;
  const c=canvas.ctx;
  c.save();
  try {
    canvas.backdrop();
    plates[id](canvas,Number.isFinite(value)?value:0,Number.isFinite(phase)?clamp(phase):1);
    return true;
  } finally {
    c.restore();
  }
}

