import { planets } from '../../data/client';
import type { Scene, SceneMap } from './engine';
import { C, arrow, bar, clamp, clear, ease, el, fmt, g, lerp, rng, sphere, star, text } from './draw';

const disco = (): Scene => {
  let layer: SVGGElement;
  const rnd = rng(23);
  const grains = Array.from({ length: 160 }, () => { const a = rnd() * Math.PI * 2, r = 25 + Math.pow(rnd(), 0.8) * 190; return [a, r] as [number, number]; });
  const caps = [
    'Uma nuvem de gás e poeira, girando devagar, começa a se contrair.',
    'Ao encolher, ela gira mais rápido e se achata num disco, com o Sol jovem no centro.',
    'Perto do Sol, só rocha e metal ficam sólidos. Além da linha do gelo, a água congela e há muito mais material sólido para juntar.',
    'Os grãos grudam e crescem: perto, mundos rochosos pequenos; longe, núcleos grandes que puxam gás e viram gigantes.'
  ];
  return {
    duration: 1500,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const k = ease(t), cx = 240, cy = 130, flat = v === 0 ? 1 : v === 1 ? lerp(1, 0.28, k) : 0.28;
      if (v <= 1) for (const [a, r] of grains) el('circle', { cx: cx + Math.cos(a + t * 0.6) * r * (v === 0 ? 0.6 : 1), cy: cy + Math.sin(a + t * 0.6) * r * flat * (v === 0 ? 0.6 : 1), r: 1.8, fill: C.ink2, opacity: 0.55 }, layer);
      if (v >= 2) {
        el('ellipse', { cx, cy, rx: 220, ry: 62, fill: C.soft }, layer);
        el('ellipse', { cx, cy, rx: 105, ry: 29, fill: 'none', stroke: C.blue, 'stroke-width': 2, 'stroke-dasharray': '6 5' }, layer);
        text(layer, cx + 60, cy - 38, 'linha do gelo', { class: 'mx-t small strong', fill: C.blue });
        if (v === 2) for (const [a, r] of grains) { const ice = r > 105; el('circle', { cx: cx + Math.cos(a) * r, cy: cy + Math.sin(a) * r * 0.28, r: ice ? 2.6 : 1.6, fill: ice ? '#8db3e8' : '#a0764a' }, layer); }
        if (v === 3) {
          [[48, 3], [66, 4.5], [84, 5], [100, 3.5]].forEach(([r, s]) => el('circle', { cx: cx + r * Math.cos(1 + r), cy: cy + r * 0.28 * Math.sin(1 + r), r: s * k + 1, fill: '#a0764a' }, layer));
          [[135, 14], [170, 11], [195, 8], [215, 8]].forEach(([r, s]) => el('circle', { cx: cx + r * Math.cos(r), cy: cy + r * 0.28 * Math.sin(r), r: s * k + 2, fill: '#d9b27a' }, layer));
        }
      }
      star(layer, cx, cy, v === 0 ? 6 : 12, C.gold);
      if (v === 0) for (let i = 0; i < 4; i++) { const a = (i / 4) * Math.PI * 2; arrow(layer, cx + Math.cos(a) * 140, cy + Math.sin(a) * 85, cx + Math.cos(a + 0.4) * 140, cy + Math.sin(a + 0.4) * 85, C.muted, 1.5); }
      return caps[v];
    }
  };
};

const rochosos = (): Scene => {
  let layer: SVGGElement;
  const P = [
    { n: 'Mercúrio', light: 6.7, atm: 'quase nenhuma', atmW: 0, temp: 167, col: '#9a8f86', cap: 'Mercúrio recebe quase 7 vezes mais luz do Sol que a Terra, mas sem atmosfera o calor escapa: de dia passa de 400 °C, à noite cai abaixo de −170 °C.' },
    { n: 'Vênus', light: 1.9, atm: '92 vezes a da Terra', atmW: 1, temp: 464, col: '#e2c28a', cap: 'Vênus recebe menos luz que Mercúrio, mas sua atmosfera grossa de gás carbônico prende o calor: é o planeta mais quente, dia e noite.' },
    { n: 'Terra', light: 1, atm: '1 (referência)', atmW: 0.35, temp: 15, col: '#3d7cc9', cap: 'Terra: atmosfera moderada e efeito estufa na medida para a água ficar líquida em boa parte da superfície.' },
    { n: 'Marte', light: 0.43, atm: '0,6% da Terra', atmW: 0.08, temp: -65, col: '#c1592f', cap: 'Marte recebe menos da metade da luz da Terra e tem atmosfera muito fina: é frio e seco na superfície.' }
  ];
  return {
    duration: 900,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const p = P[v], k = ease(t);
      el('circle', { cx: 80, cy: 125, r: 44 + 22 * p.atmW, fill: '#e8a85a', opacity: 0.12 + 0.35 * p.atmW }, layer);
      sphere(layer, 80, 125, 42, p.col);
      text(layer, 80, 200, p.n, { class: 'mx-t strong', 'text-anchor': 'middle' });
      bar(layer, 170, 50, 210, 7, p.light * k, 'luz do Sol recebida (Terra = 1)', fmt(p.light, 1), C.gold);
      bar(layer, 170, 115, 210, 1, p.atmW * k, 'atmosfera (pressão)', p.atm, C.blue);
      bar(layer, 170, 180, 210, 600, (p.temp + 100) * k, 'temperatura média', `${fmt(p.temp)} °C`, C.accent);
      return p.cap;
    }
  };
};

const gigantes = (): Scene => {
  let layer: SVGGElement;
  const bands = [
    { to: 0.12, name: 'nuvens', col: '#e8cfa4' },
    { to: 0.45, name: 'hidrogênio gasoso', col: '#d9b27a' },
    { to: 0.75, name: 'hidrogênio líquido', col: '#b98a55' },
    { to: 0.93, name: 'hidrogênio "metálico"', col: '#8a6238' },
    { to: 1, name: 'núcleo?', col: '#5a4128' }
  ];
  return {
    init(svg) { layer = g(svg); },
    value: (v) => (v < 0.12 ? 'nas nuvens' : v < 0.14 ? 'nível de 1 bar' : `${Math.round(v * 100)}% do caminho ao centro`),
    draw(v) {
      clear(layer);
      const top = 20, h = 230, x = 60, w = 120;
      let y0 = top;
      for (const b of bands) { const y1 = top + b.to * h; el('rect', { x, y: y0, width: w, height: y1 - y0, fill: b.col }, layer); text(layer, x + w + 12, (y0 + y1) / 2 + 5, b.name, { class: 'mx-t small' }); y0 = y1; }
      const y1bar = top + 0.13 * h;
      el('line', { x1: x - 10, x2: x + w + 10, y1: y1bar, y2: y1bar, stroke: C.accent, 'stroke-width': 2, 'stroke-dasharray': '5 4' }, layer);
      text(layer, x - 14, y1bar + 5, '1 bar', { class: 'mx-t small strong warm', 'text-anchor': 'end' });
      const py = top + v * h;
      el('path', { d: `M${x + w / 2} ${py} l-10 -16 h20 Z`, fill: C.accent }, layer);
      return v < 0.12 ? 'Topo das nuvens de Júpiter: muito frio. Não há chão para pousar.'
        : v < 0.15 ? 'Nível de 1 bar: a mesma pressão do ar ao nível do mar na Terra. É o nível de referência usado para os valores do catálogo; a posição dele no desenho é esquemática. Ainda é só gás.'
        : v < 0.75 ? 'O gás fica cada vez mais denso e quente até virar líquido, sem nenhuma superfície no meio do caminho.'
        : 'Lá no fundo, a pressão é de milhões de vezes a da Terra. O hidrogênio conduz eletricidade como metal. O núcleo ainda é estudado (valores aproximados).';
    }
  };
};

const COMET_ORBIT = { a: 190, e: 0.8, cx: 260, cy: 135 };
/** Posição e tangente na elipse; a fase cresce uniformemente no tempo. */
export function cometPosition(f: number): [number, number, number, number] {
  const { a, e, cx, cy } = COMET_ORBIT;
  const b = a * Math.sqrt(1 - e * e);
  const M = (((f % 1) + 1) % 1) * Math.PI * 2;
  let E = M;
  for (let i = 0; i < 8; i++) E -= (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
  // O Sol desenhado está no foco esquerdo (cx − ae): E = 0 é o periélio.
  return [cx - a * Math.cos(E), cy + b * Math.sin(E), a * Math.sin(E), b * Math.cos(E)];
}
const cometa = (): Scene => {
  let layer: SVGGElement;
  const { a, e, cx: cxE, cy } = COMET_ORBIT;
  const b = a * Math.sqrt(1 - e * e), sunX = cxE - a * e;
  const pos = cometPosition;
  return {
    init(svg) { layer = g(svg); },
    value: (v) => { const [x, y] = pos(v); const d = Math.hypot(x - sunX, y - cy); return d < 60 ? 'perto do Sol' : d < 200 ? 'a meio caminho' : 'longe do Sol'; },
    draw(v) {
      clear(layer);
      el('ellipse', { cx: cxE, cy, rx: a, ry: b, fill: 'none', stroke: C.line, 'stroke-dasharray': '4 5' }, layer);
      star(layer, sunX, cy, 12, C.gold);
      const [x, y, vx, vy] = pos(v);
      const d = Math.hypot(x - sunX, y - cy), ux = (x - sunX) / d, uy = (y - cy) / d;
      const L = clamp(9e5 / (d * d), 0, 130);
      if (L > 4) {
        el('line', { x1: x, y1: y, x2: x + ux * L, y2: y + uy * L, stroke: C.blue, 'stroke-width': 3, 'stroke-linecap': 'round', opacity: 0.8 }, layer);
        const vn = Math.hypot(vx, vy), lx = -vx / vn, ly = -vy / vn;
        el('path', { d: `M${x} ${y} Q${x + ux * L * 0.6} ${y + uy * L * 0.6} ${x + (ux * 0.75 + lx * 0.35) * L} ${y + (uy * 0.75 + ly * 0.35) * L}`, fill: 'none', stroke: C.gold, 'stroke-width': 5, opacity: 0.6, 'stroke-linecap': 'round' }, layer);
      }
      el('circle', { cx: x, cy: y, r: 5, fill: C.ink }, layer);
      text(layer, 20, 250, 'azul: cauda de gás · dourado: cauda de poeira', { class: 'mx-t small' });
      return L <= 4 ? 'Longe do Sol, o cometa é só um bloco de gelo e poeira, sem cauda.'
        : 'Perto do Sol, o gelo vira gás e solta poeira. A luz e o vento do Sol empurram tudo para longe dele: a cauda de gás aponta direto para fora, a de poeira faz uma curva. Repare que, quando o cometa se afasta, a cauda vai na frente.';
    }
  };
};

/** Órbita por integração numérica simples (salto de rã), só o Sol puxando. */
export const ORBIT_DRAWN_CENTRAL_RADIUS=.14;
export interface OrbitPath { pts:[number,number][]; times:number[]; kind:'cai'|'orbita'|'escapa'|'longe' }
export function trajectory(v: number): OrbitPath {
  if(!Number.isFinite(v)||v<0)throw new RangeError('Velocidade inválida.');
  let x = 1, y = 0, vx = 0, vy = v;
  const pts: [number, number][] = [[x, y]];
  const times=[0];let elapsed=0; let ang = 0, prevA = 0;
  for (let i = 0; i < 6000; i++) {
    const r = Math.hypot(x, y), dt = 0.004 * Math.max(0.2, r) ** 1.5;
    const ax = -x / r ** 3, ay = -y / r ** 3;
    vx += ax * dt / 2; vy += ay * dt / 2; x += vx * dt; y += vy * dt;
    const r2 = Math.hypot(x, y); vx += (-x / r2 ** 3) * dt / 2; vy += (-y / r2 ** 3) * dt / 2;
    elapsed+=dt; if (i % 3 === 0) {pts.push([x, y]);times.push(elapsed);}
    const a = Math.atan2(y, x); let da = a - prevA; if (da < -Math.PI) da += 2 * Math.PI; if (da > Math.PI) da -= 2 * Math.PI; ang += da; prevA = a;
    if (r2 < ORBIT_DRAWN_CENTRAL_RADIUS) { pts.push([x, y]);times.push(elapsed); return { pts,times, kind: 'cai' }; }
    if (r2 > 3.4) return { pts,times, kind: v * v >= 2 ? 'escapa' : 'longe' };
    if (Math.abs(ang) >= Math.PI * 2) { pts.push(pts[0]);times.push(elapsed); return { pts,times, kind: 'orbita' }; }
  }
  return { pts,times, kind: 'orbita' };
}
/** Interpola por tempo acumulado, preservando aceleração na elipse. */
export function trajectoryAt(path:OrbitPath,phase:number):{position:[number,number];index:number}{
 const time=Math.max(0,Math.min(1,Number.isFinite(phase)?phase:0))*path.times.at(-1)!;
 let lo=0,hi=path.times.length-1;while(hi-lo>1){const mid=(lo+hi)>>1;if(path.times[mid]<time)lo=mid;else hi=mid;}
 const k=(time-path.times[lo])/(path.times[hi]-path.times[lo]||1),a=path.pts[lo],b=path.pts[hi];
 return {position:[a[0]+(b[0]-a[0])*k,a[1]+(b[1]-a[1])*k],index:lo};
}
const orbitas = (): Scene => {
  let layer: SVGGElement;
  let cacheV = -1, cache = trajectory(0.5);
  const S = 72, cx = 270, cy = 135;
  const P = ([x, y]: [number, number]): [number, number] => [cx + x * S, cy - y * S];
  return {
    animate: 'time',
    duration: 3200,
    init(svg) { layer = g(svg); },
    value: (v) => (v === 0 ? 'parado' : `${fmt(v, 2)} × a velocidade de círculo`),
    draw(v, t) {
      if (v !== cacheV) { cache = trajectory(v); cacheV = v; }
      clear(layer);
      star(layer, cx, cy, 10, C.gold);
      text(layer, cx, cy + 30, 'Sol', { class: 'mx-t small', 'text-anchor': 'middle' });
      const pts = cache.pts.map(P);
      el('polyline', { points: pts.map((p) => p.join(',')).join(' '), fill: 'none', stroke: C.line, 'stroke-width': 2, 'stroke-dasharray': '4 4' }, layer);
      const sample=trajectoryAt(cache,t);const n=sample.index;
      el('polyline', { points: pts.slice(0, n + 1).concat([P(sample.position)]).map((p) => p.join(',')).join(' '), fill: 'none', stroke: C.accent, 'stroke-width': 2.5 }, layer);
      const [bx, by] = P(sample.position), [px, py] = pts[Math.max(0, n - 1)];
      // vetores: velocidade (direção do movimento) e gravidade (sempre para o Sol)
      const dvx = bx - px || 0, dvy = by - py || (n === 1 ? -1 : 0), dl = Math.hypot(dvx, dvy) || 1;
      if (v > 0.01) arrow(layer, bx, by, bx + (dvx / dl) * 40 * Math.max(0.4, v), by + (dvy / dl) * 40 * Math.max(0.4, v), C.blue, 2.2);
      const gx = cx - bx, gy = cy - by, gl = Math.hypot(gx, gy) || 1;
      arrow(layer, bx, by, bx + (gx / gl) * 32, by + (gy / gl) * 32, C.accent, 2.2);
      el('circle', { cx: bx, cy: by, r: 7, fill: C.ink }, layer);
      text(layer, 14, 24, 'azul: movimento · vermelho: gravidade', { class: 'mx-t small' });
      const [sx, sy] = P([1, 0]); text(layer, sx + 10, sy + 22, 'lançamento', { class: 'mx-t small' });
      const kind = cache.kind;
      return v < 0.02 ? 'Sem velocidade lateral, o corpo cai até o limite central ampliado do desenho.'
        : kind === 'cai' ? 'Neste modelo, a trajetória cruza o limite central ampliado. Isso não indica uma colisão com o Sol em uma órbita real.'
        : kind === 'orbita' && Math.abs(v - 1) < 0.04 ? 'Na velocidade certa, ele cai na direção do Sol o tempo todo e erra o Sol o tempo todo: uma órbita quase circular. Nenhum motor empurra para frente.'
        : kind === 'orbita' ? `Órbita elíptica: ${v < 1 ? 'mais lento que o de círculo, ele se aproxima do Sol, acelera e volta' : 'mais rápido que o de círculo, ele se afasta, perde velocidade e volta'}. A gravidade sempre aponta para o Sol.`
        : kind === 'longe' ? 'Rápido: a órbita fica tão alongada que sai do desenho, mas ainda volta um dia.'
        : 'Rápido demais (mais de 1,41 vez a de círculo): a gravidade não consegue trazê-lo de volta. Ele escapa.';
    }
  };
};

const comparar = (): Scene => {
  let layer: SVGGElement;
  const earth=planets.find(p=>p.id==='terra')!;
  const density=[5.51,1.33,.69],colors=['#3d7cc9','#d9b27a','#e8cf9a'];
  const P=['terra','jupiter','saturno'].map((id,i)=>{const p=planets.find(p=>p.id===id)!;return {n:p.name,r:p.radius,m:p.mass/earth.mass,d:density[i],g:p.gravity,col:colors[i]};});

  const props = [
    { k: 'r' as const, max: 75000, f: (x: number) => `${fmt(x)} km`, cap: 'Raio (no equador): Júpiter é 11 vezes maior que a Terra. Saturno, quase 10.' },
    { k: 'm' as const, max: 330, f: (x: number) => `${fmt(x)} Terras`, cap: 'Massa: Júpiter tem 318 vezes a massa da Terra; Saturno, 95.' },
    { k: 'd' as const, max: 6, f: (x: number) => `${fmt(x, 2)} g/cm³`, cap: 'Densidade: a Terra é rocha e metal, a mais densa. Saturno é menos denso que a água (1 g/cm³).' },
    { k: 'g' as const, max: 26, f: (x: number) => `${fmt(x, 1)} m/s²`, cap: 'Gravidade equatorial efetiva, incluindo rotação (gigantes no nível de 1 bar): Saturno, com 95 vezes a massa, tem gravidade parecida com a da Terra, porque a massa está espalhada num raio enorme.' }
  ];
  return {
    duration: 900,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const pr = props[v], k = ease(t);
      P.forEach((p, i) => {
        const y = 50 + i * 70;
        el('circle', { cx: 40, cy: y + 4, r: 6 + 20 * Math.sqrt(p.r / 72000), fill: p.col }, layer);
        bar(layer, 90, y, 270, pr.max, p[pr.k] * k, p.n, pr.f(p[pr.k]), [C.blue, C.accent, C.gold][i]);
      });
      return pr.cap;
    }
  };
};

export const scenes: SceneMap = {
  'sistema-solar-disco': disco,
  'sistema-solar-sol-e-planetas': rochosos,
  'sistema-solar-gigantes': gigantes,
  'sistema-solar-pequenos-corpos': cometa,
  'sistema-solar-orbitas': orbitas,
  'sistema-solar-medindo-mundos': comparar
};

