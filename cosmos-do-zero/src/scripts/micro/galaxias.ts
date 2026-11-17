import type { Scene, SceneMap } from './engine';
import { C, H, W, arrow, clamp, clear, ease, el, g, lerp, rng, star, text } from './draw';

const viaLactea = (): Scene => {
  // Cada degrau é um poster das cenas atuais (1200×800), recortado para480×270; o ponto marcado no degrau seguinte
  // é onde o degrau anterior "cabe". Afastar a câmera = a imagem anterior encolhe até esse ponto.
  const base = import.meta.env.BASE_URL.replace(/\/$/, '');
  const levels = [
    { img: 'earth', at: [240, 135], mark: null as null | [number, number], label: '', ruler: 'Diâmetro: 12.700 km · a luz cruza em 0,04 s', cap: 'Terra: o planeta onde você está. Tudo o que vem a seguir a contém.' },
    { img: 'solar-system', at: [145, 130], mark: null, label: 'Terra', ruler: 'Até Netuno: 4,5 bilhões de km · a luz leva 4 horas', cap: 'Sistema Solar: o Sol e tudo o que gira em volta dele. Os planetas aparecem ampliados para leitura. Tamanhos e distâncias fora de escala.' },
    { img: 'milky-way', at: [330, 185], mark: null, label: 'Sol', ruler: 'Diâmetro: uns 100 mil anos-luz', cap: 'Via Láctea: a circunferência marca uma posição ilustrativa para o Sistema Solar. Centenas de bilhões de estrelas. O Sol fica num braço, a uns 26 mil anos-luz do centro, não no meio.' },
    { img: 'galaxies', at: [240,135], mark: null, label: 'Via Láctea', ruler: 'Uns 10 milhões de anos-luz', cap: 'Grupo Local: a Via Láctea, Andrômeda e dezenas de galáxias pequenas, presas pela gravidade.' },
    { img: 'cosmic-web', at: [123, 115], mark: null, label: 'Grupo Local', ruler: 'Filamentos com milhões de anos-luz', cap: 'Teia cósmica: grupos e aglomerados de galáxias ao longo de filamentos. O Grupo Local é um ponto num desses fios.' }
  ];
  let imgs: SVGImageElement[] = [], over: SVGGElement, ruler: SVGTextElement, prev = 0, from = 0;
  const place = (im: SVGImageElement, s: number, cx: number, cy: number, op: number) => {
    // escala s em torno do ponto (cx, cy) da tela
    im.setAttribute('transform', `translate(${cx} ${cy}) scale(${s}) translate(${-cx} ${-cy})`);
    im.setAttribute('opacity', String(op));
    im.setAttribute('display', op > 0.001 ? 'inline' : 'none');
  };
  return {
    duration: 1600,
    init(svg) {
      const root = g(svg);
      el('rect', { x: 0, y: 0, width: W, height: H, fill: '#04060b' }, root);
      imgs = levels.map((l) => el('image', { href: `${base}/renders/${l.img}.webp`, x: 0, y: -25, width: W, height: 320, preserveAspectRatio: 'xMidYMid slice', 'aria-hidden': 'true' }, root));
      over = g(svg);
      el('rect', { x: 0, y: H - 30, width: W, height: 30, fill: 'rgba(4,6,11,.72)' }, svg);
      ruler = text(svg, W / 2, H - 11, '', { class: 'mx-t', 'text-anchor': 'middle', fill: '#f3f1ea', style: 'fill:#f3f1ea' });
      text(svg, W - 8, 18, 'render artístico · fora de escala', { class: 'mx-t small', 'text-anchor': 'end', style: 'fill:rgba(243,241,234,.8);paint-order:stroke;stroke:#04060b;stroke-width:3px' });
    },
    draw(v, t) {
      if (v !== prev) { from = prev; prev = v; }
      if (t >= 1) from = v; // fim da transição: estado de repouso idêntico, venha de onde vier
      const k = ease(t), L = levels[v], [mx, my] = L.at;
      imgs.forEach((im, i) => { if (i !== v && i !== from) place(im, 1, mx, my, 0); });
      if (from < v) {
        // afastar: o degrau anterior encolhe até virar o ponto marcado; o novo entra de perto
        place(imgs[v], lerp(2.4, 1, k), mx, my, clamp(k * 1.6));
        if (from !== v) place(imgs[from], lerp(1, 0.04, k), mx, my, clamp(1 - k * 1.4));
      } else if (from > v) {
        // aproximar: o degrau de fora cresce em volta do ponto e some; o de dentro aparece
        const [fx, fy] = levels[from].at;
        place(imgs[from], lerp(1, 2.4, k), fx, fy, clamp(1 - k * 1.4));
        place(imgs[v], lerp(0.04, 1, k), fx, fy, clamp(k * 1.6));
      } else place(imgs[v], 1, mx, my, 1);
      clear(over);
      const op = clamp((t - 0.6) / 0.4);
      if (L.mark && op > 0) {
        const [x, y] = L.mark, right = x < 300, tg = g(over, { opacity: op });
        el('circle', { cx: x, cy: y, r: 11, fill: 'none', stroke: '#ffd166', 'stroke-width': 2.5 }, tg);
        el('line', { x1: x + (right ? 9 : -9), y1: y + 7, x2: x + (right ? 38 : -38), y2: y + 30, stroke: '#ffd166', 'stroke-width': 1.5 }, tg);
        text(tg, x + (right ? 41 : -41), y + 42, L.label, { class: 'mx-t strong', 'text-anchor': right ? 'start' : 'end', style: 'fill:#ffd166;paint-order:stroke;stroke:#04060b;stroke-width:3px' });
        if (v === 3) text(tg, 352, 196, 'Andrômeda', { class: 'mx-t', 'text-anchor': 'middle', style: 'fill:#f3f1ea;paint-order:stroke;stroke:#04060b;stroke-width:3px' });
      } else if (!L.mark && op > 0) {
        text(over, 14, 26, 'você está aqui', { class: 'mx-t strong', 'text-anchor': 'start', opacity: op, style: 'fill:#ffd166;paint-order:stroke;stroke:#04060b;stroke-width:3px' });
      }
      ruler.textContent = levels[v].ruler;
      return `Degrau ${v + 1} de 5. ${levels[v].cap}`;
    }
  };
};

const tipos = (): Scene => {
  let disc: SVGImageElement, halo: SVGEllipseElement, annotation: SVGTextElement;
  const field = import.meta.env.BASE_URL.replace(/\/$/, '') + '/models/galaxies-v4/768/';
  const maps = ['stars-only','grand-spiral','grand-spiral','elliptical'];
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
      el('rect',{width:W,height:H,fill:'#070b12'},svg);
      halo = el('ellipse',{cx:240,cy:135,rx:190,ry:120,fill:'url(#mx-halo)'},svg);
      disc = el('image',{x:50,y:-46,width:380,height:350,preserveAspectRatio:'none'},svg);
      annotation = text(svg,16,28,'',{class:'mx-t small',style:'fill:#eee6d8;paint-order:stroke;stroke:#070b12;stroke-width:3px'});
    },
    draw(v, t) {
      disc.setAttribute('href',field+maps[v]+'.webp');
      disc.setAttribute('transform',v===3?'rotate(-12 240 130)':'rotate(-17 240 130) translate(0 33) scale(1 .74)');
      halo.setAttribute('opacity',v===2?String(ease(t)): '0');
      annotation.textContent = ['Estrelas do disco','Gás, poeira e estrelas','Halo inferido · extensão ilustrativa','Galáxia elíptica'][v];
      return caps[v];
    }
  };
};

const teia = (): Scene => {
  let plate: SVGImageElement, traces: SVGPathElement, legends: SVGGElement;
  let last = -1;
  const rnd = rng(42);
  const nodes = [[35,75],[174,35],[281,84],[446,42],[129,162],[335,106],[392,211],[230,208]];
  const links = [[0,1],[1,2],[2,3],[0,4],[2,4],[2,5],[5,6],[4,7],[6,7]];
  const samples = Array.from({length:950}, () => {
    const [a,b] = links[Math.floor(rnd()*links.length)], f = rnd();
    return [rnd()*W, rnd()*H, lerp(nodes[a][0],nodes[b][0],f)+(rnd()-.5)*10, lerp(nodes[a][1],nodes[b][1],f)+(rnd()-.5)*12];
  });
  return {
    init(svg) {
      const layer = g(svg,{class:'mx-flat'});
      el('rect',{width:W,height:H,fill:'#050b11'},layer);
      plate = el('image',{width:W,height:H,preserveAspectRatio:'none',href:import.meta.env.BASE_URL+'renders/cosmic-web-small.webp'},layer);
      traces = el('path',{fill:'none',stroke:'#cfdbdf','stroke-width':1.3,'stroke-linecap':'round'},layer);
      legends = g(layer,{style:'fill:#f7f0de;stroke:#050b11;stroke-width:3px;paint-order:stroke'});
      for (const [title,x,y] of [['Vazio',160,109],['Aglomerado',282,76],['Filamento',62,136]] as const) {
        text(legends,x,y,title,{class:'mx-t small',style:'fill:#f7f0de'});
      }
    },
    value: v => v < .05 ? 'quase liso' : v < .95 ? Math.round(v*100)+'%' : 'teia formada',
    draw(v) {
      if (v !== last) {
        last = v;
        const k = 1 - (1-v)**2;
        plate.setAttribute('opacity', String(k*k));
        traces.setAttribute('opacity', String(.5*(1-k)));
        traces.setAttribute('d',k < .995 ? samples.map(([x,y,tx,ty]) =>
          'M'+lerp(x,tx,k).toFixed(1)+' '+lerp(y,ty,k).toFixed(1)+'h.1').join('') : '');
        legends.setAttribute('opacity',String(clamp((v-.88)/.12)));
      }
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


