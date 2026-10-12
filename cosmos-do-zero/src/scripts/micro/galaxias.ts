import type { Scene, SceneMap } from './engine';
import { C, H, W, arrow, clamp, clear, ease, el, g, lerp, rng, star, text } from './draw';

/** Pontos de uma espiral de dois braços (forma de galáxia), determinísticos. */
function spiral(seed: number, n: number, cx: number, cy: number, r: number, tilt = 0.55): [number, number, number][] {
  const rnd = rng(seed), pts: [number, number, number][] = [];
  for (let i = 0; i < n; i++) {
    const arm = i % 2, k = rnd(), ang = arm * Math.PI + k * 3.6 + (rnd() - 0.5) * 0.5, rr = r * (0.12 + k * 0.88) + (rnd() - 0.5) * 8;
    pts.push([cx + Math.cos(ang) * rr, cy + Math.sin(ang) * rr * tilt, 0.6 + rnd() * 1.4]);
  }
  return pts;
}

const viaLactea = (): Scene => {
  let layer: SVGGElement, ruler: SVGTextElement;
  const levels = [
    { ruler: 'Diâmetro: 12.700 km · a luz cruza em 0,04 s', cap: 'Terra: o planeta onde você está. Tudo o que vem a seguir a contém.' },
    { ruler: 'Até Netuno: 4,5 bilhões de km · a luz leva 4 horas', cap: 'Sistema Solar: o Sol e tudo o que gira em volta dele. A Terra virou um ponto na terceira órbita.' },
    { ruler: 'Diâmetro: uns 100 mil anos-luz', cap: 'Via Láctea: centenas de bilhões de estrelas. O Sol fica num braço, a uns 26 mil anos-luz do centro, não no meio.' },
    { ruler: 'Uns 10 milhões de anos-luz', cap: 'Grupo Local: a Via Láctea, Andrômeda e dezenas de galáxias pequenas, presas pela gravidade.' },
    { ruler: 'Bilhões de anos-luz', cap: 'Teia cósmica: grupos e aglomerados de galáxias ao longo de filamentos. O Grupo Local é um ponto num desses fios.' }
  ];
  const here = (p: Element, x: number, y: number, label: string, right = true) => {
    el('circle', { cx: x, cy: y, r: 9, fill: 'none', stroke: C.accent, 'stroke-width': 2.5 }, p);
    el('line', { x1: x + (right ? 9 : -9), y1: y - 6, x2: x + (right ? 40 : -40), y2: y - 30, stroke: C.accent, 'stroke-width': 1.5 }, p);
    text(p, x + (right ? 44 : -44), y - 32, label, { class: 'mx-t strong warm', 'text-anchor': right ? 'start' : 'end' });
  };
  return {
    duration: 1500,
    init(svg) { layer = g(svg); ruler = text(svg, W / 2, H - 12, '', { class: 'mx-t', 'text-anchor': 'middle' }); },
    draw(v, t) {
      clear(layer);
      const s = lerp(3, 1, ease(t));
      const inner = g(layer, { transform: `translate(${W / 2} 125) scale(${s}) translate(${-W / 2} -125)`, opacity: clamp(t * 2) });
      if (v === 0) {
        el('circle', { cx: W / 2, cy: 125, r: 88, fill: C.blue }, inner);
        el('path', { d: 'M200 90 q30 -25 60 0 t50 30 q-20 30 -60 20 t-50 -50 Z M250 170 q30 10 40 -15 q20 15 0 35 q-30 10 -40 -20 Z', fill: C.gold, opacity: 0.85 }, inner);
        text(inner, W / 2, 238, 'você está aqui', { class: 'mx-t strong warm', 'text-anchor': 'middle' });
      } else if (v === 1) {
        star(inner, W / 2, 125, 12, C.gold);
        [30, 45, 62, 80, 112, 150, 185, 215].forEach((r) => el('ellipse', { cx: W / 2, cy: 125, rx: r, ry: r * 0.42, fill: 'none', stroke: C.line, 'stroke-width': 1 }, inner));
        el('circle', { cx: W / 2 + 62, cy: 125, r: 3.5, fill: C.blue }, inner);
        here(inner, W / 2 + 62, 125, 'Terra', true);
      } else if (v === 2) {
        el('ellipse', { cx: W / 2, cy: 125, rx: 26, ry: 13, fill: C.gold, opacity: 0.55 }, inner);
        for (const [x, y, r] of spiral(7, 520, W / 2, 125, 190)) el('circle', { cx: x, cy: y, r, fill: C.ink2, opacity: 0.55 }, inner);
        here(inner, W / 2 + 112, 152, 'Sol', true);
      } else if (v === 3) {
        const gal = (x: number, y: number, r: number, name: string, seed: number) => {
          for (const [px, py, pr] of spiral(seed, 90, x, y, r, 0.5)) el('circle', { cx: px, cy: py, r: pr * 0.7, fill: C.ink2, opacity: 0.6 }, inner);
          text(inner, x, y + r * 0.5 + 18, name, { class: 'mx-t small', 'text-anchor': 'middle' });
        };
        gal(165, 120, 48, 'Via Láctea', 3); gal(330, 95, 58, 'Andrômeda', 5); gal(300, 185, 22, 'Triângulo', 9);
        const rnd = rng(11); for (let i = 0; i < 26; i++) el('circle', { cx: 60 + rnd() * 360, cy: 30 + rnd() * 190, r: 1.6, fill: C.muted }, inner);
        here(inner, 165, 120, 'nós', false);
      } else {
        const rnd = rng(21), nodes: [number, number][] = [];
        for (let i = 0; i < 14; i++) nodes.push([30 + rnd() * 420, 20 + rnd() * 200]);
        nodes.forEach(([x, y], i) => nodes.slice(i + 1).forEach(([x2, y2]) => { if (Math.hypot(x2 - x, y2 - y) < 130) for (let k = 0; k < 18; k++) { const f = rnd(); el('circle', { cx: lerp(x, x2, f) + (rnd() - 0.5) * 8, cy: lerp(y, y2, f) + (rnd() - 0.5) * 8, r: 1.2, fill: C.ink2, opacity: 0.6 }, inner); } }));
        nodes.forEach(([x, y]) => el('circle', { cx: x, cy: y, r: 4, fill: C.accent, opacity: 0.7 }, inner));
        here(inner, nodes[3][0], nodes[3][1], 'Grupo Local', nodes[3][0] < 300);
      }
      ruler.textContent = levels[v].ruler;
      return `Degrau ${v + 1} de 5. ${levels[v].cap}`;
    }
  };
};

const tipos = (): Scene => {
  let layer: SVGGElement;
  const caps = [
    'Estrelas: centenas de bilhões, num disco com braços espirais.',
    'Gás e poeira ficam no disco; é deles que nascem novas estrelas. As faixas escuras são poeira.',
    'A gravidade das estrelas, gás e poeira não basta para o jeito como a galáxia gira: inferimos um halo de massa invisível em volta.',
    'Uma galáxia elíptica: estrelas mais velhas, pouco gás, sem braços. Espirais e elípticas são famílias diferentes; uma não é fase obrigatória da outra.'
  ];
  return {
    duration: 1300,
    init(svg) {
      const defs = el('defs', {}, svg);
      const rg = el('radialGradient', { id: 'mx-halo' }, defs);
      el('stop', { offset: 0, 'stop-color': C.dm, 'stop-opacity': 0.35 }, rg);
      el('stop', { offset: 1, 'stop-color': C.dm, 'stop-opacity': 0 }, rg);
      layer = g(svg);
    },
    draw(v, t) {
      clear(layer);
      const k = ease(t);
      if (v === 3) {
        for (let i = 0; i < 380; i++) { const r = rng(i + 3); const a = r() * Math.PI * 2, d = Math.pow(r(), 1.6) * 110; el('circle', { cx: W / 2 + Math.cos(a) * d * 1.4, cy: 128 + Math.sin(a) * d * 0.85, r: 1, fill: C.gold, opacity: 0.75 * k + 0.1 }, layer); }
        el('ellipse', { cx: W / 2, cy: 128, rx: 40, ry: 26, fill: C.gold, opacity: 0.35 }, layer);
        return caps[3];
      }
      if (v >= 2) el('ellipse', { cx: W / 2, cy: 128, rx: 230, ry: 125, fill: 'url(#mx-halo)', opacity: v === 2 ? k : 1 }, layer);
      el('ellipse', { cx: W / 2, cy: 128, rx: 22, ry: 11, fill: C.gold, opacity: 0.7 }, layer);
      for (const [x, y, r] of spiral(4, 600, W / 2, 128, 170, 0.45)) el('circle', { cx: x, cy: y, r: r * 0.8, fill: C.ink2, opacity: 0.6 }, layer);
      if (v >= 1) for (const [x, y] of spiral(8, 120, W / 2, 128, 160, 0.45)) el('circle', { cx: x + 4, cy: y + 2, r: 4, fill: C.accent, opacity: 0.25 * (v === 1 ? k : 1) }, layer);
      if (v >= 2) text(layer, W / 2 + 150, 30, 'halo inferido', { class: 'mx-t small' });
      if (v >= 1) text(layer, 20, 30, 'gás e poeira', { class: 'mx-t small warm' });
      return caps[v];
    }
  };
};

const teia = (): Scene => {
  let layer: SVGGElement;
  const rnd = rng(42);
  const nodes: [number, number][] = [[70, 60], [200, 40], [330, 80], [430, 50], [110, 190], [250, 150], [390, 200], [180, 240], [460, 140]];
  const links = [[0, 1], [1, 2], [2, 3], [0, 4], [1, 5], [2, 5], [5, 6], [4, 5], [4, 7], [5, 7], [6, 8], [3, 8], [2, 8]];
  const pts = Array.from({ length: 340 }, () => {
    const start: [number, number] = [rnd() * W, rnd() * (H - 30)];
    let end: [number, number];
    if (rnd() < 0.3) { const n = nodes[Math.floor(rnd() * nodes.length)]; end = [n[0] + (rnd() - 0.5) * 18, n[1] + (rnd() - 0.5) * 18]; }
    else { const [a, b] = links[Math.floor(rnd() * links.length)]; const f = rnd(); end = [lerp(nodes[a][0], nodes[b][0], f) + (rnd() - 0.5) * 10, lerp(nodes[a][1], nodes[b][1], f) + (rnd() - 0.5) * 10]; }
    return { start, end };
  });
  return {
    init(svg) { layer = g(svg); },
    value: (v) => (v < 0.05 ? 'quase liso' : v < 0.95 ? `${Math.round(v * 100)}%` : 'teia formada'),
    draw(v) {
      clear(layer);
      const k = 1 - (1 - v) ** 2;
      for (const p of pts) el('circle', { cx: lerp(p.start[0], p.end[0], k), cy: lerp(p.start[1], p.end[1], k), r: 1.7, fill: C.ink2, opacity: 0.75 }, layer);
      if (v > 0.9) {
        text(layer, 300, 250, 'vazio', { class: 'mx-t strong warm' });
        text(layer, nodes[5][0] + 12, nodes[5][1] - 10, 'aglomerado', { class: 'mx-t strong warm' });
        text(layer, 120, 118, 'filamento', { class: 'mx-t strong warm', transform: 'rotate(68 120 118)' });
      }
      text(layer, 8, H - 8, 'simulação esquemática', { class: 'mx-t small' });
      return v < 0.1 ? 'No começo, a matéria estava quase uniforme, com diferenças minúsculas.'
        : v < 0.9 ? 'Regiões um pouco mais densas puxam mais matéria. As diferenças crescem e aparecem fios e nós.'
        : 'Pronto: aglomerados (nós), filamentos (fios) e vazios (regiões com poucas galáxias). É o padrão que os mapas de galáxias mostram.';
    }
  };
};

const nebulosas = (): Scene => {
  let layer: SVGGElement;
  const cloud = (p: Element, x: number, y: number, fill: string, op: number) => {
    const r = rng(5);
    p = g(p, { filter: 'url(#mx-blur)' });
    for (let i = 0; i < 14; i++) el('circle', { cx: x + (r() - 0.5) * 120, cy: y + (r() - 0.5) * 70, r: 24 + r() * 22, fill, opacity: op }, p);
  };
  const eye = (p: Element, x: number, y: number) => { el('ellipse', { cx: x, cy: y, rx: 16, ry: 9, fill: 'none', stroke: C.ink, 'stroke-width': 2 }, p); el('circle', { cx: x, cy: y, r: 4, fill: C.ink }, p); text(p, x, y + 28, 'você', { class: 'mx-t small', 'text-anchor': 'middle' }); };
  return {
    duration: 2200,
    init(svg) { const f = el('filter', { id: 'mx-blur', x: '-30%', y: '-30%', width: '160%', height: '160%' }, el('defs', {}, svg)); el('feGaussianBlur', { stdDeviation: 10 }, f); layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const k = ease(t);
      if (v === 0) {
        cloud(layer, 200, 120, '#d24b5a', 0.12 + 0.2 * k);
        star(layer, 200, 120, 10, '#9fc3ff');
        for (let i = 0; i < 8; i++) { const a = (i / 8) * Math.PI * 2; arrow(layer, 200 + Math.cos(a) * 16, 120 + Math.sin(a) * 16, 200 + Math.cos(a) * (16 + 50 * k), 120 + Math.sin(a) * (16 + 50 * k), '#7a3bd6', 1.5); }
        eye(layer, 430, 130);
        if (k > 0.6) arrow(layer, 280, 125, 405, 130, '#d24b5a', 2);
        return 'Emissão: a estrela muito quente solta luz ultravioleta, que energiza o gás. O gás passa a brilhar com cores próprias (muito do vermelho vem do hidrogênio).';
      }
      if (v === 1) {
        cloud(layer, 240, 80, C.blue, 0.1 + 0.18 * k);
        star(layer, 110, 190, 9, '#fff2c8');
        arrow(layer, 120, 182, lerp(120, 220, k), lerp(182, 95, k), C.gold, 2);
        if (k > 0.5) arrow(layer, 250, 95, lerp(250, 405, (k - 0.5) * 2), lerp(95, 128, (k - 0.5) * 2), C.blue, 2);
        eye(layer, 430, 130);
        return 'Reflexão: a poeira não brilha sozinha; ela rebate a luz de uma estrela próxima. A luz azul é rebatida com mais facilidade, por isso essas nuvens costumam parecer azuladas.';
      }
      const r = rng(17);
      for (let i = 0; i < 70; i++) { const x = 20 + r() * 300, y = 15 + r() * 225; const hidden = Math.hypot((x - 180) / 1.4, y - 125) < 75; el('circle', { cx: x, cy: y, r: 1.8, fill: C.ink2, opacity: hidden ? 0.9 * (1 - k) : 0.85 }, layer); }
      cloud(layer, 180, 125, '#2a1e18', 0.1 + 0.55 * k);
      eye(layer, 430, 130);
      return 'Escura (absorção): uma nuvem densa de poeira fica entre você e estrelas de fundo e bloqueia a luz delas. No céu, aparece uma mancha sem estrelas.';
    }
  };
};

const luz = (): Scene => {
  let layer: SVGGElement;
  const src = [
    { name: 'Lua', from: 'da Lua', time: '1,3 segundo', clock: '12:00:01', note: 'Você vê a Lua como ela era há pouco mais de 1 segundo.' },
    { name: 'Sol', from: 'do Sol', time: '8 minutos e 20 segundos', clock: '12:08', note: 'Você vê o Sol como ele era há 8 minutos. Se ele sumisse agora, você só saberia 8 minutos depois.' },
    { name: 'Proxima Centauri', from: 'de Proxima Centauri', time: '4,2 anos', clock: 'daqui a 4,2 anos', note: 'A estrela mais próxima depois do Sol: a luz que chega hoje saiu há mais de 4 anos.' }
  ];
  return {
    duration: 2600,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const s = src[v], k = t;
      const x0 = 70, x1 = 410, y = 120;
      if (v === 0) el('circle', { cx: x0, cy: y, r: 22, fill: C.muted }, layer); else if (v === 1) star(layer, x0, y, 24, C.gold); else star(layer, x0, y, 10, '#ff9a6a');
      el('circle', { cx: x1, cy: y, r: 16, fill: C.blue }, layer);
      text(layer, x0, y + 52, s.name, { class: 'mx-t strong', 'text-anchor': 'middle' });
      text(layer, x1, y + 52, 'Terra', { class: 'mx-t strong', 'text-anchor': 'middle' });
      el('line', { x1: x0 + 30, y1: y, x2: x1 - 22, y2: y, stroke: C.line, 'stroke-dasharray': '4 6' }, layer);
      const px = lerp(x0 + 30, x1 - 22, k);
      el('circle', { cx: px, cy: y, r: 7, fill: C.accent }, layer);
      el('circle', { cx: px, cy: y, r: 14, fill: C.accent, opacity: 0.2 }, layer);
      // relógios de saída e chegada
      text(layer, x0, 40, 'saiu às 12:00', { class: 'mx-t small', 'text-anchor': 'middle' });
      text(layer, 470, 40, k >= 1 ? `chegou: ${s.clock}` : 'chegando…', { class: 'mx-t small strong warm', 'text-anchor': 'end' });
      text(layer, W / 2, 230, `Viagem da luz: ${s.time}`, { class: 'mx-t strong', 'text-anchor': 'middle' });
      return k < 1 ? `A luz saiu ${s.from} e ainda está a caminho.` : `${s.note} Distância e tempo de viagem são coisas diferentes, mas andam juntas.`;
    }
  };
};

const horizonte = (): Scene => {
  let layer: SVGGElement;
  const rnd = rng(77);
  const gals = Array.from({ length: 70 }, () => [rnd() * W, rnd() * H] as [number, number]);
  const obs: [number, number][] = [[200, 135], [330, 140], [210, 60]];
  return {
    duration: 1400,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const prev = obs[(v + obs.length - 1) % obs.length], cur = obs[v], k = t >= 1 ? 1 : ease(t);
      const cx = lerp(prev[0], cur[0], k), cy = lerp(prev[1], cur[1], k), R = 95;
      el('circle', { cx, cy, r: R, fill: C.accent, opacity: 0.08 }, layer);
      el('circle', { cx, cy, r: R, fill: 'none', stroke: C.accent, 'stroke-width': 2, 'stroke-dasharray': '6 5' }, layer);
      for (const [x, y] of gals) { const inside = Math.hypot(x - cx, y - cy) < R; el('ellipse', { cx: x, cy: y, rx: 4, ry: 2.4, fill: inside ? C.ink : C.muted, opacity: inside ? 0.9 : 0.4 }, layer); }
      el('circle', { cx, cy, r: 7, fill: C.accent }, layer);
      text(layer, cx, cy - 14, 'observador', { class: 'mx-t small strong warm', 'text-anchor': 'middle' });
      text(layer, cx + R * 0.72, cy + R * 0.72 + 16, 'horizonte', { class: 'mx-t small warm' });
      return `O círculo é até onde a luz teve tempo de chegar a este observador. Galáxias fora dele continuam existindo. Mude o observador: o horizonte vai junto, porque é dele, não uma parede do Universo.`;
    }
  };
};

export const scenes: SceneMap = {
  'galaxias-e-nebulosas-via-lactea': viaLactea,
  'galaxias-e-nebulosas-tipos': tipos,
  'galaxias-e-nebulosas-teia-cosmica': teia,
  'galaxias-e-nebulosas-nebulosas': nebulosas,
  'galaxias-e-nebulosas-gas-e-estrelas': luz,
  'galaxias-e-nebulosas-centros-galacticos': horizonte
};
