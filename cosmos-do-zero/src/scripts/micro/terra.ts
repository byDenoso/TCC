import type { Scene, SceneMap } from './engine';
import { C, arrow, bar, clear, ease, el, fmt, g, lerp, rng, star, text } from './draw';

const formacao = (): Scene => {
  let layer: SVGGElement;
  const rnd = rng(13);
  const iron = Array.from({ length: 40 }, () => { const a = rnd() * Math.PI * 2, r = Math.sqrt(rnd()) * 100; return [a, r, rnd() * 38] as [number, number, number]; });
  const rock = Array.from({ length: 110 }, () => { const a = rnd() * Math.PI * 2, r = Math.sqrt(rnd()) * 105; return [a, r] as [number, number]; });
  const caps = [
    'Terra jovem: quente, em boa parte derretida, com ferro (vermelho escuro) e rochas misturados.',
    'O ferro é mais denso: afunda em direção ao centro, como pedra num pote de mel. Materiais leves sobem.',
    'Formam-se camadas: núcleo de ferro e níquel, manto de rocha e uma crosta fina.',
    'Hoje: núcleo interno sólido e externo líquido; o manto é quase todo sólido, mas flui muito devagar (centímetros por ano). Não é um oceano de lava.'
  ];
  return {
    duration: 1800,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const k = ease(t), cx = 150, cy = 130;
      if (v >= 2) {
        el('circle', { cx, cy, r: 115, fill: '#8a5a3a' }, layer);
        el('circle', { cx, cy, r: 110, fill: '#c0703a' }, layer);
        el('circle', { cx, cy, r: 58, fill: '#e0a040' }, layer);
        if (v === 3) el('circle', { cx, cy, r: 24, fill: '#f4d27a' }, layer);
        const labels: [string, number][] = v === 3 ? [['crosta', 112], ['manto (sólido que flui)', 85], ['núcleo externo (líquido)', 42], ['núcleo interno (sólido)', 10]] : [['crosta', 112], ['manto', 85], ['núcleo', 30]];
        labels.forEach(([n, r], i) => { el('line', { x1: cx + r, y1: cy - 4 - i * 2, x2: 300, y2: 50 + i * 42, stroke: C.line }, layer); text(layer, 305, 55 + i * 42, n, { class: 'mx-t small strong' }); });
        return caps[v];
      }
      el('circle', { cx, cy, r: 115, fill: '#d9884a', opacity: 0.85 }, layer);
      for (const [a, r] of rock) el('circle', { cx: cx + Math.cos(a) * r, cy: cy + Math.sin(a) * r, r: 2.2, fill: '#f0c890' }, layer);
      for (const [a, r, rc] of iron) { const rr = v === 0 ? r : lerp(r, rc, k); el('circle', { cx: cx + Math.cos(a) * rr, cy: cy + Math.sin(a) * rr, r: 3.4, fill: '#7a2a1a' }, layer); }
      if (v === 1) for (let i = 0; i < 6; i++) { const a = (i / 6) * Math.PI * 2; arrow(layer, cx + Math.cos(a) * 95, cy + Math.sin(a) * 95, cx + Math.cos(a) * 60, cy + Math.sin(a) * 60, C.ink, 1.5); }
      return caps[v];
    }
  };
};

const oxigenio = (): Scene => {
  let layer: SVGGElement;
  const X = (ga: number) => 40 + ((4.5 - ga) / 4.5) * 410;
  const air = (ga: number) => (ga > 2.4 ? 0.01 : ga > 0.6 ? lerp(0.12, 0.2, (2.4 - ga) / 1.8) : lerp(0.25, 1, (0.6 - ga) / 0.6));
  const sink = (ga: number) => (ga > 3 ? 0 : ga > 2.4 ? (3 - ga) / 0.6 : 1);
  return {
    init(svg) { layer = g(svg); },
    value: (v) => { const ga = 4.5 * (1 - v); return ga < 0.05 ? 'hoje' : `há ${fmt(ga, 1)} bilhões de anos`; },
    draw(v) {
      clear(layer);
      const ga = 4.5 * (1 - v);
      el('line', { x1: 40, y1: 200, x2: 450, y2: 200, stroke: C.line, 'stroke-width': 1.5 }, layer);
      [4, 3, 2, 1, 0].forEach((g2) => text(layer, X(g2), 220, g2 ? `${g2} bi` : 'hoje', { class: 'mx-t small', 'text-anchor': 'middle' }));
      text(layer, 40, 246, 'bilhões de anos atrás', { class: 'mx-t small' });
      let d = '';
      for (let gg = 4.5; gg >= ga; gg -= 0.02) d += `${d ? 'L' : 'M'}${X(gg)} ${200 - air(gg) * 150}`;
      if (d) el('path', { d, fill: 'none', stroke: C.blue, 'stroke-width': 3 }, layer);
      text(layer, 450, 40, 'oxigênio no ar (qualitativo)', { class: 'mx-t small', 'text-anchor': 'end', fill: C.blue });
      // reservatórios que consomem o oxigênio antes de ele ficar no ar
      el('rect', { x: 50, y: 30, width: 130, height: 18, rx: 4, fill: C.soft }, layer);
      el('rect', { x: 50, y: 30, width: 130 * sink(ga), height: 18, rx: 4, fill: C.accent }, layer);
      text(layer, 50, 66, 'oceanos e rochas absorvendo', { class: 'mx-t small' });
      el('line', { x1: X(ga), x2: X(ga), y1: 30, y2: 200, stroke: C.accent, 'stroke-dasharray': '4 4' }, layer);
      el('circle', { cx: X(ga), cy: 200 - air(ga) * 150, r: 6, fill: C.accent }, layer);
      return ga > 3.2 ? 'Atmosfera primitiva: quase sem oxigênio livre, com muito gás carbônico e nitrogênio. Respirar seria impossível para nós.'
        : ga > 2.4 ? 'Micróbios começam a soltar oxigênio pela fotossíntese. Mas o ferro dissolvido nos oceanos e as rochas consomem quase tudo: o ar continua sem oxigênio.'
        : ga > 0.6 ? 'Com os reservatórios cheios, o oxigênio começa a se acumular no ar (o "Grande Evento de Oxidação"), ainda bem menos que hoje.'
        : 'Nas últimas centenas de milhões de anos, o oxigênio chega perto do nível atual: cerca de 21% do ar.';
    }
  };
};

const ar = (): Scene => {
  let layer: SVGGElement;
  const rnd = rng(6);
  const mol = Array.from({ length: 36 }, () => [30 + rnd() * 420, 40 + rnd() * 150, rnd() < 0.18] as [number, number, boolean]);
  return {
    duration: 2600,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      if (v === 0) {
        for (let i = 0; i < 100; i++) { const x = 30 + (i % 10) * 22, y = 30 + Math.floor(i / 10) * 21; el('circle', { cx: x, cy: y, r: 8, fill: i < 78 ? C.blue : i < 99 ? C.accent : C.muted, opacity: i < Math.round(100 * ease(t)) ? 1 : 0.15 }, layer); }
        text(layer, 270, 46, '78 nitrogênio', { class: 'mx-t small strong', fill: C.blue });
        text(layer, 270, 70, '21 oxigênio', { class: 'mx-t small strong warm' });
        text(layer, 270, 94, '1 argônio', { class: 'mx-t small strong' });
        el('rect', { x: 270, y: 120, width: 190, height: 70, rx: 10, fill: C.surface, stroke: C.line }, layer);
        text(layer, 280, 144, 'gás carbônico:', { class: 'mx-t small strong' });
        text(layer, 280, 166, '0,04 de uma bolinha', { class: 'mx-t small' });
        el('circle', { cx: 440, cy: 160, r: 1.6, fill: C.ink }, layer);
        return 'Em 100 partes de ar seco: 78 de nitrogênio, 21 de oxigênio, quase 1 de argônio. O gás carbônico é cerca de 4 em cada 10 mil partes. Pouco em quantidade.';
      }
      el('rect', { x: 0, y: 215, width: 480, height: 55, fill: '#7a9a5a' }, layer);
      star(layer, 40, 30, 14, C.gold);
      for (const [x, y, ghg] of mol) el('circle', { cx: x, cy: y, r: ghg ? 6 : 4, fill: ghg ? C.accent : C.blue, opacity: ghg ? 1 : 0.5 }, layer);
      [70, 160, 250, 340, 430].forEach((x, i) => {
        const stopAt = i % 2 === 0 ? 95 + i * 6 : 20, len = lerp(215, stopAt, ease(Math.min(1, t * 1.3)));
        el('line', { x1: x, y1: 212, x2: x, y2: len, stroke: '#d24b5a', 'stroke-width': 2.5, 'stroke-dasharray': '6 4' }, layer);
        if (i % 2 === 0 && t > 0.75) { arrow(layer, x, stopAt, x - 22, stopAt + 30, '#d24b5a', 1.6); arrow(layer, x, stopAt, x + 22, stopAt - 26, '#d24b5a', 1.6); }
      });
      text(layer, 12, 250, 'tracejado: calor (infravermelho) saindo do chão', { class: 'mx-t small strong' });
      return 'O chão aquecido pelo Sol devolve calor como infravermelho. Nitrogênio e oxigênio (azuis) deixam passar. Gás carbônico e vapor d’água (vermelhos) absorvem e reemitem em todas as direções, inclusive de volta para baixo. Pouca quantidade, grande efeito.';
    }
  };
};

/** Perfil médio de temperatura (°C) com a altitude (km), aproximado. */
const PROFILE: [number, number][] = [[0, 15], [11, -56], [20, -56], [32, -44], [47, -2], [51, -2], [71, -58], [85, -86], [90, -86], [100, -78], [110, -33], [120, 87]];
const tempAt = (h: number): number => { for (let i = 1; i < PROFILE.length; i++) if (h <= PROFILE[i][0]) { const [h0, t0] = PROFILE[i - 1], [h1, t1] = PROFILE[i]; return lerp(t0, t1, (h - h0) / (h1 - h0)); } return PROFILE[PROFILE.length - 1][1]; };
const layerAt = (h: number): string => (h < 12 ? 'troposfera' : h < 50 ? 'estratosfera' : h < 85 ? 'mesosfera' : 'termosfera');
const camadas = (): Scene => {
  let layer: SVGGElement;
  const Y = (h: number) => 250 - (h / 120) * 230, X = (tc: number) => 230 + ((tc + 100) / 200) * 230;
  return {
    init(svg) {
      layer = g(svg);
    },
    value: (v) => `${Math.round(v)} km`,
    draw(v) {
      clear(layer);
      const bands: [number, number, string, string][] = [[0, 12, 'troposfera', '#dfeaf5'], [12, 50, 'estratosfera', '#e8e4f2'], [50, 85, 'mesosfera', '#efe2ea'], [85, 120, 'termosfera', '#f5e3d6']];
      for (const [a, b, n, col] of bands) { el('rect', { x: 10, y: Y(b), width: 460, height: Y(a) - Y(b), fill: `color-mix(in srgb, ${col} 14%, var(--bg))` }, layer); text(layer, 16, Y(b) + 16, n, { class: 'mx-t small strong' }); }
      // marcadores aproximados
      [[4, 'nuvens'], [25, 'ozônio'], [80, 'meteoros'], [110, 'auroras']].forEach(([h, n]) => text(layer, 140, Y(h as number) + 4, n as string, { class: 'mx-t small' }));
      el('rect', { x: 120, y: Y(35), width: 8, height: Y(15) - Y(35), fill: '#7a3bd6', opacity: 0.5 }, layer);
      el('line', { x1: X(0), x2: X(0), y1: 20, y2: 250, stroke: C.line, 'stroke-dasharray': '3 4' }, layer);
      text(layer, X(0), 268, '0 °C', { class: 'mx-t small', 'text-anchor': 'middle' });
      text(layer, X(-100), 268, '−100', { class: 'mx-t small', 'text-anchor': 'middle' });
      text(layer, X(100), 268, '+100', { class: 'mx-t small', 'text-anchor': 'middle' });
      el('polyline', { points: PROFILE.map(([h, tc]) => `${X(tc)},${Y(h)}`).join(' '), fill: 'none', stroke: C.accent, 'stroke-width': 3 }, layer);
      const tc = tempAt(v);
      el('line', { x1: 10, x2: 470, y1: Y(v), y2: Y(v), stroke: C.ink, 'stroke-width': 1, 'stroke-dasharray': '2 4' }, layer);
      el('circle', { cx: X(tc), cy: Y(v), r: 8, fill: C.ink, stroke: C.bg, 'stroke-width': 2 }, layer);
      text(layer, Math.min(X(tc) + 14, 380), Y(v) - 10, `${Math.round(v)} km · ${fmt(Math.round(tc))} °C`, { class: 'mx-t small strong' });
      const name = layerAt(v);
      const why = name === 'troposfera' ? 'Aqui acontecem o tempo, as nuvens e a chuva. Quanto mais alto, mais frio, porque o ar é aquecido de baixo, pelo chão.'
        : name === 'estratosfera' ? 'A temperatura volta a subir: a camada de ozônio absorve ultravioleta do Sol e esquenta o ar.'
        : name === 'mesosfera' ? 'Volta a esfriar: é a região mais fria. Muitos meteoros se queimam por aqui.'
        : 'Termosfera: o ar é rarefeito e esquenta muito ao absorver radiação do Sol. Auroras acontecem nesta altura. Acima, ela se estende por centenas de km até a exosfera.';
      return `${Math.round(v)} km, ${name}, cerca de ${fmt(Math.round(tc))} °C. ${why} As fronteiras são aproximadas e variam com o lugar e a estação.`;
    }
  };
};

const campo = (): Scene => {
  let layer: SVGGElement;
  const rnd = rng(15);
  const parts = Array.from({ length: 16 }, () => [rnd() * 0.9, 30 + rnd() * 210] as [number, number]);
  return {
    duration: 2800,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const ex = 340, ey = 135;
      if (v === 0) for (const s of [1, 1.6, 2.3]) { el('ellipse', { cx: ex - 20 * s, cy: ey, rx: 34 * s, ry: 44 * s, fill: 'none', stroke: C.blue, 'stroke-width': 1.3, opacity: 0.6 }, layer); el('ellipse', { cx: ex + 20 * s, cy: ey, rx: 34 * s, ry: 44 * s, fill: 'none', stroke: C.blue, 'stroke-width': 1.3, opacity: 0.6 }, layer); }
      el('circle', { cx: ex, cy: ey, r: 40, fill: C.blue, opacity: 0.18 }, layer);
      text(layer, ex, ey + 62, 'atmosfera', { class: 'mx-t small', 'text-anchor': 'middle' });
      el('circle', { cx: ex, cy: ey, r: 32, fill: '#3d7cc9' }, layer);
      star(layer, 20, ey, 16, C.gold);
      text(layer, 30, 22, 'vento solar →', { class: 'mx-t small strong' });
      parts.forEach(([off, y], i) => {
        const p = (t + off) % 1;
        let x = lerp(40, ex, p), yy = y;
        if (v === 0) { const d = ex - 130; if (x > d) { const k = (x - d) / (ex - d); yy = y < ey ? lerp(y, i % 5 === 0 ? ey - 34 : 10, k) : lerp(y, i % 5 === 0 ? ey + 34 : 260, k); x = lerp(d, i % 5 === 0 ? ex : ex + 60, k); } }
        else if (x > ex - 40) x = ex - 40;
        el('circle', { cx: x, cy: yy, r: 3, fill: C.gold }, layer);
      });
      if (v === 0 && t > 0.3) { el('ellipse', { cx: ex, cy: ey - 38, rx: 14, ry: 5, fill: '#3fe06f', opacity: 0.7 }, layer); el('ellipse', { cx: ex, cy: ey + 38, rx: 14, ry: 5, fill: '#3fe06f', opacity: 0.7 }, layer); }
      if (v === 1) for (let i = 0; i < 6; i++) el('circle', { cx: lerp(ex - 40, ex - 140 - i * 10, ease(t)), cy: ey - 40 + i * 16, r: 2, fill: C.blue, opacity: 1 - t }, layer);
      return v === 0
        ? 'Com campo magnético: as partículas do vento solar são desviadas em volta do planeta. Algumas descem perto dos polos e fazem auroras (verde). A atmosfera é outra camada, por dentro.'
        : 'Sem campo: o vento solar bate direto no alto da atmosfera e pode arrancar gás aos poucos, ao longo de muito tempo. Isso ajuda a explicar parte da história de Marte. Ter campo ajuda, mas não garante vida.';
    }
  };
};

const habitavel = (): Scene => {
  let layer: SVGGElement;
  const P = [
    { n: 'Vênus', p: 92, pt: '92 bar', temp: 464, water: 'não fica líquida', col: '#e2c28a', cap: 'Vênus: atmosfera esmagadora e 464 °C. Está perto da borda de dentro da região onde água poderia ser líquida, mas o efeito estufa descontrolado tornou isso impossível.' },
    { n: 'Terra', p: 1, pt: '1 bar', temp: 15, water: 'líquida', col: '#3d7cc9', cap: 'Terra: pressão e temperatura permitem água líquida. É o único lugar onde sabemos que existe vida.' },
    { n: 'Marte', p: 0.006, pt: '0,006 bar', temp: -65, water: 'gelo ou vapor', col: '#c1592f', cap: 'Marte: ar tão fino que a água líquida não se mantém na superfície por muito tempo. Há gelo, e houve água no passado. Vida? Ainda não sabemos.' },
    { n: 'Terra sem efeito estufa', p: 1, pt: '1 bar', temp: -18, water: 'congelaria em boa parte', col: '#a8c4e0', cap: 'Cenário hipotético: a mesma Terra, sem efeito estufa, teria média de uns −18 °C. A posição sozinha não garante água líquida.' }
  ];
  return {
    duration: 900,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const p = P[v], k = ease(t);
      el('circle', { cx: 80, cy: 120, r: 46, fill: p.col }, layer);
      text(layer, 80, 196, p.n.length > 12 ? 'Terra hipotética' : p.n, { class: 'mx-t strong', 'text-anchor': 'middle' });
      if (v === 3) text(layer, 80, 216, '(sem efeito estufa)', { class: 'mx-t small warm', 'text-anchor': 'middle' });
      bar(layer, 170, 50, 200, 3, (Math.log10(p.p) + 2.5) / 2 * k, 'pressão do ar (escala comprimida)', p.pt, C.blue);
      bar(layer, 170, 120, 200, 600, (p.temp + 100) * k, 'temperatura média', `${fmt(p.temp)} °C`, C.accent);
      text(layer, 170, 190, `água na superfície: ${p.water}`, { class: 'mx-t small strong' });
      return p.cap;
    }
  };
};

export const scenes: SceneMap = {
  'terra-e-atmosfera-formacao-da-terra': formacao,
  'terra-e-atmosfera-atmosfera-primitiva': oxigenio,
  'terra-e-atmosfera-ar-atual': ar,
  'terra-e-atmosfera-camadas': camadas,
  'terra-e-atmosfera-campo-magnetico': campo,
  'terra-e-atmosfera-habitabilidade': habitavel
};
