import { plate, galaxy as drawGalaxy } from './plate';
import { PLANCK } from '../../lib/cosmology';
import { photonAt, photonTable } from '../../lib/photon';
import { animator, svg } from './common';

export interface Tempo3D { set(z: number, lamNm: number): void; dispose(): void }

/** Projeção do caminho radial FLRW. A potência comprime apenas as distâncias desenhadas. */
export function mountTempo3D(host: HTMLElement, reduced: () => boolean): Tempo3D {
  let z = 0, phase = 0, table = photonTable(0, PLANCK);
  const scene = svg('svg', { viewBox: '0 0 640 400', role: 'img',
    'aria-label': 'Percurso da luz entre a região emissora e a Via Láctea durante a expansão.' }, host);
  const source = svg('g', {}, scene);
  const galaxy = svg('ellipse', { rx: 20, ry: 9, fill: '#d4b59b' }, source);
  const gas = svg('circle', { r: 24, fill: '#cf835e', opacity: .65 }, source);
  const label = svg('text', { y: -36, 'text-anchor': 'middle', fill: '#ffe3c3' }, source);
  svg('ellipse', { cx: 490, cy: 210, rx: 20, ry: 9, fill: '#89acdc' }, scene);
  svg('text', { x: 490, y: 254, 'text-anchor': 'middle', fill: '#cbddff' }, scene, 'nós · hoje');
  const ray = svg('line', { x2: 490, y1: 210, y2: 210, stroke: '#ffbd87', 'stroke-dasharray': '3 6' }, scene);
  const light = svg('circle', { cy: 210, r: 5, fill: '#fff1a6' }, scene);
  const button = host.querySelector<HTMLButtonElement>('[data-3d-play]')!;
  let sourceX = 0, lightX = 0, localScale = 1, observedNm = 656.28;
  for (const body of [galaxy, gas, light, scene.querySelector('ellipse[cx]')!]) body.setAttribute('data-lab-body', '');
  const surface = plate(scene, ['spiral','barred','plasma'], (ctx, img) => {
    drawGalaxy(ctx,img('barred'),490,210,39,-.24);
    if (z < .005) return;
    if (z < 20) drawGalaxy(ctx,img('spiral'),sourceX,210,40,.23);
    else ctx.drawImage(img('plasma'),sourceX-42,179,84,62);
    // Wavelength along this geodesic tracks a(t); compress the displayed crest spacing.
    const wavelength = observedNm * localScale;
    const period = 8 * (localScale * (1+z)) ** .22;
    ctx.save();
    ctx.strokeStyle = wavelength < 750 ? '#ff987e' : '#c0cede';
    if (wavelength >= 750) ctx.setLineDash([3,3]);
    ctx.beginPath();
    for (let d = 0; d <= Math.min(74, lightX-sourceX); d++) {
      const y = 210 + 5*Math.sin(d*2*Math.PI/period);
      if (d === 0) ctx.moveTo(lightX,y); else ctx.lineTo(lightX-d,y);
    }
    ctx.stroke(); ctx.restore();
    const glow = ctx.createRadialGradient(lightX,210,1,lightX,210,10);
    glow.addColorStop(0,'#fff5c7'); glow.addColorStop(.34,'#ffd585'); glow.addColorStop(1,'rgba(246,175,81,0)');
    ctx.fillStyle = glow; ctx.fillRect(lightX-10,200,20,20);
  });
  const paint = () => {
    const { a, chi } = photonAt(table, phase);
    const span = 390 * a ** .18;
    localScale = a; sourceX = 490 - span; lightX = 490 - span * chi; surface.refresh();
    source.setAttribute('transform', `translate(${490 - span} 210)`);
    ray.setAttribute('x1', String(490 - span));
    light.setAttribute('cx', String(490 - span * chi));
  };
  const anim = animator(host, dt => {
    phase += dt / 5200;
    if (phase > 1.25) phase = 0;
    paint();
    return true;
  });
  const sync = () => {
    button.setAttribute('aria-pressed', String(anim.running()));
    button.querySelector('[data-3d-play-label]')!.textContent = reduced() ? 'Avançar percurso' : anim.running() ? 'Pausar' : 'Continuar';
    button.firstElementChild!.textContent = anim.running() ? '❚❚' : '▶';
  };
  const click = () => { if (reduced()) { phase = phase >= 1 ? 0 : Math.min(1,phase+.25); paint(); } else if (anim.running()) anim.stop(); else anim.start(); sync(); };
  button.addEventListener('click', click);
  host.addEventListener('cosmos:autopause', sync);
  const set = (next: number, lamNm: number) => {
    observedNm = lamNm;
    if (next !== z) {
      z = next;
      table = photonTable(z, PLANCK);
      phase = reduced() ? 1 : 0;
      anim.stop();
      if (!reduced() && z >= .005) anim.start();
    }
    const now = z < .005;
    for (const node of [source, ray, light]) node.style.display = now ? 'none' : '';
    galaxy.style.display = z < 20 ? '' : 'none';
    gas.style.display = z >= 20 ? '' : 'none';
    label.textContent = z >= 20 ? 'região de gás · emissão' : 'galáxia · emissão';
    button.hidden = now;
    paint();
    sync();
  };
  const dispose = () => {
    anim.dispose(); surface.dispose();
    button.removeEventListener('click', click);
    host.removeEventListener('cosmos:autopause', sync);
    scene.remove();
  };
  set(0, 656.28);
  return { set, dispose };
}
