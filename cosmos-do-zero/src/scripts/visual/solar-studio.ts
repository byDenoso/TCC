import { planets } from '../../data/client';
import { u } from '../../lib/url';
import { mountWorldView } from './world-view';
import { svg,animator,reduced } from '../lab/common';
import { orbitalPeriodYears,SOLAR_MASS_KG } from '../../lib/physics';
import { motionPreference } from '../motion-preference';
export async function initSolarStudio():Promise<void>{
 for(const root of document.querySelectorAll<HTMLElement>('[data-solar-studio]')){
  let mode='sizes',selected=2,moon=false;
  const stage=root.querySelector<HTMLElement>('[data-solar-stage]')!,fallback=root.querySelector<SVGSVGElement>('[data-solar-fallback]')!,ruler=root.querySelector<SVGSVGElement>('[data-solar-ruler]')!;
  const modes=[...root.querySelectorAll<HTMLButtonElement>('[data-solar-mode]')],buttons=[...root.querySelectorAll<HTMLButtonElement>('[data-solar-planet]')];
  const largest=Math.max(...planets.map(p=>p.radius)),furthest=Math.max(...planets.map(p=>p.distance));
  const play=root.querySelector<HTMLButtonElement>('[data-solar-play]')!;
  const reset=root.querySelector<HTMLButtonElement>('[data-solar-reset]')!;
  const layers={clouds:true,atmosphere:true};
  const view = mountWorldView(root, stage, () => {
    if (moon) return ['lua'];
    const id = planets[selected].id;
    if (id !== 'terra' || (layers.clouds && layers.atmosphere)) return [id];
    return [layers.clouds ? 'terra-nuvens' : layers.atmosphere ? 'terra-ar' : 'terra-solo'];
  });
  const layerPanel=root.querySelector<HTMLElement>('[data-solar-layers]')!,layerNote=root.querySelector<HTMLElement>('[data-solar-layer-note]')!;
  const layerInputs=[...root.querySelectorAll<HTMLInputElement>('[data-solar-layer]')];
  layerInputs.forEach(input=>input.addEventListener('change',()=>{layers[input.dataset.solarLayer as keyof typeof layers]=input.checked;render();}));
  const sync=()=>{reset.disabled=play.disabled;play.setAttribute('aria-pressed',String(animation.running()));play.textContent=play.disabled?'Rotação indisponível nesta visualização':animation.running()?'Pausar rotação':reduced()?'Avançar rotação':'Ver rotação';};
  const render=()=>{
   const p=planets[selected];
   const earth=p.id==='terra'&&!moon;layerPanel.hidden=!earth;layerNote.hidden=!earth;
   layerInputs.forEach(input=>input.disabled=!earth);
   layerNote.textContent='Alterne o mosaico de nuvens e o brilho atmosférico ilustrativo para observar a superfície.';
   root.querySelector('[data-solar-fact="radius"]')!.textContent=(moon?1737:p.radius).toLocaleString('pt-BR')+' km';
   root.querySelector('[data-solar-fact="distance"]')!.previousElementSibling!.textContent=moon?'Distância à Terra':'Distância ao Sol';
   root.querySelector('[data-solar-fact="distance"]')!.textContent=moon?'384 mil km da Terra':p.distance.toLocaleString('pt-BR')+' UA';
   const years=orbitalPeriodYears(p.distance,1,p.mass/SOLAR_MASS_KG);const period=root.querySelector('[data-solar-fact="period"]')!;period.previousElementSibling!.textContent=moon?'Uma volta à Terra':'Uma volta ao Sol';period.textContent=moon?'27,3 dias':years.toLocaleString('pt-BR',{maximumFractionDigits:2})+(Math.round(years*100)===100?' ano terrestre':' anos terrestres');
   root.querySelector<HTMLButtonElement>('[data-solar-moon]')!.setAttribute('aria-pressed',String(moon));modes.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.solarMode===mode)));buttons.forEach((b,i)=>b.setAttribute('aria-pressed',String(i===selected&&!moon)));
   root.querySelector<HTMLElement>('[data-solar-close-note]')!.textContent=(moon?'Lua':p.id==='mercurio'?'Mercúrio · cores realçadas MESSENGER':p.name)+' · detalhe ampliado, fora da escala da régua';
   root.querySelector<HTMLImageElement>('[data-solar-poster]')!.alt=(moon?'Lua':p.name)+': mapa de origem declarada em geometria e iluminação ilustrativas.';
   root.querySelector<HTMLElement>('[data-solar-caption]')!.textContent=`${p.name}: raio de ${p.radius.toLocaleString('pt-BR')} km; semieixo maior da órbita ao redor do Sol de ${p.distance.toLocaleString('pt-BR')} UA. A rotação é ilustrativa e comprimida; não compare velocidades nesta vista.`;
   if(moon){root.querySelector<HTMLElement>('[data-solar-caption]')!.textContent='Lua: raio de cerca de 1.737 km. Mosaico LROC e relevo visual LOLA; uma superfície sem halo atmosférico. A vista ampliada não tem a escala da régua.';}
   root.querySelector<HTMLElement>('[data-solar-limit]')!.textContent=mode==='sizes'?'Diâmetros dos planetas proporcionais entre si. Separações ajustadas para caber; Sol e anéis omitidos nesta régua.':'Semieixos maiores das órbitas proporcionais. Corpos ampliados e desenhados com o mesmo tamanho para poder vê-los; não use esta régua para comparar diâmetros.';
   root.querySelector<HTMLElement>('[data-solar-period]')!.textContent=`No modelo de dois corpos, uma volta de ${p.name} leva aproximadamente ${orbitalPeriodYears(p.distance,1,p.mass/SOLAR_MASS_KG).toLocaleString('pt-BR',{maximumFractionDigits:3})} anos terrestres.`;
   if(moon)root.querySelector<HTMLElement>('[data-solar-period]')!.textContent='A Lua leva cerca de 27,3 dias para orbitar a Terra em relação às estrelas. A fórmula dos planetas ao redor do Sol não é aplicada a esta escolha.';
   fallback.replaceChildren();
   ruler.replaceChildren();
   planets.forEach((planet, i) => {
     const x = mode === 'sizes' ? 38 + i * 80 : 24 + planet.distance / furthest * 572;
     const radius = mode === 'sizes' ? planet.radius / largest * 28 : 6;
     const side = radius * 2.4; // Both export tiers have the same globe-to-frame ratio.
     const id = planet.id === 'saturno' ? 'saturno-globo' : planet.id;
     svg('image', {href: u(`/models/worlds-hd/thumbs/${id}.webp`), x:x-side/2, y:40-side/2, width:side, height:side}, ruler);
     if (mode === 'sizes' || i === selected)
       svg('text', {x, y:90, 'text-anchor':'middle', fill:'var(--ink-2)', 'font-size':12}, ruler, planet.name);
   });
   view.refresh();
  };
  const advance = () => view.advance(!moon && planets[selected].rotation < 0 ? -1 : 1);
  let elapsed = 0;
  const animation = animator(stage, dt => {
    elapsed += dt;
    if (elapsed >= 160) { advance(); elapsed %= 160; }
    return true;
  });
  const stop = () => { animation.stop(); elapsed = 0; sync(); };
  const preference = () => queueMicrotask(sync);
  motionPreference.addEventListener('change', preference);
  stage.addEventListener('worldmanual', stop);
  stage.addEventListener('cosmos:autopause', sync);
  play.addEventListener('click', () => {
    if (reduced()) advance();
    else if (animation.running()) stop();
    else animation.start();
    sync();
  });
  const rewind = () => { stop(); view.setFrame(0); };
  reset.addEventListener('click', rewind);
  modes.forEach(button => button.addEventListener('click', () => {
    mode = button.dataset.solarMode!;
    render();
  }));
  buttons.forEach((button, index) => button.addEventListener('click', () => {
    selected = index; moon = false; rewind(); render();
  }));
  root.querySelector('[data-solar-moon]')!.addEventListener('click', () => {
    moon = true; rewind(); render();
  });
  render(); sync();
  window.addEventListener('pagehide', event => {
    if (!event.persisted) {
      animation.dispose();
      motionPreference.removeEventListener('change', preference);
    }
  });
 }
}
