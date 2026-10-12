import type { Scene, SceneMap } from './engine';
import { C, arrow, clear, ease, el, g, lerp, rng, star, text } from './draw';

const colapso = (): Scene => {
  let layer: SVGGElement;
  const rnd = rng(19);
  const parts = Array.from({ length: 150 }, () => { const a = rnd() * Math.PI * 2, r = Math.sqrt(rnd()); return [a, r] as [number, number]; });
  const R = [115, 70, 30, 22];
  const temps: [string, string][] = [['−260 °C', 'muito fria'], ['milhares de °C', 'no centro'], ['~1 milhão °C', 'no centro'], ['~10 milhões °C', 'fusão começa']];
  const caps = [
    'Uma nuvem fria de gás e poeira. Se uma parte fica densa o bastante, a gravidade começa a vencer.',
    'A nuvem encolhe. Apertado, o gás esquenta, como o ar numa bomba de bicicleta.',
    'Uma protoestrela: brilha pelo calor da contração, ainda sem fusão estável. A rotação achata o resto em um disco.',
    'O centro passa de 10 milhões °C: a fusão de hidrogênio começa e segura a contração. Nasceu uma estrela.'
  ];
  return {
    duration: 1500,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const k = ease(t), from = R[Math.max(0, v - 1)], to = R[v], rad = v === 0 ? R[0] : lerp(from, to, k);
      const cx = 170, cy = 128;
      if (v >= 2) el('ellipse', { cx, cy, rx: v === 2 ? lerp(30, 110, k) : 110, ry: v === 2 ? lerp(10, 14, k) : 14, fill: C.accent, opacity: 0.2 }, layer);
      for (const [a, r] of parts) el('circle', { cx: cx + Math.cos(a) * r * rad, cy: cy + Math.sin(a) * r * rad * (v >= 2 ? 0.25 : 1), r: 1.8, fill: C.ink2, opacity: v >= 2 ? 0.25 : 0.6 }, layer);
      if (v >= 1) star(layer, cx, cy, v === 1 ? 6 * k : v === 2 ? 12 : 16, v === 3 ? '#fff0b0' : v === 2 ? '#e06a3a' : '#a5402a');
      el('rect', { x: 330, y: 40, width: 140, height: 80, rx: 10, fill: C.surface, stroke: C.line }, layer);
      text(layer, 340, 62, 'temperatura', { class: 'mx-t small' });
      text(layer, 340, 86, temps[v][0], { class: 'mx-t strong warm' });
      text(layer, 340, 106, temps[v][1], { class: 'mx-t small' });
      if (v === 0 || v === 1) for (let i = 0; i < 6; i++) { const a = (i / 6) * Math.PI * 2; arrow(layer, cx + Math.cos(a) * (rad + 30), cy + Math.sin(a) * (rad + 30), cx + Math.cos(a) * (rad + 8), cy + Math.sin(a) * (rad + 8), C.blue, 1.6); }
      return caps[v];
    }
  };
};

const fusao = (): Scene => {
  let layer: SVGGElement;
  const start: [number, number][] = [[80, 60], [80, 190], [300, 60], [300, 190]];
  const caps = [
    'No núcleo do Sol, quatro núcleos de hidrogênio (prótons) se aproximam com muita energia.',
    'Em várias etapas, eles viram um núcleo de hélio (2 prótons e 2 nêutrons).',
    'O hélio pesa cerca de 0,7% menos que os quatro hidrogênios. Essa massa que "some" vira energia: é ela que faz o Sol brilhar.',
    'Equilíbrio: a gravidade aperta para dentro (azul); a energia da fusão empurra para fora (vermelho). Enquanto há hidrogênio, as duas se compensam.'
  ];
  return {
    duration: 1600,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const k = ease(t);
      if (v === 3) {
        star(layer, 190, 130, 60, '#ffd27a');
        for (let i = 0; i < 8; i++) { const a = (i / 8) * Math.PI * 2 + 0.2; arrow(layer, 190 + Math.cos(a) * 112, 130 + Math.sin(a) * 112, 190 + Math.cos(a) * 72, 130 + Math.sin(a) * 72, C.blue, 2.4); arrow(layer, 190 + Math.cos(a + 0.4) * 34, 130 + Math.sin(a + 0.4) * 34, 190 + Math.cos(a + 0.4) * (34 + 50 * k), 130 + Math.sin(a + 0.4) * (34 + 50 * k), C.accent, 2.4); }
        text(layer, 340, 80, 'gravidade ↘', { class: 'mx-t small strong' }); text(layer, 340, 104, 'pressão ↗', { class: 'mx-t small strong warm' });
        return caps[3];
      }
      const gather = v === 0 ? 0.25 * k : 1;
      start.forEach(([x, y], i) => { const tx = 190 + (i % 2 ? 8 : -8), ty = 125 + (i < 2 ? -8 : 8); el('circle', { cx: lerp(x, tx, gather), cy: lerp(y, ty, gather), r: 10, fill: v >= 1 && i % 2 && k > 0.5 ? C.muted : C.accent }, layer); });
      if (v === 2) {
        for (let i = 0; i < 10; i++) { const a = (i / 10) * Math.PI * 2; el('line', { x1: 190 + Math.cos(a) * 26, y1: 125 + Math.sin(a) * 26, x2: 190 + Math.cos(a) * (26 + 60 * k), y2: 125 + Math.sin(a) * (26 + 60 * k), stroke: C.gold, 'stroke-width': 3 }, layer); }
        el('rect', { x: 320, y: 70, width: 140, height: 16, fill: C.accent }, layer); text(layer, 320, 62, '4 hidrogênios', { class: 'mx-t small' });
        el('rect', { x: 320, y: 120, width: 140 * (1 - 0.007 * 20), height: 16, fill: C.muted }, layer); text(layer, 320, 112, '1 hélio', { class: 'mx-t small' });
        text(layer, 320, 156, 'diferença → energia', { class: 'mx-t small strong warm' });
        text(layer, 320, 176, '(diferença exagerada)', { class: 'mx-t small' });
      }
      return caps[v];
    }
  };
};

const sol = (): Scene => {
  let layer: SVGGElement;
  const rnd = rng(4);
  const walk: [number, number][] = [[0, 0]];
  for (let i = 0; i < 60; i++) { const [x, y] = walk[walk.length - 1]; const a = rnd() * Math.PI * 2; walk.push([x + Math.cos(a) * 9, y + Math.sin(a) * 9 - 1.1]); }
  const layers = [
    { r: 45, name: 'Núcleo', temp: '~15 milhões °C', cap: 'Núcleo: onde acontece a fusão. Cerca de 15 milhões °C.' },
    { r: 110, name: 'Zona radiativa', temp: 'milhões de °C', cap: 'Zona radiativa: a energia é rebatida de partícula em partícula, num caminho torto. Pode levar milhares de anos para atravessar.' },
    { r: 150, name: 'Zona convectiva', temp: '~2 milhões → 6 mil °C', cap: 'Zona convectiva: o gás quente sobe e o frio desce, como água fervendo numa panela.' },
    { r: 160, name: 'Superfície', temp: '~5.500 °C', cap: 'Superfície (fotosfera): a luz escapa para o espaço. A cor amarela das figuras é atribuída; visto do espaço, o Sol é quase branco.' }
  ];
  return {
    duration: 2400,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const cx = 40, cy = 135;
      [...layers].reverse().forEach((l, ri) => { const i = layers.length - 1 - ri; el('circle', { cx, cy, r: l.r, fill: ['#ffe08a', '#ffbe5c', '#ff9a3c', '#ffd27a'][i], opacity: i === v ? 1 : 0.55, stroke: i === v ? C.accent : 'none', 'stroke-width': 3 }, layer); });
      el('circle', { cx, cy, r: 45, fill: '#fff3c4' }, layer);
      if (v === 1) {
        const n = Math.max(2, Math.floor(walk.length * t)), pts = walk.slice(0, n).map(([x, y]) => [cx + 50 + x, cy - 10 + y]);
        el('polyline', { points: pts.map((p) => p.join(',')).join(' '), fill: 'none', stroke: C.ink, 'stroke-width': 1.5 }, layer);
      }
      if (v === 2) for (let i = 0; i < 3; i++) { const y = cy - 70 + i * 40, ph = t * Math.PI * 2 + i; el('ellipse', { cx: cx + 130, cy: y, rx: 14, ry: 18, fill: 'none', stroke: C.ink, 'stroke-width': 1.5, 'stroke-dasharray': '4 3', 'stroke-dashoffset': -ph * 10 }, layer); }
      if (v === 3) for (let i = 0; i < 5; i++) { const a = -0.9 + i * 0.45; arrow(layer, cx + Math.cos(a) * 165, cy + Math.sin(a) * 165, cx + Math.cos(a) * (165 + 40 * ease(t)), cy + Math.sin(a) * (165 + 40 * ease(t)), C.gold, 2); }
      text(layer, 300, 70, layers[v].name, { class: 'mx-t strong' });
      text(layer, 300, 96, layers[v].temp, { class: 'mx-t strong warm' });
      return layers[v].cap;
    }
  };
};

const pequenas = (): Scene => {
  let layer: SVGGElement;
  const caps = [
    'Hoje: o Sol e uma anã vermelha (um terço da massa do Sol) fundem hidrogênio tranquilamente.',
    'Daqui a uns 5 bilhões de anos: o Sol esgota o hidrogênio do núcleo e começa a inchar. A anã vermelha nem mudou.',
    'Uns 7 bilhões: o Sol vira gigante vermelha, centenas de vezes maior. A anã vermelha segue igual.',
    'Uns 8 bilhões: o Sol solta as camadas de fora (uma nebulosa) e sobra o núcleo: uma anã branca, do tamanho da Terra.',
    'Trilhões de anos: a anã branca esfriou. A anã vermelha só agora estaria terminando; esse fim é previsto, nunca observado.'
  ];
  return {
    duration: 1500,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const k = ease(t), cy = 120;
      text(layer, 140, 250, 'Sol', { class: 'mx-t strong', 'text-anchor': 'middle' });
      text(layer, 380, 250, 'anã vermelha', { class: 'mx-t strong', 'text-anchor': 'middle' });
      el('line', { x1: 260, y1: 20, x2: 260, y2: 230, stroke: C.line, 'stroke-dasharray': '4 6' }, layer);
      const sunR = [18, 22, 90, 5, 5][v], prevR = [18, 18, 22, 90, 5][v];
      const r = lerp(prevR, sunR, k);
      if (v === 3) el('circle', { cx: 140, cy, r: lerp(40, 95, k), fill: 'none', stroke: '#5fb3a8', 'stroke-width': 10, opacity: 0.4 }, layer);
      star(layer, 140, cy, r, v <= 1 ? '#ffd27a' : v === 2 ? '#e0603a' : v === 3 ? '#f4f6ff' : '#9aa3b5', v < 4);
      if (v >= 3) text(layer, 140, cy + 40, v === 3 ? 'anã branca' : 'anã branca fria (prevista)', { class: 'mx-t small', 'text-anchor': 'middle' });
      if (v < 4) star(layer, 380, cy, 9, '#ff7a4a');
      else { el('circle', { cx: 380, cy, r: 6, fill: 'none', stroke: C.ink, 'stroke-dasharray': '3 3', 'stroke-width': 2 }, layer); text(layer, 380, cy + 34, 'fim previsto', { class: 'mx-t small warm', 'text-anchor': 'middle' }); }
      return caps[v];
    }
  };
};

const massivas = (): Scene => {
  let layer: SVGGElement;
  const caps = [
    'Uma estrela massiva (dezenas de vezes o Sol) funde hidrogênio muito rápido: vive só alguns milhões de anos.',
    'Vira supergigante e funde elementos cada vez mais pesados no núcleo, em camadas, até chegar ao ferro.',
    'Fundir ferro não libera energia. Sem sustentação, o núcleo colapsa em uma fração de segundo.',
    'Daí em diante o caminho se divide. Pode haver uma supernova e sobrar uma estrela de nêutrons; ou formar-se um buraco negro, às vezes quase sem explosão. Não há um corte exato de massa.'
  ];
  return {
    duration: 1500,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const k = ease(t), cx = 90, cy = 125;
      if (v === 0) star(layer, cx, cy, 26, '#b7d2ff');
      if (v === 1) { star(layer, cx, cy, lerp(26, 70, k), '#ff8a5a'); ['#ffd27a', '#e8c93a', '#c9a46a', '#8a8a8a'].forEach((c, i) => el('circle', { cx, cy, r: 30 - i * 7, fill: c }, layer)); }
      if (v === 2) { star(layer, cx, cy, lerp(70, 14, k), '#ffd9a0'); for (let i = 0; i < 8; i++) { const a = (i / 8) * Math.PI * 2; arrow(layer, cx + Math.cos(a) * 60, cy + Math.sin(a) * 60, cx + Math.cos(a) * 24, cy + Math.sin(a) * 24, C.blue, 2); } }
      if (v === 3) { for (let i = 0; i < 14; i++) { const a = (i / 14) * Math.PI * 2; el('line', { x1: cx, y1: cy, x2: cx + Math.cos(a) * 80 * k, y2: cy + Math.sin(a) * 80 * k, stroke: C.gold, 'stroke-width': 2, 'stroke-dasharray': '4 4' }, layer); } star(layer, cx, cy, 8, '#fff'); }
      // árvore de caminhos
      const nodes = [['Sequência principal', 30], ['Supergigante', 80], ['Núcleo colapsa', 130]] as const;
      nodes.forEach(([n, y], i) => { el('rect', { x: 230, y: y - 16, width: 150, height: 28, rx: 14, fill: i <= v ? C.surface : C.soft, stroke: i === v ? C.accent : C.line, 'stroke-width': i === v ? 2.5 : 1 }, layer); text(layer, 305, y + 3, n, { class: 'mx-t small strong', 'text-anchor': 'middle' }); if (i < 2) el('line', { x1: 305, y1: y + 12, x2: 305, y2: y + 34, stroke: C.line, 'stroke-width': 2 }, layer); });
      if (v === 3) {
        el('path', { d: 'M305 142 L250 186 M305 142 L400 186', stroke: C.accent, 'stroke-width': 2, 'stroke-dasharray': '5 4', fill: 'none' }, layer);
        text(layer, 250, 206, 'pode: supernova +', { class: 'mx-t small warm', 'text-anchor': 'middle' });
        text(layer, 250, 224, 'estrela de nêutrons', { class: 'mx-t small strong', 'text-anchor': 'middle' });
        text(layer, 400, 206, 'pode: buraco negro', { class: 'mx-t small warm', 'text-anchor': 'middle' });
        text(layer, 400, 224, '(com ou sem explosão)', { class: 'mx-t small', 'text-anchor': 'middle' });
      }
      return caps[v];
    }
  };
};

const elementos = (): Scene => {
  let layer: SVGGElement;
  const els = ['H', 'C', 'O', 'Fe', 'Au'];
  const sources = ['Big Bang', 'Estrelas como o Sol', 'Estrelas massivas', 'Supernovas', 'Colisões de estrelas de nêutrons'];
  const map: number[][] = [[0], [1, 2], [2, 3], [3, 2], [4, 3]];
  const caps = [
    'Hidrogênio: quase todo veio do Big Bang. Está na água do seu corpo.',
    'Carbono: feito no fim da vida de estrelas como o Sol e em estrelas massivas, e espalhado por ventos e nebulosas.',
    'Oxigênio: feito principalmente em estrelas massivas e espalhado quando elas explodem.',
    'Ferro: grande parte vem de supernovas, incluindo explosões de anãs brancas em sistemas duplos.',
    'Ouro: parte importante vem de colisões de estrelas de nêutrons, eventos raros. Supernovas especiais também podem contribuir.'
  ];
  return {
    duration: 1300,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const k = ease(t);
      els.forEach((e, i) => { const x = 30, y = 22 + i * 46; el('rect', { x, y, width: 52, height: 40, rx: 8, fill: i === v ? C.accent : C.surface, stroke: C.line }, layer); text(layer, x + 26, y + 27, e, { class: `mx-t strong${i === v ? ' on-accent' : ''}`, 'text-anchor': 'middle' }); });
      sources.forEach((s, i) => { const y = 30 + i * 46, on = map[v].includes(i); el('rect', { x: 250, y: y - 18, width: 220, height: 32, rx: 16, fill: on ? C.surface : C.soft, stroke: on ? C.accent : C.line, 'stroke-width': on ? 2 : 1, opacity: on ? 1 : 0.6 }, layer); text(layer, 262, y + 3, s, { class: `mx-t small${on ? ' strong' : ''}` });
        if (on) { const y0 = 42 + v * 46; const p = el('path', { d: `M82 ${y0} C170 ${y0} 170 ${y} 248 ${y}`, fill: 'none', stroke: C.accent, 'stroke-width': map[v][0] === i ? 3 : 1.6, pathLength: 1, 'stroke-dasharray': 1, 'stroke-dashoffset': 1 - k }, layer); void p; } });
      return caps[v];
    }
  };
};

export const scenes: SceneMap = {
  'vida-das-estrelas-colapso': colapso,
  'vida-das-estrelas-fusao': fusao,
  'vida-das-estrelas-sol': sol,
  'vida-das-estrelas-pequenas-e-medias': pequenas,
  'vida-das-estrelas-massivas': massivas,
  'vida-das-estrelas-elementos': elementos
};
