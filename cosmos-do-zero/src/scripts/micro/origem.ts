import {expansionPositions,separation} from '../../lib/expansion';
import type { Scene, SceneMap } from './engine';
import { C, H, W, arrow, clear, ease, el, fmt, g, lerp, rng, star, text } from './draw';

const expansao = (): Scene => {
  let layer: SVGGElement;
  const base=expansionPositions.map(p=>[p[0]*30,p[2]*26-p[1]*12] as [number,number]);
  const me=0,cx=225,cy=130,nearI=1,farI=2;
  return {
    init(svg) { layer = g(svg); },
    value: (v) => `${fmt(v, 2)} ×`,
    draw(v) {
      clear(layer);
      const [mx, my] = base[me];
      const pos = base.map(([x, y]) => [cx + (x - mx) * v + mx, cy + (y - my) * v + my] as [number, number]);
      // distâncias a partir de "você": as vizinhas e uma mais distante
      const near = nearI, far = farI;
      for (const n of [near, far]) arrow(layer, pos[me][0], pos[me][1], pos[n][0], pos[n][1], C.accent, 1.6);
      pos.forEach(([x, y], i) => el('ellipse', { cx: x, cy: y, rx: i === me ? 7 : 5, ry: i === me ? 4.5 : 3, fill: i === me ? C.accent : C.ink2 }, layer));
      text(layer, pos[me][0] - 8, pos[me][1] - 10, 'A · observador', { class: 'mx-t small strong warm', 'text-anchor': 'end' });
      // sistema preso pela gravidade: não cresce
      el('rect', { x: 372, y: 8, width: 100, height: 92, rx: 10, fill: C.surface, stroke: C.line }, layer);
      star(layer, 422, 50, 7, C.gold, false);
      el('circle', { cx: 422, cy: 50, r: 26, fill: 'none', stroke: C.line }, layer);
      el('circle', { cx: 448, cy: 50, r: 3.5, fill: C.blue }, layer);
      text(layer, 422, 92, 'Sol e Terra', { class: 'mx-t small', 'text-anchor': 'middle' });
      const dn=separation(near,me),df=separation(far,me);
      text(layer, 12, H - 30, `vizinha: ${fmt(1, 1)} → ${fmt(v, 2)}   ·   distante: ${fmt(df / dn, 1)} → ${fmt((df / dn) * v, 1)}`, { class: 'mx-t small' });
      return v < 1.02 ? 'Todas as distâncias entre galáxias vão crescer pelo mesmo fator. Mexa no controle.'
        : `As distâncias entre galáxias cresceram ${fmt(v, 2)} vezes; seus tamanhos continuam iguais. Quem começa mais longe ganha uma distância maior, na mesma proporção. Sistemas ligados pela gravidade, como o Sistema Solar, não acompanham essa expansão.`;
    }
  };
};

const redshift = (): Scene => {
  let layer: SVGGElement;
  const x0 = 40, x1 = 440;
  const nmX = (nm: number) => x0 + ((nm - 380) / (1100 - 380)) * (x1 - x0);
  const wave = (p: Element, y: number, lam: number, color: string) => {
    let d = `M${x0} ${y}`;
    for (let x = x0; x <= x1; x += 2) d += `L${x} ${y - 18 * Math.sin(((x - x0) / lam) * Math.PI * 2)}`;
    el('path', { d, fill: 'none', stroke: color, 'stroke-width': 2.5 }, p);
  };
  return {
    init(svg) {
      layer = g(svg);
      const defs = el('defs', {}, svg);
      const grad = el('linearGradient', { id: 'mx-rs-grad', x1: 0, x2: 1, y1: 0, y2: 0 }, defs);
      [[0, '#7a3bd6'], [0.2, '#3b6bff'], [0.38, '#27c6e6'], [0.5, '#3fbf5f'], [0.62, '#e8c93a'], [0.75, '#ff8a2e'], [0.9, '#e0352b'], [1, '#5a1010']].forEach(([o, c]) => el('stop', { offset: o, 'stop-color': c as string }, grad));
    },
    value: (v) => `${fmt(v, 2)} ×`,
    draw(v) {
      clear(layer);
      text(layer, x0, 26, 'onda emitida', { class: 'mx-t small' });
      wave(layer, 56, 36, C.blue);
      text(layer, x0, 100, 'onda que chega', { class: 'mx-t small warm' });
      wave(layer, 130, 36 * v, C.accent);
      el('rect', { x: x0, y: 180, width: nmX(750) - x0, height: 26, fill: 'url(#mx-rs-grad)' }, layer);
      el('rect', { x: nmX(750), y: 180, width: x1 - nmX(750), height: 26, fill: C.soft }, layer);
      text(layer, nmX(925), 198, 'infravermelho', { class: 'mx-t small', 'text-anchor': 'middle' });
      for (const nm of [434, 486, 656]) {
        el('line', { x1: nmX(nm), x2: nmX(nm), y1: 172, y2: 180, stroke: C.ink, 'stroke-width': 2 }, layer);
        const o = nm * v;
        if (o < 1100) el('rect', { x: nmX(o) - 1.5, y: 180, width: 3, height: 26, fill: '#000', opacity: 0.85 }, layer);
      }
      text(layer, x0, 168, 'linhas no laboratório ▾', { class: 'mx-t small' });
      text(layer, x0, 228, 'linhas na luz recebida (faixas escuras)', { class: 'mx-t small warm' });
      return v < 1.02 ? 'Sem expansão no caminho, a onda chega igual e as linhas escuras ficam no mesmo lugar do laboratório.'
        : `O espaço cresceu ${fmt(v, 2)} vezes durante a viagem, e a onda ficou ${fmt(v, 2)} vezes mais longa. As linhas andaram para o vermelho${v > 1.7 ? ' e algumas já saíram para o infravermelho, que nossos olhos não veem' : ''}. É isso que os astrônomos chamam de redshift.`;
    }
  };
};

const nucleos = (): Scene => {
  let layer: SVGGElement;
  const rnd = rng(31);
  const P = Array.from({ length: 24 }, () => [30 + rnd() * 300, 30 + rnd() * 200] as [number, number]);
  const N = Array.from({ length: 4 }, () => [30 + rnd() * 300, 30 + rnd() * 200] as [number, number]);
  const he: [number, number][] = [[120, 110], [250, 170]];
  const temps = ['10 bilhões °C', '1 bilhão °C', '400 milhões °C', '2.700 °C'];
  const caps = [
    'Um segundo depois: prótons (vermelho), nêutrons (cinza) e elétrons soltos, quente demais para qualquer coisa ficar grudada.',
    'Uns 3 minutos: esfriou o bastante para prótons e nêutrons se juntarem. Quase todos os nêutrons acabam presos em núcleos de hélio.',
    'Uns 20 minutos: a fábrica para. Por massa, ficou cerca de 3/4 de hidrogênio e 1/4 de hélio, com traços de outros núcleos leves. Ainda não há átomos: os elétrons estão soltos.',
    'Uns 380 mil anos depois: frio o bastante para os elétrons ficarem presos aos núcleos. Agora sim existem átomos. Núcleos levaram minutos; átomos, centenas de milhares de anos.'
  ];
  return {
    duration: 1500,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      const k = ease(t), jig = v === 0 ? 1 : v === 1 ? 0.6 : 0.3;
      const wob = (i: number) => (v < 3 ? Math.sin(t * 20 + i) * 4 * jig : 0);
      const toHe = v >= 2 ? 1 : v === 1 ? k : 0;
      N.forEach(([x, y], i) => { const [hx, hy] = he[i >> 1]; el('circle', { cx: lerp(x, hx + (i % 2 ? 6 : -6), toHe) + wob(i), cy: lerp(y, hy + 6, toHe), r: 6, fill: C.muted }, layer); });
      P.forEach(([x, y], i) => {
        const bound = i < 4;
        const [hx, hy] = bound ? he[i >> 1] : [0, 0];
        const px = bound ? lerp(x, hx + (i % 2 ? 6 : -6), toHe) : x + wob(i + 9), py = bound ? lerp(y, hy - 6, toHe) : y;
        el('circle', { cx: px, cy: py, r: 6, fill: C.accent }, layer);
        if (v === 3 && !bound) el('circle', { cx: px, cy: py, r: 13, fill: 'none', stroke: C.blue, 'stroke-width': 1.2, opacity: k }, layer);
      });
      if (v === 3) he.forEach(([x, y]) => el('circle', { cx: x, cy: y, r: 20, fill: 'none', stroke: C.blue, 'stroke-width': 1.2, opacity: k }, layer));
      if (v < 3) for (let i = 0; i < 24; i++) el('circle', { cx: 30 + ((i * 53 + t * 260) % 300), cy: 30 + ((i * 37 + t * 140) % 200), r: 2, fill: C.blue }, layer);
      el('rect', { x: 352, y: 20, width: 118, height: 120, rx: 10, fill: C.surface, stroke: C.line }, layer);
      text(layer, 362, 42, 'temperatura', { class: 'mx-t small' });
      text(layer, 362, 64, `~${temps[v]}`, { class: 'mx-t small strong warm' });
      el('circle', { cx: 368, cy: 88, r: 5, fill: C.accent }, layer); text(layer, 380, 92, 'próton', { class: 'mx-t small' });
      el('circle', { cx: 368, cy: 108, r: 5, fill: C.muted }, layer); text(layer, 380, 112, 'nêutron', { class: 'mx-t small' });
      el('circle', { cx: 368, cy: 128, r: 2.5, fill: C.blue }, layer); text(layer, 380, 132, 'elétron', { class: 'mx-t small' });
      return caps[v];
    }
  };
};

const primeiraLuz = (): Scene => {
  let layer: SVGGElement;
  const rnd = rng(12);
  const e = Array.from({ length: 22 }, () => [40 + rnd() * 400, 30 + rnd() * 170] as [number, number]);
  const zig: [number, number][] = [[30, 120], [90, 60], [130, 160], [175, 80], [210, 190], [250, 70], [300, 150], [330, 90], [380, 170], [450, 110]];
  const caps = [
    'Névoa quente: a luz bate em elétrons soltos a todo instante e muda de direção, como farol na neblina. Já existe luz, mas ela não vai longe.',
    'O Universo esfriou: os elétrons se prendem aos núcleos e formam átomos. Quase não sobram elétrons soltos para desviar a luz.',
    'A luz agora viaja em linha reta, livre. É essa luz que, 13,8 bilhões de anos depois, chega aos nossos telescópios.',
    'No caminho, o espaço cresceu cerca de mil vezes e esticou a onda: a luz saiu alaranjada e chega como micro-ondas.'
  ];
  return {
    duration: 2000,
    init(svg) { layer = g(svg); },
    draw(v, t) {
      clear(layer);
      if (v === 3) {
        let d1 = 'M40 70', d2 = 'M40 170';
        for (let x = 40; x <= 440; x += 2) { d1 += `L${x} ${70 - 16 * Math.sin(((x - 40) / 18) * Math.PI * 2)}`; d2 += `L${x} ${170 - 16 * Math.sin(((x - 40) / lerp(18, 180, ease(t))) * Math.PI * 2)}`; }
        el('path', { d: d1, fill: 'none', stroke: '#ff8a2e', 'stroke-width': 2.5 }, layer);
        el('path', { d: d2, fill: 'none', stroke: C.blue, 'stroke-width': 2.5 }, layer);
        text(layer, 40, 40, 'como saiu: alaranjada', { class: 'mx-t small' });
        text(layer, 40, 140, 'como chega hoje: micro-ondas', { class: 'mx-t small warm' });
        return caps[3];
      }
      const atoms = v >= 1 ? (v === 1 ? ease(t) : 1) : 0;
      e.forEach(([x, y], i) => {
        if (i % 2 === 0) { el('circle', { cx: x, cy: y, r: 5, fill: C.accent }, layer); el('circle', { cx: x, cy: y, r: 12, fill: 'none', stroke: C.blue, opacity: atoms, 'stroke-width': 1.2 }, layer); }
        else { const [px, py] = e[i - 1]; el('circle', { cx: lerp(x, px + 12, atoms), cy: lerp(y, py, atoms), r: 2.5, fill: C.blue }, layer); }
      });
      if (v === 0) {
        const total = zig.length - 1, f = t * total, seg = Math.min(total - 1, Math.floor(f)), k = f - seg;
        const pts = zig.slice(0, seg + 1).concat([[lerp(zig[seg][0], zig[seg + 1][0], k), lerp(zig[seg][1], zig[seg + 1][1], k)]]);
        el('polyline', { points: pts.map((p) => p.join(',')).join(' '), fill: 'none', stroke: C.gold, 'stroke-width': 2, opacity: 0.7 }, layer);
        const [hx, hy] = pts[pts.length - 1]; el('circle', { cx: hx, cy: hy, r: 5, fill: C.gold }, layer);
      } else {
        for (const y of [60, 120, 180]) { const x = lerp(20, 460, v === 2 ? t : 1); el('line', { x1: 20, y1: y, x2: x, y2: y, stroke: C.gold, 'stroke-width': 2, opacity: v === 1 ? 0 : 0.8 }, layer); if (v === 2) el('circle', { cx: x, cy: y, r: 5, fill: C.gold }, layer); }
      }
      text(layer, 12, H - 10, 'amarelo: luz · vermelho: núcleo · azul: elétron', { class: 'mx-t small' });
      return caps[v];
    }
  };
};

const estruturas = (): Scene => {
  let layer: SVGGElement;
  const rnd = rng(55);
  const seeds = Array.from({ length: 9 }, () => [40 + rnd() * 400, 30 + rnd() * 150, 0.5 + rnd() * 0.5] as [number, number, number]);
  return {
    init(svg) { layer = g(svg); },
    value: (v) => (v < 0.15 ? '380 mil anos' : v < 0.45 ? 'dezenas de milhões de anos' : v < 0.75 ? 'uns 100 a 250 milhões de anos?' : 'uns 500 milhões a 1 bilhão de anos'),
    draw(v) {
      clear(layer);
      for (const [x, y, s] of seeds) {
        const grow = Math.min(1, v * 1.6) * s;
        el('circle', { cx: x, cy: y, r: 6 + 26 * (1 - grow), fill: C.ink2, opacity: 0.08 + 0.4 * grow }, layer);
        const lit = (v - 0.45) * 3 * s;
        if (lit > 0) {
          el('circle', { cx: x, cy: y, r: Math.min(70, 70 * lit * Math.max(0, (v - 0.55) * 2.4)), fill: C.blue, opacity: 0.12 }, layer);
          star(layer, x, y, 3 + 2 * Math.min(1, lit), C.gold);
        }
      }
      // eixo do tempo com faixa de incerteza
      const y = 225;
      el('line', { x1: 30, y1: y, x2: 450, y2: y, stroke: C.line, 'stroke-width': 2 }, layer);
      el('rect', { x: 220, y: y - 8, width: 110, height: 16, fill: C.accent, opacity: 0.15 }, layer);
      text(layer, 275, y + 26, 'primeiras estrelas: data incerta', { class: 'mx-t small warm', 'text-anchor': 'middle' });
      el('circle', { cx: lerp(30, 450, v), cy: y, r: 7, fill: C.accent }, layer);
      text(layer, 30, y - 14, 'transparente', { class: 'mx-t small' });
      return v < 0.15 ? 'O Universo acabou de ficar transparente. A matéria é quase uniforme, com regiões só um pouquinho mais densas.'
        : v < 0.45 ? 'Idade das trevas: ainda sem estrelas. A gravidade faz as regiões densas crescerem e o gás se concentrar.'
        : v < 0.75 ? 'As primeiras estrelas acendem dentro das concentrações de gás. A data exata ainda é incerta: a faixa no eixo mostra isso.'
        : 'Bolhas de gás ionizado (azul) crescem em volta das primeiras galáxias até se juntarem. Galáxias maiores se formam por fusões.';
    }
  };
};

const comeco = (): Scene => {
  let layer: SVGGElement;
  const segs = [
    { x: 30, w: 50, kind: 'unknown', label: '?' },
    { x: 80, w: 70, kind: 'hyp', label: 'inflação?' },
    { x: 150, w: 70, kind: 'model', label: '' },
    { x: 220, w: 50, kind: 'ev', label: 'núcleos leves' },
    { x: 270, w: 50, kind: 'model', label: '' },
    { x: 320, w: 40, kind: 'ev', label: 'luz antiga' },
    { x: 360, w: 90, kind: 'ev', label: 'galáxias' }
  ];
  const caps = [
    'Firmes: medimos a quantidade de núcleos leves, a luz mais antiga e a evolução das galáxias. As três pistas concordam.',
    'Entre as pistas, o modelo calcula a história com física testada em laboratório.',
    'A inflação é uma hipótese para um instante muito anterior: um crescimento rapidíssimo. Explica várias coisas, mas ainda não foi confirmada.',
    'Antes disso, não sabemos. A física conhecida não descreve com segurança o começo absoluto.'
  ];
  return {
    duration: 1200,
    init(svg) {
      layer = g(svg);
      const defs = el('defs', {}, svg);
      const pat = el('pattern', { id: 'mx-hatch', width: 8, height: 8, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' }, defs);
      el('rect', { width: 8, height: 8, fill: C.surface }, pat);
      el('line', { x1: 0, y1: 0, x2: 0, y2: 8, stroke: C.accent, 'stroke-width': 3 }, pat);
    },
    draw(v, t) {
      clear(layer);
      const k = ease(t);
      const show = (kind: string) => (kind === 'ev' ? 0 : kind === 'model' ? 1 : kind === 'hyp' ? 2 : 3);
      for (const s of segs) {
        const step = show(s.kind), on = step < v ? 1 : step === v ? k : 0;
        const fill = s.kind === 'ev' ? C.ink : s.kind === 'model' ? C.blue : s.kind === 'hyp' ? 'url(#mx-hatch)' : C.soft;
        el('rect', { x: s.x, y: 110, width: s.w - 2, height: 34, rx: 4, fill, opacity: 0.15 + 0.85 * on }, layer);
        if (s.label && on > 0.3) text(layer, s.x + s.w / 2, s.kind === 'ev' ? 170 : 96, s.label, { class: `mx-t small${s.kind === 'ev' ? ' strong' : ' warm'}`, 'text-anchor': 'middle' });
      }
      text(layer, 30, 220, 'começo', { class: 'mx-t small' });
      text(layer, 450, 220, 'hoje', { class: 'mx-t small', 'text-anchor': 'end' });
      arrow(layer, 70, 216, 420, 216, C.line, 1.5);
      return caps[v];
    }
  };
};

export const scenes: SceneMap = {
  'origem-do-universo-o-universo': expansao,
  'origem-do-universo-expansao': redshift,
  'origem-do-universo-fase-quente': nucleos,
  'origem-do-universo-primeira-luz': primeiraLuz,
  'origem-do-universo-primeiras-estruturas': estruturas,
  'origem-do-universo-nossa-epoca': comeco
};
void W;
