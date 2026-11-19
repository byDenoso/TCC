import { baked, depthCanvas } from './lesson-depth';
import { u } from '../lib/url';
import { motionPreference } from './motion-preference';
import { $, $$, setText } from './dom';
import { clampMass, massLabel, stellarPath } from '../lib/stars';
import { format } from '../lib/format';
import { getParam, setParams } from '../lib/url-state';
import { drawStellar } from './micro/stellar';
import { visibleMotion } from './visible-motion';

/** Laboratório estelar: a massa escolhe o caminho; as etapas são desenhadas e podem ser percorridas passo a passo. */
export function initStars(): void {
  const root = $('[data-island="stars"]');
  if (!root) return;
  const slider = $<HTMLInputElement>('[data-star-mass]', root)!;
  const presets = $$<HTMLButtonElement>('[data-mass]', root);
  const svg = $<SVGSVGElement>('[data-star-svg]', root);
  const caption = $('[data-star-caption]', root);
  const play = $<HTMLButtonElement>('[data-star-play]', root);
  const reduced = motionPreference;
  const layer = svg ? document.createElementNS('http://www.w3.org/2000/svg', 'g') : null;
  if (svg && layer) svg.append(layer);
  let step = 2, t = 1, playing = false, frame = 0, last = 0;
  let automatic: ReturnType<typeof visibleMotion> | null = null;
  // A nuvem é o ambiente ilustrativo das duas primeiras etapas.
  const cloud = svg && layer ? document.createElementNS(svg.namespaceURI!, 'image') : null;
  if (cloud && layer) {
    cloud.setAttribute('x', '35');
    cloud.setAttribute('y', '15');
    cloud.setAttribute('width', '230');
    cloud.setAttribute('height', '215');
    cloud.setAttribute('preserveAspectRatio', 'xMidYMid slice');
    cloud.setAttribute('opacity', '.55');
    cloud.setAttribute('aria-hidden', 'true');
    layer.before(cloud);
  }

  const texture = document.createElement('canvas');
  texture.width=480; texture.height=270;
  if (svg) {
    const plane=document.createElementNS('http://www.w3.org/2000/svg','foreignObject');
    plane.setAttribute('width','480');plane.setAttribute('height','270');plane.setAttribute('aria-hidden','true');
    plane.style.pointerEvents='none';plane.style.overflow='hidden';texture.style.pointerEvents='none';
    plane.append(texture);svg.append(plane);texture.dataset.stellarDepth='';
  }
  const tinted=document.createElement('canvas');
  let lastColor='';
  const paintSurface=depthCanvas(svg ? texture : null,(ctx,image)=>{
    const star=image('/renders/micro-hd/sol.webp');
    if(!layer || !star)return;
    // The model's own disks set the center and radius at this mass, stage and instant.
    for(const disk of layer.querySelectorAll<SVGCircleElement>('circle[fill^="url("]')) {
      if(disk.getAttribute('fill')?.includes('-halo'))continue;
      const radius=disk.r.baseVal.value*1.07, x=disk.cx.baseVal.value, y=disk.cy.baseVal.value;
      const gradientId=disk.getAttribute('fill')!.slice(5,-1);
      const color=layer.querySelector(`[id="${gradientId}"] stop[offset="50%"]`)?.getAttribute('stop-color') ?? '#fff';
      if(color!==lastColor){
        tinted.width=star.naturalWidth;tinted.height=star.naturalHeight;
        const material=tinted.getContext('2d');
        if(material){
          material.drawImage(star,0,0);
          material.globalCompositeOperation='color';material.fillStyle=color;
          material.fillRect(0,0,tinted.width,tinted.height);
          material.globalCompositeOperation='destination-in';material.drawImage(star,0,0);
          lastColor=color;
        }
      }
      ctx.drawImage(lastColor===color?tinted:star,x-radius,y-radius,radius*2,radius*2);
    }
    if(step===4 && clampMass(Number(slider.value))>=8) {
      const disk=image(baked('disk'));
      if(disk) {ctx.globalAlpha=1;ctx.drawImage(disk,173,94,64,64);}
    }
  });
  const paint = () => {
    const m = clampMass(Number(slider.value));
    if (layer && caption) caption.textContent = drawStellar(layer, m, step, t);
    paintSurface();
    if (cloud) {
      if (step < 2 && !cloud.hasAttribute('href')) cloud.setAttribute('href', u('/models/stellar/plates/cloud.webp'));
      cloud.setAttribute('visibility', step < 2 ? 'visible' : 'hidden');
    }
    $$<HTMLButtonElement>('[data-star-step]', root).forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.starStep) === step)));
  };
  const setPlaying = (on: boolean) => {
    playing = on;
    if (!play) return;
    play.setAttribute('aria-pressed', String(on));
    setText($('[data-star-play-label]', play), on ? 'Pausar' : reduced.matches ? 'Avançar' : 'Reproduzir ciclo');
    $('.mx-ico', play)!.textContent = on ? '❚❚' : '▶';
  };
  const stop = () => { if (!playing) return; cancelAnimationFrame(frame); setPlaying(false); paint(); };
  const tick = (now: number) => {
    if (!playing) return;
    t = Math.min(1, t + (last ? Math.min(64, now - last) : 16) / 1500); last = now;
    if (t >= 1) { if (step < 4) { step += 1; t = 0; } else { stop(); return; } }
    paint(); frame = requestAnimationFrame(tick);
  };
  const next = () => { stop(); step = step >= 4 ? 0 : step + 1; t = 1; paint(); };

  const render = (url = true) => {
    const m = clampMass(Number(slider.value));
    const path = stellarPath(m);
    setText($('[data-star-value]', root), massLabel(m, (n) => format(n)));
    setText($('[data-star-class]', root), path.category); setText($('[data-star-title]', root), path.title);
    setText($('[data-star-summary]', root), path.summary); setText($('[data-star-time]', root), path.time);
    setText($('[data-star-note]', root), path.note);
    const list = $('[data-star-path]', root)!;
    list.replaceChildren(...path.steps.map((name, i) => {
      const li = document.createElement('li');
      const b = document.createElement('button'); b.type = 'button'; b.dataset.starStep = String(i);
      const n = document.createElement('span'); n.textContent = String(i + 1).padStart(2, '0');
      const p = document.createElement('p'); p.textContent = name; b.append(n, p);
      b.addEventListener('click', () => { automatic?.manual(); stop(); step = i; t = 1; paint(); });
      li.append(b); return li;
    }));
    presets.forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.mass) === m)));
    paint();
    if (url) setParams({ massa: m === 1 ? null : String(m).replace('.', ',') });
  };
  slider.addEventListener('input', () => { automatic?.manual(); stop(); render(); });
  presets.forEach((b) => b.addEventListener('click', () => { automatic?.manual(); stop(); slider.value = b.dataset.mass!; render(); }));
  const start = () => {
    if (step >= 4 && t >= 1) step = 0;
    if (t >= 1) t = 0;
    last = 0; setPlaying(true); frame = requestAnimationFrame(tick);
  };
  play?.addEventListener('click', () => {
    automatic?.manual();
    if (playing) { stop(); return; }
    if (reduced.matches) { next(); return; }
    start();
  });
  $('[data-star-next]', root)?.addEventListener('click', () => { automatic?.manual(); next(); });
  $('[data-star-reset]', root)?.addEventListener('click', () => { automatic?.manual(); stop(); step = 2; t = 1; paint(); });
  window.addEventListener('pagehide',(event)=>{stop();if(!event.persisted){automatic?.dispose();}});
  reduced.addEventListener('change', () => { if (reduced.matches) { stop(); t = 1; paint(); } setPlaying(playing); });
  const q = getParam('massa');
  if (q) slider.value = String(clampMass(Number(q.replace(',', '.'))));
  setPlaying(false);
  render(false);
  if (svg && play) automatic = visibleMotion(svg.parentElement!, { start, stop, running: () => playing });
}
