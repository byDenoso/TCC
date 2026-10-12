import type { Scene, SceneMap } from './engine';
import { C, W, arrow, clear, ease, el, fmt, g, lerp, rng, star, text } from './draw';
import { vHalo, vLum, vTotal } from '../../lib/rotation';

const metodo = (): Scene => {
  let layer: SVGGElement;
  const cards = [
    { t: 'Luz chega', k: 'medida' },
    { t: 'Espectro', k: 'medida' },
    { t: 'Modelos', k: 'inferência' },
    { t: 'Conclusão', k: 'conclusão + pergunta' }
  ];
  const caps = [
    'Medida: o telescópio recebe luz de uma galáxia distante. Nada foi interpretado ainda.',
    'Medida: a luz é separada em cores (espectro). As linhas escuras aparecem fora do lugar do laboratório.',
    'Inferência: comparamos com modelos. O que melhor explica o deslocamento das linhas? O espaço ter crescido durante a viagem.',
    'Conclusão: o Universo se expande. E surge uma pergunta aberta: por que a expansão hoje acelera?'
  ];
  return {
    duration: 1200,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      cards.forEach((c, i) => {
        const x = 18 + i * 116, on = i < v ? 1 : i === v ? ease(t) : 0;
        el('rect', { x, y: 60, width: 100, height: 110, rx: 12, fill: i <= v ? C.surface : C.soft, stroke: i === v ? C.accent : C.line, 'stroke-width': i === v ? 2.5 : 1, opacity: 0.4 + 0.6 * (i <= v ? 1 : 0) }, layer);
        text(layer, x + 50, 150, c.t, { class: 'mx-t small strong', 'text-anchor': 'middle' });
        text(layer, x + 50, 196, c.k, { class: `mx-t small${c.k === 'medida' ? '' : ' warm'}`, 'text-anchor': 'middle', opacity: on });
        const cx = x + 50, cy = 100;
        if (i === 0) { el('path', { d: `M${cx - 22} ${cy + 18} L${cx + 14} ${cy - 16} L${cx + 22} ${cy - 8} L${cx - 14} ${cy + 26} Z`, fill: C.ink2 }, layer); }
        if (i === 1) { el('rect', { x: cx - 36, y: cy - 10, width: 72, height: 18, fill: C.gold, opacity: 0.6 }, layer); [-20, 2, 18].forEach((d) => el('rect', { x: cx + d, y: cy - 10, width: 3, height: 18, fill: C.ink }, layer)); }
        if (i === 2) { el('path', { d: `M${cx - 34} ${cy + 20} Q${cx} ${cy + 10} ${cx + 34} ${cy - 22}`, fill: 'none', stroke: C.blue, 'stroke-width': 2.5 }, layer); [[-24, 14], [-6, 10], [12, 0], [26, -14]].forEach(([dx, dy]) => el('circle', { cx: cx + dx, cy: cy + dy, r: 3, fill: C.accent }, layer)); }
        if (i === 3) { text(layer, cx - 10, cy + 8, '✓', { class: 'mx-t strong', 'font-size': 26, 'text-anchor': 'middle' }); text(layer, cx + 16, cy + 8, '?', { class: 'mx-t strong warm', 'font-size': 26, 'text-anchor': 'middle' }); }
        if (i < 3) arrow(layer, x + 102, 115, x + 114, 115, i < v ? C.accent : C.line, 1.5);
      });
      return caps[v];
    }
  };
};

const espectros = (): Scene => {
  let layer: SVGGElement;
  const gals = [
    { name: 'Andrômeda', exp: 0, local: -14, cap: 'Andrômeda está tão perto que a gravidade local vence: ela vem na nossa direção e a luz chega levemente azulada. Uma galáxia só, perto, não mostra a expansão.' },
    { name: 'média distância', exp: 22, local: 10, cap: 'A média distância, a expansão já aparece, mas o movimento próprio da galáxia (azul) ainda mistura o sinal. Daí a necessidade de muitas galáxias.' },
    { name: 'muito distante', exp: 120, local: 8, cap: 'Muito longe, a parte da expansão domina: as linhas andam bem para o vermelho e o movimento próprio vira detalhe.' }
  ];
  const lines = [120, 190, 300];
  return {
    duration: 1400,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const s = gals[v], k = ease(t), shift = (s.exp + s.local) * k;
      text(layer, 30, 34, 'laboratório', { class: 'mx-t small' });
      el('rect', { x: 30, y: 42, width: 420, height: 26, rx: 4, fill: C.soft }, layer);
      lines.forEach((x) => el('rect', { x, y: 42, width: 3, height: 26, fill: C.ink }, layer));
      text(layer, 30, 104, `galáxia ${s.name}`, { class: 'mx-t small warm' });
      el('rect', { x: 30, y: 112, width: 420, height: 26, rx: 4, fill: C.soft }, layer);
      lines.forEach((x) => { const nx = x + shift * (x / 190); if (nx < 448) el('rect', { x: nx, y: 112, width: 3, height: 26, fill: C.accent }, layer); });
      // decomposição do deslocamento
      const y = 190, x0 = 160;
      el('line', { x1: x0, y1: y - 16, x2: x0, y2: y + 52, stroke: C.line }, layer);
      text(layer, 30, y + 4, 'expansão', { class: 'mx-t small' });
      if (s.exp) arrow(layer, x0, y, x0 + s.exp * 1.8 * k, y, C.accent, 3);
      text(layer, 30, y + 38, 'movimento próprio', { class: 'mx-t small' });
      arrow(layer, x0, y + 34, x0 + s.local * 1.8 * k + (s.local < 0 ? -0.01 : 0.01), y + 34, C.blue, 3);
      text(layer, 450, 34, '← azul · vermelho →', { class: 'mx-t small', 'text-anchor': 'end' });
      return s.cap;
    }
  };
};

const cmb = (): Scene => {
  let layer: SVGGElement;
  const rnd = rng(101);
  const spots = Array.from({ length: 320 }, () => { const a = rnd() * Math.PI * 2, r = Math.sqrt(rnd()); return [W / 2 + Math.cos(a) * r * 205, 125 + Math.sin(a) * r * 100, 4 + rnd() * 7, rnd() < 0.5] as [number, number, number, boolean]; });
  const caps = [
    'Céu bruto (simulado): a faixa brilhante é a nossa própria galáxia, que também emite micro-ondas e fica na frente do sinal antigo.',
    'Retiramos a Via Láctea com medidas em várias frequências. Sobra uma luz quase igual em todas as direções.',
    'Realçamos as diferenças: vermelho um pouco mais quente, azul um pouco mais frio. São variações de cerca de 1 parte em 100 mil.',
    'Sem realce, o céu parece liso. As cores fortes dos mapas famosos são atribuídas para mostrar diferenças minúsculas.'
  ];
  return {
    duration: 1400,
    init(svg) {
      layer = g(svg);
      const defs = el('defs', {}, svg);
      const clip = el('clipPath', { id: 'mx-cmb-clip' }, defs);
      el('ellipse', { cx: W / 2, cy: 125, rx: 210, ry: 105 }, clip);
    },
    draw(v, t) {
      clear(layer);
      const k = ease(t);
      const contrast = v === 0 ? 0.12 : v === 1 ? 0.12 : v === 2 ? lerp(0.12, 0.5, k) : lerp(0.5, 0.04, k);
      const sky = g(layer, { 'clip-path': 'url(#mx-cmb-clip)' });
      el('ellipse', { cx: W / 2, cy: 125, rx: 210, ry: 105, fill: '#c9a46a' }, sky);
      for (const [x, y, r, hot] of spots) el('circle', { cx: x, cy: y, r, fill: hot ? '#d0402a' : '#2c5aa8', opacity: contrast }, sky);
      const band = v === 0 ? 1 : v === 1 ? 1 - k : 0;
      if (band > 0) el('ellipse', { cx: W / 2, cy: 125, rx: 220, ry: 16, fill: '#fff2c8', opacity: 0.9 * band }, sky);
      el('ellipse', { cx: W / 2, cy: 125, rx: 210, ry: 105, fill: 'none', stroke: C.line }, layer);
      text(layer, W / 2, 252, 'simulação didática, não o mapa real', { class: 'mx-t small', 'text-anchor': 'middle' });
      return caps[v];
    }
  };
};

const rotacao = (): Scene => {
  let layer: SVGGElement;
  const radii = [26, 52, 80];
  const caps = [
    'Previsão contando só o que brilha: quase toda a massa visível está no centro, então as estrelas de fora deveriam girar bem mais devagar.',
    'O que se mede: as estrelas de fora giram quase tão rápido quanto as de dentro. A curva fica quase plana.',
    'Com um halo de massa invisível em volta, a conta bate com a medida. Chamamos essa massa de matéria escura. Conhecemos o efeito, não a partícula.'
  ];
  return {
    duration: 3000,
    init(svg) {
      const rg = el('radialGradient', { id: 'mx-halo2' }, el('defs', {}, svg));
      el('stop', { offset: 0, 'stop-color': C.dm, 'stop-opacity': 0.35 }, rg);
      el('stop', { offset: 1, 'stop-color': C.dm, 'stop-opacity': 0 }, rg);
      layer = g(svg);
    },
    draw(v, t) {
      clear(layer);
      const cx = 110, cy = 128;
      if (v === 2) el('circle', { cx, cy, r: 105, fill: 'url(#mx-halo2)', opacity: ease(Math.min(1, t * 2)) }, layer);
      el('ellipse', { cx, cy, rx: 18, ry: 18, fill: C.gold, opacity: 0.7 }, layer);
      radii.forEach((r) => {
        el('circle', { cx, cy, r, fill: 'none', stroke: C.line, 'stroke-dasharray': '3 4' }, layer);
        const sp = v === 0 ? vLum(r) : vTotal(r);
        const ang = (t * sp * 4.2) / r - Math.PI / 2;
        star(layer, cx + Math.cos(ang) * r, cy + Math.sin(ang) * r, 4, C.accent, false);
      });
      // gráfico
      const X = (r: number) => 240 + r * 2.4, Y = (s: number) => 210 - s * 2; // vTotal máx ≈ 82 cabe em y≈46
      el('line', { x1: 240, y1: 210, x2: 460, y2: 210, stroke: C.line, 'stroke-width': 1.5 }, layer);
      el('line', { x1: 240, y1: 40, x2: 240, y2: 210, stroke: C.line, 'stroke-width': 1.5 }, layer);
      text(layer, 350, 236, 'distância ao centro →', { class: 'mx-t small', 'text-anchor': 'middle' });
      text(layer, 232, 34, 'velocidade', { class: 'mx-t small' });
      let dp = '', dobs = '';
      for (let r = 1; r <= 90; r += 2) { dp += `${dp ? 'L' : 'M'}${X(r)} ${Y(vLum(r))}`; dobs += `${dobs ? 'L' : 'M'}${X(r)} ${Y(vTotal(r))}`; }
      el('path', { d: dp, fill: 'none', stroke: C.muted, 'stroke-width': 2.5, 'stroke-dasharray': v === 0 ? '' : '6 5' }, layer);
      text(layer, X(88), Y(vLum(88)) + 18, 'previsão (só o visível)', { class: 'mx-t small', 'text-anchor': 'end' });
      if (v >= 1) {
        for (let r = 8; r <= 88; r += 10) el('circle', { cx: X(r), cy: Y(vTotal(r) + Math.sin(r) * 1.5), r: 3.5, fill: C.accent }, layer);
        text(layer, X(88), Y(vTotal(88)) - 10, 'medida', { class: 'mx-t small strong warm', 'text-anchor': 'end' });
      }
      if (v === 2) {
        let dh = '';
        for (let r = 1; r <= 90; r += 2) dh += `${dh ? 'L' : 'M'}${X(r)} ${Y(vHalo(r))}`;
        el('path', { d: dh, fill: 'none', stroke: C.dm, 'stroke-width': 1.5, 'stroke-dasharray': '4 4', opacity: 0.6 }, layer);
        text(layer, X(88), Y(vHalo(88)) + 14, 'só o halo', { class: 'mx-t small', 'text-anchor': 'end' });
        el('path', { d: dobs, fill: 'none', stroke: C.dm, 'stroke-width': 2.5 }, layer);
      }
      return caps[v];
    }
  };
};

/** Diferença de "quão fraca parece" (magnitudes) entre um Universo acelerando e um só de matéria. */
function deltaMag(z: number): number {
  const dl = (om: number, ol: number) => { let s = 0; const n = 60; for (let i = 0; i < n; i++) { const zz = ((i + 0.5) / n) * z; s += 1 / Math.sqrt(om * (1 + zz) ** 3 + ol); } return (1 + z) * (s * z) / n; };
  return 5 * Math.log10(dl(0.315, 0.685) / dl(1, 0));
}
const supernovas = (): Scene => {
  let layer: SVGGElement;
  const rnd = rng(8);
  const data = Array.from({ length: 22 }, () => { const z = 0.05 + rnd() * 1.1; const n = (rnd() + rnd() + rnd() - 1.5) * 0.18; return [z, deltaMag(z) + n, 0.12 + rnd() * 0.12] as [number, number, number]; });
  const X = (z: number) => 60 + z * 330, Y = (d: number) => 150 - d * 190;
  const caps = [
    'Cada ponto é uma supernova, com barra de erro. O eixo vertical mostra o quanto ela parece mais fraca do que num Universo só de matéria, freando.',
    'Se a expansão estivesse só freando, os pontos ficariam em volta desta linha. Eles ficam acima: as supernovas parecem mais fracas, mais longe do que o esperado.',
    'O modelo com aceleração (energia escura) passa no meio dos pontos. Nenhum ponto sozinho decide; o conjunto decide.'
  ];
  return {
    duration: 1400,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const k = ease(t);
      el('line', { x1: 60, y1: 230, x2: 450, y2: 230, stroke: C.line, 'stroke-width': 1.5 }, layer);
      el('line', { x1: 60, y1: 20, x2: 60, y2: 230, stroke: C.line, 'stroke-width': 1.5 }, layer);
      text(layer, 255, 258, 'mais distante →', { class: 'mx-t small', 'text-anchor': 'middle' });
      text(layer, 66, 30, '↑ mais fraca que o esperado', { class: 'mx-t small' });
      for (const [z, d, e] of data) {
        el('line', { x1: X(z), x2: X(z), y1: Y(d - e), y2: Y(d + e), stroke: C.ink2, 'stroke-width': 1.2 }, layer);
        el('circle', { cx: X(z), cy: Y(d), r: 3.5, fill: C.ink }, layer);
      }
      if (v >= 1) {
        el('line', { x1: 60, x2: lerp(60, 450, v === 1 ? k : 1), y1: Y(0), y2: Y(0), stroke: C.muted, 'stroke-width': 2.5, 'stroke-dasharray': '7 5' }, layer);
        text(layer, 450, Y(0) + 18, 'só freando', { class: 'mx-t small', 'text-anchor': 'end' });
      }
      if (v >= 2) {
        let d = '';
        for (let z = 0.01; z <= 1.2 * k + 0.01; z += 0.02) d += `${d ? 'L' : 'M'}${X(z)} ${Y(deltaMag(z))}`;
        el('path', { d, fill: 'none', stroke: C.accent, 'stroke-width': 3 }, layer);
        text(layer, X(1.15), Y(deltaMag(1.15)) - 12, 'acelerando', { class: 'mx-t small strong warm', 'text-anchor': 'end' });
      }
      return caps[v];
    }
  };
};

const ajuste = (): Scene => {
  let layer: SVGGElement;
  const rnd = rng(64);
  const all = Array.from({ length: 40 }, () => { const x = 0.5 + rnd() * 9.5; const n = (rnd() + rnd() + rnd() + rnd() - 2) * 2.4; return [x, 2 * x + 1 + n] as [number, number]; });
  const X = (x: number) => 50 + x * 40, Y = (y: number) => 235 - y * 9;
  return {
    init(svg) { layer = g(svg); },
    value: (v) => `${Math.round(v)} medidas`,
    draw(v) {
      clear(layer);
      const n = Math.round(v), pts = all.slice(0, n);
      const mx = pts.reduce((s, p) => s + p[0], 0) / n, my = pts.reduce((s, p) => s + p[1], 0) / n;
      const sxx = pts.reduce((s, p) => s + (p[0] - mx) ** 2, 0), sxy = pts.reduce((s, p) => s + (p[0] - mx) * (p[1] - my), 0);
      const b = sxy / sxx, a = my - b * mx;
      const res = pts.reduce((s, p) => s + (p[1] - a - b * p[0]) ** 2, 0) / Math.max(1, n - 2);
      const seb = Math.sqrt(res / sxx);
      el('line', { x1: 50, y1: 235, x2: 460, y2: 235, stroke: C.line, 'stroke-width': 1.5 }, layer);
      el('line', { x1: 50, y1: 15, x2: 50, y2: 235, stroke: C.line, 'stroke-width': 1.5 }, layer);
      let up = '', lo = '';
      for (let x = 0; x <= 10.2; x += 0.3) { const se = Math.sqrt(res * (1 / n + (x - mx) ** 2 / sxx)) * 2; up += `${up ? 'L' : 'M'}${X(x)} ${Y(a + b * x + se)}`; lo = `L${X(x)} ${Y(a + b * x - se)}` + lo; }
      el('path', { d: `${up}${lo}Z`, fill: C.accent, opacity: 0.15 }, layer);
      el('line', { x1: X(0), y1: Y(a), x2: X(10.2), y2: Y(a + b * 10.2), stroke: C.accent, 'stroke-width': 2.5 }, layer);
      for (const [x, y] of pts) el('circle', { cx: X(x), cy: Y(y), r: 4, fill: C.ink }, layer);
      text(layer, 60, 30, `inclinação estimada: ${fmt(b, 2)} ± ${fmt(seb, 2)}`, { class: 'mx-t strong' });
      return `Com ${n} medidas, a inclinação fica entre ${fmt(b - 2 * seb, 1)} e ${fmt(b + 2 * seb, 1)} (faixa colorida). ${n < 10 ? 'Poucos pontos: a faixa é larga, cabem várias conclusões.' : n < 25 ? 'A faixa estreita: o valor fica mais confiável.' : 'Faixa estreita. Mas atenção: um erro de calibração que desloca todos os pontos juntos não some com mais dados.'}`;
    }
  };
};

export const scenes: SceneMap = {
  'misterios-do-cosmos-horizonte': metodo,
  'misterios-do-cosmos-exoplanetas': espectros,
  'misterios-do-cosmos-vida': cmb,
  'misterios-do-cosmos-materia-escura': rotacao,
  'misterios-do-cosmos-energia-escura': supernovas,
  'misterios-do-cosmos-limites': ajuste
};
