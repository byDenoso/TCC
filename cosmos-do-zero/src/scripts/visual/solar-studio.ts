import { u } from '../../lib/url';
import { planets } from '../../data/client';
import { attachWorldView } from './world-view';
import type { MountedScene } from './runtime';
import { svg,animator,reduced } from '../lab/common';
import { orbitalPeriodYears,SOLAR_MASS_KG } from '../../lib/physics';
export async function initSolarStudio():Promise<void>{
 for(const root of document.querySelectorAll<HTMLElement>('[data-solar-studio]')){
  let mode='sizes',selected=2,moon=false,phase=0,ticket=0,alive=true,view:MountedScene|null=null;
  const stage=root.querySelector<HTMLElement>('[data-solar-stage]')!,fallback=root.querySelector<SVGSVGElement>('[data-solar-fallback]')!,ruler=root.querySelector<SVGSVGElement>('[data-solar-ruler]')!;
  const modes=[...root.querySelectorAll<HTMLButtonElement>('[data-solar-mode]')],buttons=[...root.querySelectorAll<HTMLButtonElement>('[data-solar-planet]')];
  const largest=Math.max(...planets.map(p=>p.radius)),furthest=Math.max(...planets.map(p=>p.distance));
  const play=root.querySelector<HTMLButtonElement>('[data-solar-play]')!;
  const sync=()=>{play.setAttribute('aria-pressed',String(animation.running()));play.textContent=animation.running()?'Pausar rotação':reduced()?'Avançar rotação':'Ver rotação';};
  const render=()=>{
   const p=planets[selected];root.querySelector<HTMLButtonElement>('[data-solar-moon]')!.setAttribute('aria-pressed',String(moon));modes.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.solarMode===mode)));buttons.forEach((b,i)=>b.setAttribute('aria-pressed',String(i===selected&&!moon)));
   root.querySelector<HTMLElement>('[data-solar-close-note]')!.textContent=(moon?'Lua':p.id==='mercurio'?'Mercúrio · cores realçadas MESSENGER':p.name)+' · detalhe ampliado, fora da escala da régua';
   root.querySelector<HTMLImageElement>('[data-solar-poster]')!.alt=(moon?'Lua':p.name)+': mapa de origem declarada em geometria e iluminação ilustrativas.';
   root.querySelector<HTMLImageElement>('[data-solar-poster]')!.src=u('/models/portraits/'+(moon?'lua':p.id)+'.webp');
   root.querySelector<HTMLElement>('[data-solar-caption]')!.textContent=`${p.name}: raio de ${p.radius.toLocaleString('pt-BR')} km; semieixo maior da órbita ao redor do Sol de ${p.distance.toLocaleString('pt-BR')} UA. A rotação é ilustrativa e comprimida; não compare velocidades nesta vista.`;
   if(moon){root.querySelector<HTMLElement>('[data-solar-caption]')!.textContent='Lua: raio de cerca de 1.737 km. Mosaico LROC e relevo visual LOLA; uma superfície sem halo atmosférico. A vista ampliada não tem a escala da régua.';}
   root.querySelector<HTMLElement>('[data-solar-limit]')!.textContent=mode==='sizes'?'Diâmetros dos planetas proporcionais entre si. Separações ajustadas para caber; Sol e anéis omitidos nesta régua.':'Semieixos maiores das órbitas proporcionais. Corpos ampliados e desenhados com o mesmo tamanho para poder vê-los; não use esta régua para comparar diâmetros.';
   root.querySelector<HTMLElement>('[data-solar-period]')!.textContent=`No modelo de dois corpos, uma volta de ${p.name} leva aproximadamente ${orbitalPeriodYears(p.distance,1,p.mass/SOLAR_MASS_KG).toLocaleString('pt-BR',{maximumFractionDigits:3})} anos terrestres.`;
   if(moon)root.querySelector<HTMLElement>('[data-solar-period]')!.textContent='A Lua leva cerca de 27,3 dias para orbitar a Terra em relação às estrelas. A fórmula dos planetas ao redor do Sol não é aplicada a esta escolha.';
   fallback.replaceChildren();ruler.replaceChildren();planets.forEach((p,i)=>{const x=mode==='sizes'?38+i*80:24+p.distance/furthest*572,r=mode==='sizes'?p.radius/largest*28:6;svg('circle',{cx:x,cy:40,r,fill:i===selected?'#ce804c':'#91a9be'},ruler);if(mode==='sizes'||i===selected)svg('text',{x,y:90,'text-anchor':'middle',fill:'var(--ink-2)','font-size':12},ruler,p.name);});view?.state({value:selected,phase});
  };
  const animation=animator(stage,dt=>{phase+=dt*.00008;view?.state({phase});return true;});
  play.addEventListener('click',()=>{if(reduced()){phase+=.25;render();}else if(animation.running())animation.stop();else animation.start();sync();});stage.addEventListener('cosmos:autopause',sync);
  root.querySelector<HTMLButtonElement>('[data-solar-reset]')!.addEventListener('click',()=>{animation.stop();phase=0;render();sync();});
  const refresh=async()=>{const token=++ticket;view?.dispose();view=null;render();const next=await attachWorldView(stage,()=>[moon?'lua':planets[selected].id],undefined,()=>alive&&token===ticket);if(alive&&token===ticket){view=next;render();}else next?.dispose();};
  modes.forEach(b=>b.addEventListener('click',()=>{mode=b.dataset.solarMode!;render();}));buttons.forEach((b,i)=>b.addEventListener('click',()=>{selected=i;moon=false;phase=0;void refresh();}));root.querySelector<HTMLButtonElement>('[data-solar-moon]')!.addEventListener('click',()=>{moon=true;phase=0;void refresh();});render();sync();
  await refresh();
  window.addEventListener('pagehide',e=>{ticket++;if(!e.persisted){alive=false;animation.dispose();view?.dispose();}});
  window.addEventListener('pageshow',e=>{if(e.persisted&&!view)void refresh();});
 }
}
