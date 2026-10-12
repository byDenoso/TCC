import { LOCAL_H0, OMEGA_B, PLANCK, ageNow, fate, flat, hasBounce, omegaK, omegaR, scaleCurve, type Cosmos } from '../../lib/cosmology';
import { clear, duration, fmt, initGuess, q, qa, svg } from './common';
import { getParam, setParams } from '../../lib/url-state';

const W = 640, H = 400, PL = 52, PR = 18, PT = 22, PB = 46;

const scenarios: Record<string, Cosmos> = {
  nosso: PLANCK,
  materia: { h0: PLANCK.h0, om: 1, ol: 0 },
  crunch: { h0: PLANCK.h0, om: 2, ol: 0 },
  escura: flat(PLANCK.h0, 0.1)
};

export function initReceita(root: HTMLElement): void {
  const chart = q<SVGSVGElement>(root, '[data-r-chart]');
  const sOm = q<HTMLInputElement>(root, '[data-r-om]'), sOl = q<HTMLInputElement>(root, '[data-r-ol]'), sH0 = q<HTMLInputElement>(root, '[data-r-h0]');
  const oOm = q(root, '[data-r-om-out]'), oOl = q(root, '[data-r-ol-out]'), oH0 = q(root, '[data-r-h0-out]');
  const out = Object.fromEntries(qa(root, '[data-r-out]').map((n) => [n.dataset.rOut!, n])) as Record<string, HTMLElement>;
  const mix = qa(root, '[data-r-mix] span');
  const mixText = q(root, '[data-r-mixtext]');
  const warn = q(root, '[data-r-warn]');
  const tension = q(root, '[data-r-tension]');
  const live = q(root, '[data-r-live]');
  const chips = qa<HTMLButtonElement>(root, '[data-r-scenario]');
  const ref = scaleCurve(PLANCK, ageNow(PLANCK) + 45);
  const refAge = ageNow(PLANCK);

  let drawNext = true;
  const params = (): Cosmos => ({ om: Number(sOm.value), ol: Number(sOl.value), h0: Number(sH0.value) });
  const set = (p: Cosmos): void => { sOm.value = String(p.om); sOl.value = String(p.ol); sH0.value = String(p.h0); render(); };

  const draw = (p: Cosmos, age: number, f: ReturnType<typeof fate>): void => {
    clear(chart);
    const x0 = -(Math.max(age, refAge) + 1.2);
    const x1 = f.kind === 'crunch' ? f.crunchGyr! - age + 3 : 42;
    const curve = scaleCurve(p, age + 46);
    const yMax = f.kind === 'crunch' ? Math.max(2, f.aMax! * 1.12) : Math.min(8, Math.max(2.4, interp(curve, age + x1) * 1.04));
    const X = (x: number) => PL + ((x - x0) / (x1 - x0)) * (W - PL - PR);
    const Y = (a: number) => H - PB - (a / yMax) * (H - PB - PT);
    const defs = svg('defs', {}, chart);
    const clip = svg('clipPath', { id: 'r-clip' }, defs);
    svg('rect', { x: PL, y: PT - 4, width: W - PL - PR, height: H - PB - PT + 4 }, clip);
    // grade e eixos
    const ticks = [-10, 0, 10, 20, 30, 40].filter((t) => t >= x0 && t <= x1);
    for (const t of ticks) { svg('line', { x1: X(t), x2: X(t), y1: PT, y2: H - PB, class: t === 0 ? 'r-today' : 'obs-gridline' }, chart); svg('text', { x: X(t), y: H - PB + 18, 'text-anchor': 'middle', class: 'obs-cap small' }, chart, t === 0 ? 'hoje' : `${t > 0 ? '+' : '−'}${Math.abs(t)}`); }
    for (let a = 1; a <= yMax; a += yMax > 5 ? 2 : 1) { svg('line', { x1: PL, x2: W - PR, y1: Y(a), y2: Y(a), class: a === 1 ? 'r-today' : 'obs-gridline' }, chart); svg('text', { x: PL - 8, y: Y(a) + 4, 'text-anchor': 'end', class: 'obs-cap small' }, chart, `${a}×`); }
    svg('line', { x1: PL, y1: H - PB, x2: W - PR, y2: H - PB, class: 'obs-axis' }, chart);
    svg('line', { x1: PL, y1: PT, x2: PL, y2: H - PB, class: 'obs-axis' }, chart);
    svg('text', { x: (PL + W - PR) / 2, y: H - 6, 'text-anchor': 'middle', class: 'obs-cap small' }, chart, 'tempo a partir de hoje (bilhões de anos)');
    svg('text', { x: 13, y: (PT + H - PB) / 2, 'text-anchor': 'middle', class: 'obs-cap small', transform: `rotate(-90 13 ${(PT + H - PB) / 2})` }, chart, 'distâncias entre galáxias (hoje = 1)');
    const g = svg('g', { 'clip-path': 'url(#r-clip)' }, chart);
    const path = (c: { t: number[]; a: number[] }, shift: number) => c.t.map((t, i) => `${i ? 'L' : 'M'}${X(t - shift).toFixed(1)} ${Y(c.a[i]).toFixed(1)}`).join('');
    svg('path', { d: path(ref, refAge), class: 'r-ref' }, g);
    svg('path', { d: path(curve, age), class: drawNext ? 'r-curve is-draw' : 'r-curve', pathLength: 1 }, g);
    drawNext = false;
    svg('circle', { cx: X(0), cy: Y(1), r: 5, class: 'r-now' }, chart);
    svg('circle', { cx: X(-age), cy: Y(0), r: 4, class: 'r-bang' }, chart);
    svg('text', { x: Math.min(X(-age) + 8, W - 120), y: Y(0) - 8, class: 'obs-cap warm' }, chart, 'início (Big Bang)');
    svg('text', { x: PL + 10, y: PT + 14, class: 'obs-cap' }, chart, 'tracejado: o nosso Universo');
    if (f.kind === 'crunch') svg('text', { x: X(f.crunchGyr! - age) - 6, y: H - PB - 10, 'text-anchor': 'end', class: 'obs-cap warm' }, chart, 'colapso');
  };
  const interp = (c: { t: number[]; a: number[] }, t: number): number => { for (let i = 1; i < c.t.length; i++) if (c.t[i] >= t) return c.a[i]; return c.a[c.a.length - 1]; };

  const render = (): void => {
    const p = params();
    const rel = (v: number, ref: number) => { const r = v / ref; return v === 0 ? 'nenhuma' : Math.abs(r - 1) < 0.03 ? 'igual ao nosso' : r < 0.6 ? 'bem menos que no nosso' : r < 1 ? 'um pouco menos' : r < 1.6 ? 'um pouco mais' : r < 3 ? 'bem mais que no nosso' : 'muito mais que no nosso'; };
    oOm.textContent = rel(p.om, PLANCK.om); oOl.textContent = rel(p.ol, PLANCK.ol);
    oH0.textContent = Math.abs(p.h0 - PLANCK.h0) < 0.05 ? 'igual ao nosso' : p.h0 > PLANCK.h0 ? (p.h0 / PLANCK.h0 > 1.15 ? 'bem mais rápido' : 'um pouco mais rápido') : (p.h0 / PLANCK.h0 < 0.85 ? 'bem mais lento' : 'um pouco mais lento');
    const bounce = hasBounce(p);
    warn.hidden = !bounce;
    q(root, '[data-r-chartwrap]').classList.toggle('is-off', bounce);
    const age = bounce ? NaN : ageNow(p);
    const ok = !bounce && Number.isFinite(age);
    const f = ok ? fate(p) : null;
    if (ok && f) draw(p, age, f); else clear(chart);
    out.age.textContent = ok ? `${duration(age)}${Math.abs(age - refAge) > 0.05 ? ` (o nosso: ${fmt(refAge, 1)} bilhões)` : ''}` : '—';
    out.accel.textContent = f ? (f.q0 < 0 ? 'acelerando' : 'freando') : '—';
    out.fate.textContent = f ? (f.kind === 'crunch' ? `para de crescer, encolhe e colapsa daqui a ${duration(f.crunchGyr! - age)}` : f.kind === 'accelerating' ? 'cresce para sempre, cada vez mais rápido' : 'cresce para sempre, cada vez mais devagar') : '—';
    const ok2 = 1 - p.om - p.ol - omegaR(p);
    out.geom.textContent = Math.abs(ok2) < 0.005 ? 'plana: a geometria da escola funciona' : ok2 > 0 ? 'aberta: curva como uma sela' : 'fechada: curva como a superfície de uma bola';
    // composição
    const ob = Math.min(OMEGA_B, p.om), dm = p.om - ob, de = p.ol, ck = Math.max(0, omegaK(p));
    const parts = [ob, dm, de, ck], total = parts.reduce((s, v) => s + v, 0) || 1;
    mix.forEach((s, i) => { s.style.flexBasis = `${(parts[i] / total) * 100}%`; s.hidden = parts[i] / total < 0.002; });
    const pc = (v: number) => `${fmt((v / total) * 100, 1)}%`;
    const sum = p.om + p.ol;
    const head = Math.abs(sum - 1) < 0.01 ? 'Divisão do total: ' : `Somando tudo, há ${fmt(sum, 2)} vez${sum >= 2 ? 'es' : ''} a quantidade que deixaria o espaço plano. ${sum > 1 ? 'A barra mostra só como esse total se divide: ' : 'O que falta vira curvatura do espaço. Divisão: '}`;
    mixText.textContent = head + `Matéria comum ${pc(ob)} · matéria escura ${pc(dm)} · energia escura ${pc(de)}${ck > 0.003 ? ` · espaço curvo ${pc(ck)}` : ''}`;
    // tensão de Hubble com Ωm e ΩΛ atuais
    if (!bounce) {
      const aPl = ageNow({ ...p, h0: PLANCK.h0 }), aLo = ageNow({ ...p, h0: LOCAL_H0 });
      q(tension, '[data-r-t-cmb]').textContent = `${fmt(aPl, 1)} bilhões de anos`;
      q(tension, '[data-r-t-local]').textContent = `${fmt(aLo, 1)} bilhões de anos`;
    }
    chips.forEach((b) => { const sc = b.dataset.rScenario!; const t = scenarios[sc]; b.setAttribute('aria-pressed', String(!!t && Math.abs(t.om - p.om) < 1e-6 && Math.abs(t.ol - p.ol) < 1e-6 && Math.abs(t.h0 - p.h0) < 0.05)); });
    qa<HTMLButtonElement>(root, '[data-r-h0set]').forEach((b) => b.setAttribute('aria-pressed', String(Math.abs(Number(b.dataset.rH0set) - p.h0) < 0.05)));
    live.textContent = bounce ? 'Com essa receita o Universo nunca teria começado pequeno e quente. Mude a matéria ou a energia escura.' : `Idade: ${duration(age)}. A expansão hoje está ${out.accel.textContent}. Futuro: ${out.fate.textContent}.`;
    setParams({ om: Math.abs(p.om - PLANCK.om) < 1e-6 ? null : String(p.om), ol: Math.abs(p.ol - PLANCK.ol) < 1e-6 ? null : String(p.ol), h0: Math.abs(p.h0 - PLANCK.h0) < 0.05 ? null : String(p.h0) });
  };

  [sOm, sOl, sH0].forEach((s) => s.addEventListener('input', render));
  const tried = new Set<string>();
  chips.forEach((b) => b.addEventListener('click', () => { drawNext = true; set(scenarios[b.dataset.rScenario!]); tried.add(b.dataset.rScenario!); if (tried.size >= 3) root.dispatchEvent(new CustomEvent('cosmos:badge', { bubbles: true, detail: { id: 'receita' } })); }));
  qa<HTMLButtonElement>(root, '[data-r-h0set]').forEach((b) => b.addEventListener('click', () => { sH0.value = b.dataset.rH0set!; render(); }));
  const num = (k: string, lo: number, hi: number): number | null => { const v = Number(getParam(k)); return getParam(k) !== null && Number.isFinite(v) && v >= lo && v <= hi ? v : null; };
  const om = num('om', 0.05, 2), ol = num('ol', 0, 1.5), h0 = num('h0', 50, 90);
  set({ om: om ?? PLANCK.om, ol: ol ?? PLANCK.ol, h0: h0 ?? PLANCK.h0 });
  initGuess(root, { unlocked: om !== null || ol !== null || h0 !== null });
  qa<HTMLButtonElement>(root, '[data-r-go]').forEach((b) => b.addEventListener('click', () => { set(scenarios[b.dataset.rGo!]); }));
}
