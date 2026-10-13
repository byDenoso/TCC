/**
 * A luz mais antiga em três etapas (Canvas 2D):
 *  A. Universo quente: elétrons livres desviam a luz (espalhamento). Sem fonte central: a caixa é um pedaço de um meio uniforme e se repete nas bordas.
 *  B. Formação de átomos: elétrons capturados pelos núcleos; o espalhamento cessa e as trilhas ficam retas.
 *  C. Expansão: aproximação de uma onda; a grade (o próprio espaço) e o comprimento de onda crescem juntos.
 * Desenho, painel, régua do espectro e legenda leem o mesmo estado. Com movimento reduzido, cada etapa mostra um quadro estático equivalente.
 */
import { A_DEC, STEP_TEXT, STEPS, URL_PARAM, bandOf, fmtLength, fmtScale, fmtTemp, peakUm, rulerPos, scaleAt, stepFromParam, tempAt, T_DEC } from '../lib/cmb-journey';
import { getParam, setParams } from '../lib/url-state';

const DONE_KEY = 'cosmos-v6-praticado';
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const DUR = [9000, 6500, 8000]; // ms por etapa; a etapa A repete em ciclo enquanto está tocando

function rng(seed: number): () => number {
  let s = seed >>> 0;
  return () => { s = (s + 0x6d2b79f5) >>> 0; let x = s; x = Math.imul(x ^ (x >>> 15), x | 1); x ^= x + Math.imul(x ^ (x >>> 7), x | 61); return ((x ^ (x >>> 14)) >>> 0) / 4294967296; };
}
const ease = (k: number) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);
const clamp = (x: number, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x));

interface Palette { bg: string; ink: string; ink2: string; muted: string; line: string; e: string; n: string; light: string; grid: string; dark: boolean }
function palette(): Palette {
  const cs = getComputedStyle(document.documentElement);
  const v = (n: string) => cs.getPropertyValue(n).trim();
  const dark = cs.colorScheme.includes('dark') || v('--bg').toLowerCase() === '#070b18';
  return { bg: v('--bg'), ink: v('--ink'), ink2: v('--ink-2'), muted: v('--muted'), line: v('--line-strong'), e: v('--accent-2'), n: v('--accent'), light: v('--c-rad'), grid: v('--line'), dark };
}

/* ───────── simulação (unidades: fração da largura, caixa periódica 1 × h) ───────── */
interface Nucleus { x: number; y: number; he: boolean }
interface Electron { x: number; y: number; vx: number; vy: number; home: number; bindAt: number; x0: number; y0: number; bound: number }
interface Photon { x: number; y: number; dx: number; dy: number; trail: number[]; flash: number }

class Plasma {
  n: Nucleus[] = []; e: Electron[] = []; p: Photon[] = [];
  h = 0.56;
  constructor(h: number) { this.reset(h); }
  reset(h: number): void {
    this.h = h;
    const r = rng(1091);
    this.n = []; this.e = []; this.p = [];
    const NN = Math.round(64 * h / 0.56);
    for (let i = 0; i < NN; i++) this.n.push({ x: r(), y: r() * h, he: i % 12 === 0 });
    this.n.forEach((nu, i) => {
      const k = nu.he ? 2 : 1;
      for (let j = 0; j < k; j++) {
        const x = r(), y = r() * h, a = r() * Math.PI * 2;
        this.e.push({ x, y, vx: Math.cos(a), vy: Math.sin(a), home: i, bindAt: 0.12 + 0.68 * r(), x0: x, y0: y, bound: 0 });
      }
    });
    for (let i = 0; i < 6; i++) { const a = r() * Math.PI * 2; this.p.push({ x: r(), y: r() * h, dx: Math.cos(a), dy: Math.sin(a), trail: [], flash: 0 }); }
  }
  /** Avança dt (s). freeFrac: fração de elétrons ainda livres (1 em A, cai em B). */
  step(dt: number, bindProgress: number | null, r: () => number): void {
    const h = this.h;
    const wrap = (o: { x: number; y: number }) => { o.x = (o.x + 1) % 1; o.y = (o.y + h) % h; };
    // elétrons: agitação térmica; em B, captura pelo núcleo de origem
    for (const el of this.e) {
      if (bindProgress === null || bindProgress < el.bindAt) {
        el.vx += (r() - 0.5) * 6 * dt; el.vy += (r() - 0.5) * 6 * dt;
        const s = Math.hypot(el.vx, el.vy) || 1; el.vx /= s; el.vy /= s;
        el.x += el.vx * 0.05 * dt; el.y += el.vy * 0.05 * dt; wrap(el);
        el.x0 = el.x; el.y0 = el.y; el.bound = 0;
      } else {
        el.bound = clamp((bindProgress - el.bindAt) / 0.14);
      }
    }
    // luz: anda em linha reta e muda de direção ao passar perto de um elétron livre
    const speed = 0.19, rs = 0.022;
    for (const ph of this.p) {
      const nx = ph.x + ph.dx * speed * dt, ny = ph.y + ph.dy * speed * dt;
      ph.flash = Math.max(0, ph.flash - dt * 2.5);
      let hit = false;
      for (const el of this.e) {
        if (el.bound > 0.5) continue;
        let ddx = el.x - nx, ddy = el.y - ny;
        if (ddx > 0.5) ddx -= 1; if (ddx < -0.5) ddx += 1; if (ddy > h / 2) ddy -= h; if (ddy < -h / 2) ddy += h;
        if (ddx * ddx + ddy * ddy < rs * rs && r() < 0.5) { hit = true; break; }
      }
      if (hit) {
        const a = r() * Math.PI * 2; ph.dx = Math.cos(a); ph.dy = Math.sin(a); ph.flash = 1; // o vértice da trilha marca o desvio
      }
      const jumped = nx < 0 || nx >= 1 || ny < 0 || ny >= h;
      ph.x = (nx + 1) % 1; ph.y = (ny + h) % h;
      if (jumped) ph.trail.push(Infinity, Infinity); // quebra da trilha ao atravessar a borda periódica
      ph.trail.push(ph.x, ph.y);
      const cap = this.p[0] === ph ? 520 : 200; if (ph.trail.length > cap) ph.trail.splice(0, ph.trail.length - cap);
    }
  }
}

/* ───────── componente ───────── */
export function initCmbJourney(): void {
  document.querySelectorAll<HTMLElement>('[data-cmbj]').forEach((root) => {
    if (root.dataset.cmbjBooted) return;
    root.dataset.cmbjBooted = '1';
    const io = 'IntersectionObserver' in window ? new IntersectionObserver((es) => { if (es.some((x) => x.isIntersecting)) { io!.disconnect(); setup(root); } }, { rootMargin: '400px 0px' }) : null;
    if (io) io.observe(root); else setup(root);
  });
}

function setup(root: HTMLElement): void {
  const canvas = root.querySelector<HTMLCanvasElement>('[data-cmbj-canvas]')!;
  const ctx = canvas.getContext('2d');
  const stage = root.querySelector<HTMLElement>('[data-cmbj-stage]')!;
  const q = <T extends HTMLElement>(s: string) => root.querySelector<T>(s)!;
  const stepBtns = [...root.querySelectorAll<HTMLButtonElement>('[data-cmbj-goto]')];
  const btnPrev = q<HTMLButtonElement>('[data-cmbj-prev]'), btnNext = q<HTMLButtonElement>('[data-cmbj-next]');
  const btnPlay = q<HTMLButtonElement>('[data-cmbj-play]'), btnReplay = q<HTMLButtonElement>('[data-cmbj-replay]');
  const live = q('[data-cmbj-live]');
  const fields = { ask: q('[data-cmbj-ask]'), say: q('[data-cmbj-say]'), act: q('[data-cmbj-act]'), changed: q('[data-cmbj-changed]') };
  const panel = { time: q('[data-cmbj-time]'), temp: q('[data-cmbj-temp]'), scale: q('[data-cmbj-scale]'), lambda: q('[data-cmbj-lambda]'), band: q('[data-cmbj-band]'), marker: q('[data-cmbj-marker]'), ruler: q('[data-cmbj-ruler]') };
  // faixas da régua na mesma escala do marcador (o CSS tem os mesmos valores como reserva sem JS)
  { const v = rulerPos(0.75), m = rulerPos(1000); panel.ruler.style.gridTemplateColumns = `${v}fr ${m - v}fr ${1 - m}fr`; }
  const legends = [...root.querySelectorAll<HTMLElement>('[data-cmbj-legend]')];
  if (!ctx) { root.classList.add('is-static'); return; }

  let step = stepFromParam(getParam(URL_PARAM));
  let t = 0, elapsed = 0, playing = false, frame = 0, last = 0, visible = true, done = false, autoPaused = false;
  let pal = palette();
  let W = 0, H = 0, dpr = 1;
  const plasma = new Plasma(0.56);
  const r = rng(7);
  const sprites = new Map<string, HTMLCanvasElement>();
  const particle = (x: number, y: number, radius: number, color: string) => {
    let sprite = sprites.get(color);
    if (!sprite) {
      sprite = document.createElement('canvas'); sprite.width = sprite.height = 64;
      const c = sprite.getContext('2d')!;
      const glow = c.createRadialGradient(30, 28, 0, 32, 32, 32);
      glow.addColorStop(0, '#fff8e7'); glow.addColorStop(0.18, color);
      glow.addColorStop(0.42, color); glow.addColorStop(0.43, `${color}70`); glow.addColorStop(1, `${color}00`);
      c.fillStyle = glow; c.fillRect(0, 0, 64, 64); sprites.set(color, sprite);
    }
    const halo = radius * 2.3;
    ctx.drawImage(sprite, x - halo, y - halo, halo * 2, halo * 2);
  };

  const resize = () => {
    const box = stage.getBoundingClientRect();
    W = Math.max(280, box.width); H = Math.max(240, box.height);
    dpr = Math.min(window.devicePixelRatio || 1, W < 600 ? 1.5 : 2);
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    const h = H / W;
    if (Math.abs(h - plasma.h) > 0.01) { plasma.reset(h); warm(); }
    draw();
  };
  /** Pré-aquece a simulação para não começar com trilhas vazias. */
  const warm = () => { for (let i = 0; i < 160; i++) plasma.step(1 / 30, step === 0 ? null : step === 1 ? (reduced.matches ? 1 : ease(t)) : 1, r); };

  /* ── desenho ── */
  const drawPlasma = (bind: number | null) => {
    const s = W; // 1 unidade = largura
    // brilho de fundo: meio quente e opaco (A) que esfria em B
    const heat = bind === null ? 1 : 1 - ease(clamp(bind));
    if (heat > 0.01) {
      // meio quente e opaco por igual (sem foco central): véu quente uniforme que some quando o Universo esfria
      ctx.fillStyle = pal.n; ctx.globalAlpha = (pal.dark ? 0.13 : 0.10) * heat; ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = pal.light; ctx.globalAlpha = (pal.dark ? 0.06 : 0.16) * heat; ctx.fillRect(0, 0, W, H); ctx.globalAlpha = 1;
    }
    // núcleos e átomos
    for (const nu of plasma.n) {
      particle(nu.x * s, nu.y * s, nu.he ? 4.6 : 3.4, pal.n);
    }
    // elétrons
    for (const el of plasma.e) {
      const nu = plasma.n[el.home];
      if (el.bound > 0) {
        const k = ease(el.bound);
        // trajetória até o núcleo (sem atravessar a borda periódica)
        let tx = nu.x, ty = nu.y;
        if (tx - el.x0 > 0.5) tx -= 1; if (tx - el.x0 < -0.5) tx += 1; if (ty - el.y0 > plasma.h / 2) ty -= plasma.h; if (ty - el.y0 < -plasma.h / 2) ty += plasma.h;
        const ang = elapsed / 600 + el.bindAt * 40;
        const orb = 9 / s;
        const x = el.x0 + (tx - el.x0) * k + Math.cos(ang) * orb * k, y = el.y0 + (ty - el.y0) * k + Math.sin(ang) * orb * k;
        if (k > 0.85) { ctx.strokeStyle = pal.e; ctx.globalAlpha = 0.45 * (k - 0.85) / 0.15; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(nu.x * s, nu.y * s, 9, 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1; }
        particle(((x % 1) + 1) % 1 * s, ((y % plasma.h) + plasma.h) % plasma.h * s, 2.1, pal.e);
      } else {
        particle(el.x * s, el.y * s, 2.1, pal.e);
      }
    }
    // luz: trilhas com cauda que desbota; pontos de desvio marcados
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    plasma.p.forEach((ph, pi) => {
      const lead = pi === 0; // uma trilha em destaque; as outras ficam discretas
      const tr = ph.trail, n = tr.length / 2, base = lead ? 0.3 : 0.05, span = lead ? 0.7 : 0.25;
      if (lead) { ctx.shadowColor = pal.light; ctx.shadowBlur = 8; }
      let started = false;
      ctx.strokeStyle = pal.light; ctx.lineWidth = lead ? 3 : 1.2;
      for (let i = 0; i < n; i++) {
        const x = tr[2 * i], y = tr[2 * i + 1];
        if (!Number.isFinite(x)) { if (started) { ctx.stroke(); started = false; } continue; }
        if (!started) { ctx.globalAlpha = base + span * (i / n); ctx.beginPath(); ctx.moveTo(x * s, y * s); started = true; }
        else { ctx.lineTo(x * s, y * s); if (i % 12 === 0) { ctx.stroke(); ctx.globalAlpha = base + span * (i / n); ctx.beginPath(); ctx.moveTo(x * s, y * s); } }
      }
      if (started) ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.globalAlpha = lead ? 1 : 0.55;
      particle(ph.x * s, ph.y * s, lead ? 5 : 2.6, pal.light);
      ctx.globalAlpha = 1; ctx.shadowBlur = 0;
      if (lead && ph.flash > 0) { ctx.strokeStyle = pal.light; ctx.globalAlpha = ph.flash; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(ph.x * s, ph.y * s, 6 + 12 * (1 - ph.flash), 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1; }
    });
  };

  /** Etapa C: grade do espaço e uma onda, ampliadas. k ∈ [0,1] percorre o fator de escala de 1/1091 até 1 em escala logarítmica. */
  const drawExpansion = (k: number, travel: number) => {
    const a = scaleAt(k);
    const stretch = Math.pow(a / A_DEC, Math.log(3) / Math.log(1 / A_DEC)); // 1 → 3 na tela (escala comprimida; o real é ~1 100)
    const cell = Math.min(W, H) * 0.1 * stretch;
    const ox = W * 0.08, oy = H * 0.5; // ponto da grade fixo na tela: escolha do desenho, não um centro
    // grade = o próprio espaço
    ctx.strokeStyle = pal.grid; ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = ox - Math.ceil(ox / cell) * cell; x <= W; x += cell) { ctx.moveTo(x, 0); ctx.lineTo(x, H); }
    for (let y = oy - Math.ceil(oy / cell) * cell; y <= H; y += cell) { ctx.moveTo(0, y); ctx.lineTo(W, y); }
    ctx.stroke();
    // átomos presos a nós da grade: a distância entre eles cresce com a grade
    const nodes: [number, number][] = [[1, -2], [3, 1], [5, -1], [7, 2], [2, 2], [6, -2], [9, 0], [11, -1], [12, 2], [4, -3], [8, 3], [10, -3], [13, 1], [15, -2], [16, 3], [18, 0], [14, -4], [2, 4], [6, 4], [20, 2]];
    for (const [i, j] of nodes) {
      const x = ox + i * cell, y = oy + j * cell;
      if (x > W + 10 || y < -10 || y > H + 10) continue;
      ctx.fillStyle = pal.n; ctx.beginPath(); ctx.arc(x, y, 3.4, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = pal.e; ctx.globalAlpha = 0.6; ctx.beginPath(); ctx.arc(x, y, 8, 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1;
    }
    // onda: comprimento de onda proporcional à célula da grade (as duas crescem juntas)
    const lam = cell * 0.9, amp = Math.min(H * 0.13, 34);
    const head = ox + travel * (W - ox) * 1.05;
    ctx.strokeStyle = pal.ink; ctx.lineWidth = 2.6; ctx.beginPath();
    let first = true;
    for (let x = Math.max(0, head - W * 0.85); x <= Math.min(W, head); x += 2) {
      const env = clamp((x - (head - W * 0.85)) / (W * 0.12)) * clamp((head - x) / (W * 0.06));
      const y = oy - amp * env * Math.sin(((x - head) / lam) * Math.PI * 2);
      if (first) { ctx.moveTo(x, y); first = false; } else ctx.lineTo(x, y);
    }
    ctx.stroke();
    // régua de um comprimento de onda, ao lado da onda
    const rx = Math.min(W - lam - 16, Math.max(16, head - lam * 1.6)), ry = oy + amp + 22;
    if (head > ox + lam) {
      ctx.strokeStyle = pal.ink2; ctx.lineWidth = 1.4; ctx.beginPath();
      ctx.moveTo(rx, ry); ctx.lineTo(rx + lam, ry); ctx.moveTo(rx, ry - 5); ctx.lineTo(rx, ry + 5); ctx.moveTo(rx + lam, ry - 5); ctx.lineTo(rx + lam, ry + 5); ctx.stroke();
      ctx.fillStyle = pal.ink2; ctx.font = `600 ${W < 520 ? 13 : 14}px ${getComputedStyle(root).fontFamily}`; ctx.textAlign = 'center';
      ctx.fillText('1 comprimento de onda', rx + lam / 2, ry + 18);
    }
    return a;
  };

  const draw = () => {
    root.dataset.bound = String(plasma.e.filter((e) => e.bound > 0.5).length); // elétrons presos (lido pelos testes)
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const k = reduced.matches ? 1 : t;
    let a = A_DEC;
    if (step === 0) drawPlasma(null);
    else if (step === 1) drawPlasma(ease(k));
    else a = drawExpansion(ease(k), reduced.matches ? 0.92 : clamp(t * 1.25));
    sync(a, k);
  };

  /* ── texto, painel e controles: mesmo estado do desenho ── */
  const sync = (a: number, k: number) => {
    const st = STEP_TEXT[step];
    root.dataset.step = st.id;
    stepBtns.forEach((b, i) => { b.setAttribute('aria-current', i === step ? 'step' : 'false'); b.dataset.state = i < step ? 'done' : i === step ? 'now' : 'next'; });
    legends.forEach((l) => { l.hidden = !l.dataset.cmbjLegend!.split(' ').includes(st.id); });
    btnPrev.disabled = step === 0; btnNext.disabled = step === STEPS.length - 1;
    if (step === 0) {
      panel.time.textContent = 'antes de ~380 mil anos'; panel.temp.textContent = `acima de ${fmtTemp(T_DEC)}`; panel.scale.textContent = `menor que ${fmtScale(A_DEC)}`;
      panel.lambda.textContent = 'luz presa no meio'; panel.band.textContent = '—';
    } else if (step === 1) {
      panel.time.textContent = '≈ 380 mil anos'; panel.temp.textContent = `≈ ${fmtTemp(T_DEC)}`; panel.scale.textContent = fmtScale(A_DEC);
      const um = peakUm(A_DEC); panel.lambda.textContent = `pico em ≈ ${fmtLength(um)}`; panel.band.textContent = bandOf(um);
    } else {
      const now = k >= 0.999;
      panel.time.textContent = now ? '≈ 13,8 bilhões de anos (hoje)' : 'a luz viajando'; panel.temp.textContent = fmtTemp(tempAt(a)); panel.scale.textContent = fmtScale(a);
      const um = peakUm(a); panel.lambda.textContent = `pico em ≈ ${fmtLength(um)}`; panel.band.textContent = bandOf(um);
    }
    const um = step === 0 ? null : peakUm(a);
    panel.marker.hidden = um === null;
    if (um !== null) panel.marker.style.setProperty('--pos', String(rulerPos(um)));
    panel.ruler.setAttribute('aria-valuetext', um === null ? 'sem valor nesta etapa' : `${fmtLength(um)}, ${bandOf(um)}`);
    fields.ask.textContent = st.ask; fields.say.textContent = st.say; fields.act.textContent = st.act; fields.changed.textContent = st.changed;
    root.classList.toggle('show-changed', done || reduced.matches || !playing && t > 0.5);
  };

  const announce = () => { const st = STEP_TEXT[step]; live.textContent = `Etapa ${step + 1} de 3: ${st.label}. ${st.say}`; };
  const setPlaying = (on: boolean) => {
    playing = on; btnPlay.setAttribute('aria-pressed', String(on));
    const finished = !on && t >= 1;
    btnPlay.dataset.mode = on ? 'pause' : finished && step < 2 ? 'next' : finished ? 'again' : t > 0 ? 'resume' : 'start';
    btnPlay.querySelector('[data-cmbj-play-label]')!.textContent = { pause: 'Pausar', next: 'Próxima etapa', again: 'Ver de novo', resume: 'Continuar', start: 'Começar' }[btnPlay.dataset.mode]!;
    btnPlay.querySelector('.cmbj-ico')!.textContent = on ? '❚❚' : btnPlay.dataset.mode === 'next' ? '→' : btnPlay.dataset.mode === 'again' ? '↺' : '▶';
  };
  const tick = (now: number) => {
    if (!playing) return;
    const dt = last ? Math.min(now - last, 50) : 16; last = now;
    elapsed += dt;
    t += dt / DUR[step];
    if (step !== 2) plasma.step(dt / 1000, step === 0 ? null : ease(clamp(t)), r);
    if (t >= 1) {
      if (step === 0) { t = 0; done = true; } // o meio quente não "termina": a cena repete
      else { t = 1; done = true; draw(); setPlaying(false); return; }
    }
    draw();
    frame = requestAnimationFrame(tick);
  };
  const play = () => { if (!visible || document.hidden || reduced.matches) { if (!reduced.matches) autoPaused = true; draw(); return; } if (t >= 1) t = 0; last = 0; setPlaying(true); cancelAnimationFrame(frame); frame = requestAnimationFrame(tick); };
  const pause = () => { cancelAnimationFrame(frame); setPlaying(false); draw(); };
  const go = (i: number, autoplay = true) => {
    step = clamp(i, 0, STEPS.length - 1); t = 0; elapsed = 0; done = false;
    if (step <= 1) { plasma.reset(plasma.h); warm(); } // A: elétrons livres; B: recomeça a captura
    setParams({ [URL_PARAM]: step === 0 ? null : String(step + 1) });
    announce();
    draw(); // painel e etapa atualizados já no clique, sem esperar o próximo quadro
    if (autoplay && !reduced.matches) play(); else { pause(); }
  };
  btnPrev.addEventListener('click', () => go(step - 1));
  btnNext.addEventListener('click', () => go(step + 1));
  btnReplay.addEventListener('click', () => { t = 0; done = false; if (step === 1) { plasma.reset(plasma.h); warm(); } play(); });
  btnPlay.addEventListener('click', () => { autoPausedReset(); const m = btnPlay.dataset.mode; if (playing) pause(); else if (m === 'next') go(step + 1); else if (m === 'again') go(0); else play(); });
  stepBtns.forEach((b, i) => b.addEventListener('click', () => go(i)));
  root.addEventListener('keydown', (ev) => {
    if ((ev.target as HTMLElement).closest('button, a, input, summary')) {
      if (ev.key === 'ArrowRight' && (ev.target as HTMLElement).matches('[data-cmbj-goto]')) { ev.preventDefault(); stepBtns[Math.min(2, step + 1)].focus(); go(step + 1); }
      if (ev.key === 'ArrowLeft' && (ev.target as HTMLElement).matches('[data-cmbj-goto]')) { ev.preventDefault(); stepBtns[Math.max(0, step - 1)].focus(); go(step - 1); }
    }
  });

  // visibilidade: pausa fora da tela e com a aba oculta; libera o quadro
  const autoPausedReset = () => { autoPaused = false; };
  // pausa automática (fora da tela ou aba oculta) retoma sozinha quando a cena volta; pausa pelo botão não
  new IntersectionObserver(([e]) => {
    visible = e.isIntersecting;
    if (!visible && playing) { pause(); autoPaused = true; }
    else if (visible && autoPaused && !document.hidden) { autoPaused = false; play(); }
  }, { threshold: 0.2 }).observe(stage);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && playing) { pause(); autoPaused = true; }
    else if (!document.hidden && autoPaused && visible) { autoPaused = false; play(); }
  });
  reduced.addEventListener('change', () => { pause(); });
  const refreshPalette = () => { pal = palette(); sprites.clear(); draw(); };
  new MutationObserver(refreshPalette).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', refreshPalette);
  new ResizeObserver(() => resize()).observe(stage);

  setupChecks(root);
  root.classList.add('is-ready');
  resize(); warm(); announce();
  setPlaying(false);
  draw();
}

/** Verificação (observar a animação não conta como domínio: só acertar as perguntas marca o progresso) depois da experiência (mesma chave de progresso das microexperiências). */
function setupChecks(root: HTMLElement): void {
  const section = root.closest<HTMLElement>('.lesson-section')?.id ?? root.dataset.section ?? '';
  const boxes = [...root.querySelectorAll<HTMLElement>('[data-cmbj-check]')];
  const answered = new Set<number>();
  const history = root.querySelector<HTMLElement>('[data-cmbj-history]');
  let prev: Set<string>;
  try { prev = new Set(JSON.parse(localStorage.getItem(DONE_KEY) ?? '[]') as string[]); } catch { prev = new Set(); }
  if (history && prev.has(section)) { history.hidden = false; history.textContent = 'Você acertou estas perguntas numa visita anterior. Elas começam de novo agora.'; }
  boxes.forEach((box, bi) => {
    const right = Number(box.dataset.right);
    const btns = [...box.querySelectorAll<HTMLButtonElement>('[data-cmbj-opt]')];
    const out = box.querySelector<HTMLElement>('[data-cmbj-why]')!;
    btns.forEach((b, i) => b.addEventListener('click', () => {
      const ok = i === right;
      btns.forEach((x, j) => { x.dataset.state = j === i ? (ok ? 'right' : 'wrong') : ok && j !== right ? 'idle' : x.dataset.state ?? 'idle'; if (ok) x.disabled = true; });
      out.hidden = false;
      out.querySelector('strong')!.textContent = ok ? 'Isso.' : 'Ainda não.';
      out.querySelector('span')!.textContent = ok ? ` ${out.dataset.why}` : ' Volte à etapa da experiência ligada a esta pergunta e tente de novo.';
      if (ok) answered.add(bi);
      if (answered.size === boxes.length) {
        prev.add(section);
        try { localStorage.setItem(DONE_KEY, JSON.stringify([...prev])); } catch { /* sem armazenamento */ }
        root.dataset.practiced = 'true';
        document.querySelectorAll<HTMLAnchorElement>(`[data-toc] a[href="#${section}"]`).forEach((a) => (a.dataset.practiced = 'true'));
        root.dispatchEvent(new CustomEvent('cosmos:micro', { bubbles: true, detail: { id: section } }));
      }
    }));
  });
}
