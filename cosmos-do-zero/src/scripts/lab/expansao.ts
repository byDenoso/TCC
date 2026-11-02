import { animator, clear, fmt, initGuess, q, qa, reduced, svg } from './common';
import { expansionPositions, separation, projectExpansion } from '../../lib/expansion';
import type { MountedScene } from '../visual/runtime';
import { motionPreference } from '../motion-preference';
import { visibleMotion } from '../visible-motion';

const SCALE_MAX=2.5;
const colors=['#b4a0ff','#ffbd87','#8ee1d4'];
export function initExpansao(root:HTMLElement):void {
 const stage=q<SVGSVGElement>(root,'[data-e-svg]'),plot=q<SVGSVGElement>(root,'[data-e-plot]');
 const range=q<HTMLInputElement>(root,'[data-e-range]'),out=q(root,'[data-e-scale]');
 const play=q<HTMLButtonElement>(root,'[data-e-play]'),arrows=q<HTMLInputElement>(root,'[data-e-arrows]');
 const before=q<HTMLInputElement>(root,'[data-e-before]'),stops=q<HTMLInputElement>(root,'[data-e-stops]'),speed=q<HTMLSelectElement>(root,'[data-e-speed]');
 const reading=q(root,'[data-e-reading]'),live=q(root,'[data-e-live]'),volume=q<HTMLElement>(root,'[data-e-volume]');
 const buttons=qa<HTMLButtonElement>(root,'[data-e-observer]'),targets=qa<HTMLButtonElement>(root,'[data-e-target]');
 let scaleValue=Number(range.value),observer=0,target=1,moved=false,visual:MountedScene|null=null,transition=0;
 clear(stage);clear(plot);
 const defs=svg('defs',{},stage);const glow=svg('radialGradient',{id:root.id+'-galaxy'},defs);svg('stop',{offset:0,'stop-color':'#fff6dc'},glow);svg('stop',{offset:.35,'stop-color':'#c6beff','stop-opacity':.8},glow);svg('stop',{offset:1,'stop-color':'#9bb8ff','stop-opacity':0},glow);
 for(let i=0;i<45;i++)svg('circle',{cx:(i*137.5)%640,cy:(i*83.7)%400,r:i%4===0?1:.6,fill:'#bdcbea',opacity:.15+(i%3)*.07},stage);
 const ghosts=expansionPositions.map(()=>svg('ellipse',{rx:12,ry:7,class:'e-before'},stage));
 const lines=expansionPositions.map(()=>svg('line',{stroke:'#9eb9e8','stroke-width':1,opacity:.5},stage));
 const ruler=svg('line',{class:'e-ruler'},stage),measure=svg('text',{class:'e-measure','text-anchor':'middle'},stage);
 const galaxyNodes=expansionPositions.map((_,i)=>{
  const g=svg('g',{'aria-hidden':'true',class:'e-galaxy'},stage);
  svg('ellipse',{rx:i<3?23:14,ry:i<3?12:7,fill:`url(#${root.id}-galaxy)`},g);
  svg('ellipse',{rx:i<3?13:8,ry:i<3?6:4,fill:colors[i%3],opacity:.85},g);
  svg('ellipse',{rx:5,ry:2.5,fill:'#fff0cf'},g);
  if(i<3)svg('text',{x:0,y:22,class:'obs-cap','text-anchor':'middle'},g,'ABC'[i]);return g;
 });
 const ring=svg('circle',{r:20,fill:'none',stroke:colors[0],'stroke-width':1.5},stage);
 const maxD=Math.ceil(Math.max(...expansionPositions.flatMap((_,i)=>[0,1,2].map(o=>separation(i,o)))));
 const px=(d:number)=>48+d/maxD*492,py=(d:number)=>190-d/((SCALE_MAX-1)*maxD)*170;
 svg('line',{x1:48,y1:190,x2:540,y2:190,class:'obs-axis'},plot);svg('line',{x1:48,y1:20,x2:48,y2:190,class:'obs-axis'},plot);
 svg('text',{x:294,y:224,'text-anchor':'middle',class:'obs-cap small'},plot,'distância antes (passos)');
 svg('text',{x:16,y:110,transform:'rotate(-90 16 110)','text-anchor':'middle',class:'obs-cap small'},plot,'afastamento (passos)');
 const fit=svg('line',{class:'e-fit'},plot);
 const dots=expansionPositions.map((_,i)=>{
  const group=svg('g',{role:'button',tabindex:0,'aria-label':`Comparar galáxia ${i<3?'ABC'[i]:i+1}`},plot);
  svg('circle',{r:14,fill:'transparent'},group);
  const dot=svg('circle',{r:4,class:'e-dot'},group);
  const select=()=>{if(i!==observer){target=i;render();}};
  group.addEventListener('click',select);group.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select();}});return {group,dot};
 });
 const set=(node:Element,attrs:Record<string,string|number>)=>Object.entries(attrs).forEach(([k,v])=>node.setAttribute(k,String(v)));
 const render=()=>{
  const scale=scaleValue;out.textContent=`${fmt(scale,2)} ×`;
  const [ox,oy]=projectExpansion(observer,observer,scale);set(ring,{cx:ox,cy:oy,stroke:colors[observer]});
  expansionPositions.forEach((_,i)=>{
   const [x,y]=projectExpansion(i,observer,scale),[bx,by]=projectExpansion(i,observer,1);
   set(galaxyNodes[i],{transform:`translate(${x.toFixed(2)} ${y.toFixed(2)})`,'data-selected':String(i===target)});
   galaxyNodes[i].classList.toggle('is-observer',i===observer);
   set(ghosts[i],{cx:bx,cy:by});ghosts[i].style.display=before.checked&&i!==observer?'':'none';
   set(lines[i],{x1:bx,y1:by,x2:x,y2:y});lines[i].style.display=arrows.checked&&i!==observer&&scale>1.01?'':'none';
   const d=separation(i,observer);set(dots[i].group,{transform:`translate(${px(d)} ${py(d*(scale-1))})`,'aria-pressed':String(i===target)});dots[i].group.style.display=i===observer?'none':'';dots[i].dot.dataset.selected=String(i===target);
  });
  const [tx,ty]=projectExpansion(target,observer,scale),distance=separation(target,observer);
  set(ruler,{x1:ox,y1:oy,x2:tx,y2:ty});set(measure,{x:(ox+tx)/2,y:(oy+ty)/2-10});measure.textContent=`${fmt(distance*scale,1)} passos`;
  set(fit,{x1:px(0),x2:px(maxD),y1:py(0),y2:py(maxD*(scale-1))});
  visual?.state({value:scale});
  buttons.forEach((b,i)=>{b.setAttribute('aria-pressed',String(i===observer));b.style.setProperty('--galaxy-color',colors[i]);});
  targets.forEach((b,i)=>{b.disabled=i===observer;b.setAttribute('aria-pressed',String(i===target));});
  const name=(i:number)=>i<3?'ABC'[i]:String(i+1);
  q(root,'[data-e-observer-label]').textContent=`Você observa da galáxia ${name(observer)}`;
  q(root,'[data-e-selection]').textContent=`${name(observer)} → ${name(target)}: ${fmt(distance,1)} passos no início · ${fmt(distance*scale,1)} agora · +${fmt(distance*(scale-1),1)} de afastamento.`;
  q<HTMLElement>(root,'[data-e-finish]').hidden=scale<SCALE_MAX;
  const guide=q(root,'[data-e-guide]');const message=scale<1.5?'Observe a régua: o espaço cresce e as galáxias mantêm seu tamanho.':scale<2?'Compare um ponto próximo e outro distante no gráfico: o mais distante ganhou mais distância.':'Troque a galáxia observadora: o mesmo padrão aparece de outro lugar.';if(guide.textContent!==message)guide.textContent=message;
  reading.textContent=`As distâncias crescem na mesma proporção: ${fmt(scale,2)} vezes o espaçamento inicial. As galáxias mantêm seu tamanho. Mude de observador: ninguém ocupa um centro privilegiado.`;
  range.setAttribute('aria-valuetext',`${fmt(scale,2)} vezes o espaçamento inicial`);
  if(!anim.running())live.textContent=`Observador ${name(observer)}. Galáxia ${name(target)}: antes ${fmt(distance,1)} passos, agora ${fmt(distance*scale,1)}.`;
  if(moved&&scale>=1.5)root.dispatchEvent(new CustomEvent('cosmos:badge',{bubbles:true,detail:{id:'sem-centro'}}));
 };
 const syncPlay=()=>{play.setAttribute('aria-pressed',String(anim.running()));play.textContent=anim.running()?'Pausar':scaleValue>=SCALE_MAX?'Recomeçar':reduced()?'Avançar expansão':'Deixar o espaço crescer';};
 const anim=animator(root,dt=>{
  const previous=scaleValue;scaleValue=Math.min(SCALE_MAX,scaleValue+dt*.00022*Number(speed.value));
  const stop=stops.checked?[1.5,2,2.5].find(value=>previous<value-1e-6&&scaleValue>=value):undefined;
  if(stop!==undefined)scaleValue=stop;
  range.value=String(scaleValue);render();const more=scaleValue<SCALE_MAX&&stop===undefined;
  if(!more)queueMicrotask(()=>{syncPlay();render();});return more;
 });
 const automatic=visibleMotion(volume,{start(){anim.start();syncPlay();},stop(){anim.stop();syncPlay();render();},running:()=>anim.running(),pauseTarget:root});
 root.addEventListener('cosmos:autopause',syncPlay);motionPreference.addEventListener('change',syncPlay);
 const halt=()=>{automatic.manual();anim.stop();syncPlay();};
 buttons.forEach((b,i)=>b.addEventListener('click',()=>{halt();moved ||= i!==observer;observer=i;if(target===observer)target=(observer+1)%3;volume.classList.add('is-reframing');clearTimeout(transition);transition=window.setTimeout(()=>volume.classList.remove('is-reframing'),350);render();}));
 targets.forEach((b,i)=>b.addEventListener('click',()=>{target=i;render();}));
 play.addEventListener('click',()=>{
  automatic.manual();if(anim.running()){anim.stop();syncPlay();return;}
  if(reduced()){scaleValue=scaleValue>=SCALE_MAX?1:Math.min(SCALE_MAX,scaleValue+.25);range.value=String(scaleValue);render();syncPlay();return;}
  if(scaleValue>=SCALE_MAX){scaleValue=1;range.value='1';}
  anim.start();syncPlay();
 });
 range.addEventListener('input',()=>{halt();scaleValue=Number(range.value);render();syncPlay();});
 arrows.addEventListener('change',render);before.addEventListener('change',render);
 qa<HTMLButtonElement>(root,'[data-e-reset]').forEach(b=>b.addEventListener('click',()=>{halt();scaleValue=1;range.value='1';observer=0;target=1;render();syncPlay();}));
 import('../visual/runtime').then(async({observeScene,whenNear})=>{
  if(!await whenNear(volume))return;
  volume.dataset.sceneLoading='true';
  const {prepareEmissionGalaxies,emissionSize,emissionReady}=await import('../visual/galaxy-emission');const size=emissionSize(volume.clientWidth,volume.dataset.cosmosQuality==='low'?'low':'auto');await prepareEmissionGalaxies(size);
  const {expansion}=await import('../visual/expansion-pilot');visual=observeScene(volume,()=>expansion(()=>observer,()=>arrows.checked,volume.dataset.cosmosQuality==='low'&&emissionReady(512)?512:size,()=>target,()=>before.checked));visual.state({value:scaleValue});volume.dataset.sceneLoading='false';
 }).catch(()=>{volume.dataset.visualFallback='true';volume.dataset.sceneLoading='false';});
 window.addEventListener('pagehide',event=>{if(!event.persisted){clearTimeout(transition);motionPreference.removeEventListener('change',syncPlay);automatic.dispose();anim.dispose();visual?.dispose();}});
 initGuess(root);render();syncPlay();
}
