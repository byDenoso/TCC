import { animator, clear, fmt, initGuess, q, qa, reduced, svg } from './common';
import { expandedPosition, expansionPositions, separation } from '../../lib/expansion';
import type { MountedScene } from '../visual/runtime';

const SCALE_MAX = 2.5;
export function initExpansao(root: HTMLElement): void {
  const stage=q<SVGSVGElement>(root,'[data-e-svg]'), plot=q<SVGSVGElement>(root,'[data-e-plot]');
  const range=q<HTMLInputElement>(root,'[data-e-range]'), out=q(root,'[data-e-scale]');
  const play=q<HTMLButtonElement>(root,'[data-e-play]'), arrows=q<HTMLInputElement>(root,'[data-e-arrows]');
  const reading=q(root,'[data-e-reading]'), live=q(root,'[data-e-live]'), volume=q<HTMLElement>(root,'[data-e-volume]');
  const buttons=qa<HTMLButtonElement>(root,'[data-e-observer]');
  let scaleValue=Number(range.value);
  let observer=0, moved=false, visual: MountedScene|null=null;
  clear(stage); clear(plot);
  const galaxyNodes=expansionPositions.map((_,i)=>{
    const g=svg('g',{'aria-hidden':'true',class:'e-galaxy'},stage);
    svg('ellipse',{rx:11,ry:5,fill:i%3===1?'#dbc5a2':'#a6c5ec',opacity:0.8},g);
    svg('ellipse',{rx:5,ry:2.5,fill:'#f5d8ac'},g);
    if(i<3)svg('text',{x:0,y:22,class:'obs-cap','text-anchor':'middle'},g,'ABC'[i]); return g;
  });
  const lines=expansionPositions.map(()=>svg('line',{stroke:'#748aa8','stroke-width':1,opacity:0.5},stage));
  svg('circle',{cx:320,cy:200,r:19,fill:'none',stroke:'#ffaf78','stroke-width':2},stage);
  const maxD=8, px=(d:number)=>48+d/maxD*492, py=(d:number)=>190-d/((SCALE_MAX-1)*maxD)*170;
  svg('line',{x1:48,y1:190,x2:540,y2:190,class:'obs-axis'},plot);
  svg('line',{x1:48,y1:20,x2:48,y2:190,class:'obs-axis'},plot);
  svg('text',{x:294,y:224,'text-anchor':'middle',class:'obs-cap small'},plot,'distância antes (passos)');
  svg('text',{x:16,y:110,transform:'rotate(-90 16 110)','text-anchor':'middle',class:'obs-cap small'},plot,'afastamento (passos)');
  const fit=svg('line',{class:'e-fit'},plot);
  const dots=expansionPositions.map(()=>svg('circle',{r:3,class:'e-dot'},plot));
  const render=()=>{
    const scale=scaleValue; out.textContent=`${fmt(scale,2)} ×`;
    expansionPositions.forEach((_,i)=>{
      const p=expandedPosition(i,observer,scale), before=expandedPosition(i,observer,1);
      // Projeção oblíqua 2D do mesmo catálogo comóvel; z contribui à profundidade.
      const project=(a:number[])=>[320+(a[0]+a[2]*0.2)*40,200+(a[1]-a[2]*0.42)*40];
      const [x,y]=project(p), [bx,by]=project(before);
      galaxyNodes[i].setAttribute('transform',`translate(${x.toFixed(2)} ${y.toFixed(2)})`);
      galaxyNodes[i].classList.toggle('is-observer',i===observer);
      lines[i].setAttribute('x1',String(bx)); lines[i].setAttribute('y1',String(by)); lines[i].setAttribute('x2',String(x)); lines[i].setAttribute('y2',String(y));
      lines[i].style.display=arrows.checked&&i!==observer&&scale>1.01?'':'none';
      const d=separation(i,observer); dots[i].setAttribute('cx',String(px(d))); dots[i].setAttribute('cy',String(py(d*(scale-1)))); dots[i].style.display=i===observer?'none':'';
    });
    fit.setAttribute('x1',String(px(0))); fit.setAttribute('x2',String(px(maxD))); fit.setAttribute('y1',String(py(0))); fit.setAttribute('y2',String(py(maxD*(scale-1))));
    visual?.state({value:scale});
    buttons.forEach((b,i)=>b.setAttribute('aria-pressed',String(i===observer)));
    const distances=expansionPositions.map((_,i)=>separation(i,observer)).filter(d=>d>0).sort((a,b)=>a-b);
    const near=distances[0],far=distances.at(-1)!;
    reading.replaceChildren();
    const line=(t:string)=>{const p=document.createElement('p'); p.textContent=t; reading.append(p);};
    line(`Da galáxia ${'ABC'[observer]}, a vizinha estava a ${fmt(near,1)} passos. Agora está a ${fmt(near*scale,1)}.`);
    line(`A mais distante estava a ${fmt(far,1)} passos. Agora está a ${fmt(far*scale,1)}: ganhou ${fmt(far*(scale-1),1)} passos.`);
    line('As distâncias crescem na mesma proporção. Mude de observador: ninguém ocupa um centro privilegiado.');
    live.textContent=`Observador ${'ABC'[observer]}. Distâncias cresceram ${fmt(scale,2)} vezes. A vizinha está a ${fmt(near*scale,1)} passos; a mais distante, ${fmt(far*scale,1)}.`;
    if(moved&&scale>=1.5) root.dispatchEvent(new CustomEvent('cosmos:badge',{bubbles:true,detail:{id:'sem-centro'}}));
  };
  buttons.forEach((b,i)=>b.addEventListener('click',()=>{moved ||= i!==observer; observer=i; render();}));
  const syncPlay=()=>{play.setAttribute('aria-pressed',String(anim.running())); play.textContent=anim.running()?'Pausar':Number(range.value)>=SCALE_MAX?'Recomeçar':'Deixar o espaço crescer';};
  const anim=animator(root,dt=>{scaleValue=Math.min(SCALE_MAX,scaleValue+dt*0.00022);range.value=String(scaleValue); render(); const more=scaleValue<SCALE_MAX; if(!more)queueMicrotask(syncPlay); return more;});
  root.addEventListener('cosmos:autopause',syncPlay);
  window.addEventListener('pagehide',event=>{if(!event.persisted)anim.dispose();});
  play.addEventListener('click',()=>{
    if(anim.running()){anim.stop();syncPlay();return;}
    if(reduced()){scaleValue=scaleValue>=SCALE_MAX?1:Math.min(SCALE_MAX,scaleValue+0.25);range.value=String(scaleValue);render();syncPlay();return;}
    if(scaleValue>=SCALE_MAX){scaleValue=1;range.value='1';}anim.start();syncPlay();
  });
  range.addEventListener('input',()=>{anim.stop();scaleValue=Number(range.value);render();syncPlay();}); arrows.addEventListener('change',render);
  qa<HTMLButtonElement>(root,'[data-e-reset]').forEach(b=>b.addEventListener('click',()=>{anim.stop();scaleValue=1;range.value='1';observer=0;render();syncPlay();}));
  import('../visual/runtime').then(async({observeScene,whenNear})=>{
    if(!await whenNear(volume))return;
    const {prepareEmissionGalaxies,emissionSize,emissionReady}=await import('../visual/galaxy-emission');const size=emissionSize(volume.clientWidth,volume.dataset.cosmosQuality==='low'?'low':'auto');await prepareEmissionGalaxies(size);
    const {expansion}=await import('../visual/expansion-pilot'); visual=observeScene(volume,()=>expansion(()=>observer,()=>arrows.checked,volume.dataset.cosmosQuality==='low'&&emissionReady(512)?512:size));visual.state({value:scaleValue});
  }).catch(()=>{volume.dataset.visualFallback='true';});
  initGuess(root);render();syncPlay();
}
