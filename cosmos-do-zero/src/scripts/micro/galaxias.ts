import type { Scene, SceneMap } from './engine';
import { C, H, W, arrow, clear, ease, el, g, lerp, rng, star, text } from './draw';

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
  const names = ['Terra', 'Sistema Solar', 'Via Láctea', 'Grupo Local', 'Teia cósmica'];
  const dimensions = ['12.700 km', '4,5 bilhões de km', '100 mil anos-luz', '10 milhões de anos-luz', 'Milhões de anos-luz'];
  const measures = ['diâmetro aproximado', 'do Sol até Netuno', 'diâmetro aproximado', 'extensão aproximada', 'ao longo dos filamentos'];
  const captions = [
    'Terra: o planeta onde você está. Agora escolha Sistema Solar para descobrir onde ela cabe.',
    'Sistema Solar: a Terra é um dos planetas que orbitam o Sol. A luz leva cerca de quatro horas do Sol a Netuno. Tamanhos e distâncias no desenho são ilustrativos.',
    'Via Láctea: nosso Sistema Solar fica a cerca de 26 mil anos-luz do centro. A galáxia reúne centenas de bilhões de estrelas.',
    'Grupo Local: a Via Láctea, Andrômeda e dezenas de galáxias menores formam um conjunto ligado pela gravidade.',
    'Teia cósmica: grupos e aglomerados se distribuem em filamentos, separados por regiões menos povoadas. O desenho mostra a organização, não um mapa do céu.'
  ];
  let layer: SVGGElement;
  return {
    init(svg) { layer = g(svg); },
    draw(v) {
      clear(layer);
      const k = Math.round(v), cx = 145, cy = 123;
      const line = (x1:number,y1:number,x2:number,y2:number) => el('line',{x1,y1,x2,y2,stroke:C.line,'stroke-width':1.5},layer);
      if (k === 0) {
        el('circle',{cx,cy,r:74,fill:'#39798c'},layer);
        el('path',{d:'M117 60L144 57L168 80L157 102L183 122L169 146L150 148L137 185L118 161L123 133L102 112Z',fill:'#9dc6ae'},layer);
        el('ellipse',{cx,cy,rx:74,ry:24,fill:'none',stroke:'#c5e2d6',opacity:.55},layer);
      } else if (k === 1) {
        [33,58,83,108].forEach((r,i)=>{el('ellipse',{cx,cy,rx:r,ry:r*.66,fill:'none',stroke:C.line},layer);el('circle',{cx:cx+r*Math.cos(i*1.6),cy:cy+r*.66*Math.sin(i*1.6),r:i===1?7:4,fill:i===1?'#39798c':C.accent},layer);});
        el('circle',{cx,cy,r:14,fill:C.gold},layer);
        text(layer,cx,cy+36,'Sol',{'text-anchor':'middle',class:'mx-t small'});
      } else if (k === 2) {
        for(const [x,y,r] of spiral(4,420,cx,cy,108,.63))el('circle',{cx:x,cy:y,r,fill:C.accent,opacity:.65},layer);
        el('ellipse',{cx,cy,rx:17,ry:12,fill:C.gold},layer);
        el('circle',{cx:207,cy:144,r:5,fill:C.gold,stroke:C.ink2,'stroke-width':1.5},layer);
        line(207,151,222,186);text(layer,217,204,'Sol',{class:'mx-t small','text-anchor':'middle'});
      } else if (k === 3) {
        [[95,102],[186,151]].forEach(([x,y],i)=>{for(const [sx,sy,r]of spiral(i+3,110,x,y,44,.5))el('circle',{cx:sx,cy:sy,r:r*.8,fill:C.accent,opacity:.7},layer);});
        for(let i=0;i<14;i++)el('ellipse',{cx:65+(i*67)%165,cy:48+(i*41)%150,rx:3,ry:2,fill:C.gold},layer);
        text(layer,90,151,'Via Láctea',{class:'mx-t small','text-anchor':'middle'});
        text(layer,186,196,'Andrômeda',{class:'mx-t small','text-anchor':'middle'});
      } else {
        const nodes=[[50,65],[135,42],[235,82],[180,135],[74,167],[225,205],[125,220]];
        [[0,1],[0,4],[1,2],[1,3],[2,3],[2,5],[3,4],[3,5],[4,6],[5,6]].forEach(([a,b])=>{const A=nodes[a],B=nodes[b];line(A[0],A[1],B[0],B[1]);for(let j=0;j<12;j++)el('circle',{cx:lerp(A[0],B[0],j/11)+Math.sin(j*4)*3,cy:lerp(A[1],B[1],j/11)+Math.cos(j*4)*3,r:1.5,fill:C.accent},layer);});
        nodes.forEach(([x,y])=>el('circle',{cx:x,cy:y,r:4,fill:C.gold},layer));
      }
      line(278,40,278,213);
      text(layer,300,77,names[k],{class:'mx-t strong'});
      const words=dimensions[k].split(' ');
      const top=k===0?dimensions[k]:words.slice(0,-1).join(' ');
      const bottom=k===0?'':words[words.length-1];
      text(layer,300,122,top,{class:'mx-t strong',style:'font-size:23px;fill:var(--accent-ink)'});
      if(bottom)text(layer,300,148,bottom,{class:'mx-t',style:'font-size:19px'});
      text(layer,300,178,measures[k],{class:'mx-t small',style:'font-size:11px'});
      names.forEach((_,i)=>el('circle',{cx:204+i*18,cy:245,r:i===k?4:2.5,fill:i===k?C.accent:C.line},layer));
      return `Degrau ${k+1} de 5. ${captions[k]}`;
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
    init(svg) { layer = g(svg, { class: 'mx-flat' }); },
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


