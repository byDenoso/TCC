/**
 * Cosmologia de Friedmann–Lemaître–Robertson–Walker, sem dependências.
 * Usada pelos instrumentos do Observatório. Tudo é cálculo de modelo (ΛCDM e variações),
 * não dado observacional. H0 em km/s/Mpc, tempos em bilhões de anos (Gyr), distâncias em Mpc.
 *
 *   E(a)² = Ωr a⁻⁴ + Ωm a⁻³ + Ωk a⁻² + ΩΛ ,   Ωk = 1 − Ωm − ΩΛ − Ωr ,   dt = d ln a / (H0 E)
 */
export interface Cosmos { h0: number; om: number; ol: number }

export const C_KMS = 299792.458;
/** 1/H0 em Gyr quando H0 = 1 km/s/Mpc */
export const GYR_PER_INV_H0 = 977.792;
export const GLY_PER_MPC = 3.261564e-3;
/** Ωr h² (fótons + neutrinos sem massa), valor típico do ΛCDM. */
const OR_H2 = 4.18e-5;
export const T_CMB = 2.7255;
export const WIEN_NM_K = 2.897771955e6;
export const HALPHA_NM = 656.28;

/** Parâmetros de referência do modelo ΛCDM plano ajustado pelo Planck 2018 (TT,TE,EE+lowE+lensing). */
export const PLANCK: Cosmos = { h0: 67.4, om: 0.315, ol: 0.685 };
/** Valor local de H0 (escada de distâncias com Cefeidas e supernovas Ia, SH0ES 2022), com o mesmo Ωm. */
export const LOCAL_H0 = 73.04;
/** Fração de matéria comum (bárions), Planck 2018: Ωb ≈ 0,0493. */
export const OMEGA_B = 0.0493;

export const omegaR = (p: Cosmos): number => OR_H2 / (p.h0 / 100) ** 2;
export const omegaK = (p: Cosmos): number => 1 - p.om - p.ol - omegaR(p);
export const E2 = (a: number, p: Cosmos): number => omegaR(p) * a ** -4 + p.om * a ** -3 + omegaK(p) * a ** -2 + p.ol;

/** Universo plano com a matéria escolhida (ΩΛ = 1 − Ωm). */
export const flat = (h0: number, om: number): Cosmos => ({ h0, om, ol: 1 - om });

/** Há um instante em que E² ≤ 0 antes de hoje? Então o modelo não tem Big Bang quente (descartado pelas observações). */
export function hasBounce(p: Cosmos): boolean {
  for (let i = 0; i <= 400; i++) if (E2(Math.exp(-7 + (7 * i) / 400), p) <= 0) return true;
  return false;
}

/** Fator de escala máximo se o Universo recolapsa; null se expande para sempre. */
export function maxScale(p: Cosmos): number | null {
  let prev = 1;
  for (let i = 1; i <= 1200; i++) {
    const a = Math.exp((Math.log(1e4) * i) / 1200);
    if (E2(a, p) <= 0) {
      let lo = prev, hi = a;
      for (let k = 0; k < 60; k++) { const mid = (lo + hi) / 2; if (E2(mid, p) > 0) lo = mid; else hi = mid; }
      return (lo + hi) / 2;
    }
    prev = a;
  }
  return null;
}

/** Integral de Simpson de f em [x0, x1] com n subintervalos (n par). */
function simpson(f: (x: number) => number, x0: number, x1: number, n: number): number {
  const h = (x1 - x0) / n;
  let s = f(x0) + f(x1);
  for (let i = 1; i < n; i++) s += f(x0 + i * h) * (i % 2 ? 4 : 2);
  return (s * h) / 3;
}
const invH0 = (p: Cosmos): number => GYR_PER_INV_H0 / p.h0;
const A_MIN = 1e-9;

/** Idade (Gyr) do Universo quando o fator de escala vale `a` (a=1 → hoje). Válido enquanto a < a_max. */
export function timeAtScale(a: number, p: Cosmos): number {
  const aMax = maxScale(p);
  if (aMax === null || a < aMax * 0.5) return invH0(p) * simpson((x) => 1 / Math.sqrt(E2(Math.exp(x), p)), Math.log(A_MIN), Math.log(a), 900);
  // perto do ponto de retorno: substituição ln a = ln a_max − s², que remove a singularidade
  const L = Math.log(aMax);
  const sOf = (aa: number) => Math.sqrt(Math.max(0, L - Math.log(aa)));
  const sHalf = sOf(aMax * 0.5), sA = sOf(Math.min(a, aMax * (1 - 1e-12)));
  const tHalf = invH0(p) * simpson((x) => 1 / Math.sqrt(E2(Math.exp(x), p)), Math.log(A_MIN), Math.log(aMax * 0.5), 900);
  const g = (s: number) => (s < 1e-9 ? 2 / Math.sqrt(Math.max(1e-30, -dE2(aMax, p) * aMax)) : (2 * s) / Math.sqrt(Math.max(1e-30, E2(Math.exp(L - s * s), p))));
  return tHalf + invH0(p) * simpson(g, sA, sHalf, 600);
}
/** d(E²)/da (derivada numérica) */
const dE2 = (a: number, p: Cosmos): number => (E2(a * (1 + 1e-6), p) - E2(a * (1 - 1e-6), p)) / (2e-6 * a);

export const ageNow = (p: Cosmos): number => timeAtScale(1, p);

export type FateKind = 'crunch' | 'accelerating' | 'decelerating';
export interface Fate { kind: FateKind; q0: number; aMax: number | null; crunchGyr: number | null }
/** Destino: recolapso (Big Crunch) ou expansão para sempre; q0 < 0 = acelerando hoje. */
export function fate(p: Cosmos): Fate {
  const q0 = p.om / 2 + omegaR(p) - p.ol;
  const aMax = maxScale(p);
  if (aMax !== null) {
    const tTurn = timeAtScale(aMax, p);
    return { kind: 'crunch', q0, aMax, crunchGyr: 2 * tTurn };
  }
  return { kind: q0 < 0 ? 'accelerating' : 'decelerating', q0, aMax: null, crunchGyr: null };
}

export interface Curve { t: number[]; a: number[] }
/**
 * Curva a(t), t em Gyr desde o Big Bang. Para modelos em expansão eterna vai até `tEnd`;
 * em recolapso, até o Big Crunch.
 */
export function scaleCurve(p: Cosmos, tEnd: number, n = 700): Curve {
  const aMax = maxScale(p);
  const t: number[] = [0], a: number[] = [0];
  if (aMax === null) {
    // grade em ln a, integração cumulativa trapezoidal refinada
    const x0 = Math.log(1e-6), steps = n * 4;
    const f = (x: number) => 1 / Math.sqrt(E2(Math.exp(x), p));
    let tt = invH0(p) * simpson(f, Math.log(A_MIN), x0, 300);
    let x = x0, prevF = f(x0);
    const dx = (Math.log(300) - x0) / steps;
    t.push(tt); a.push(Math.exp(x0));
    for (let i = 1; i <= steps && tt < tEnd; i++) {
      const xn = x0 + i * dx, fn = f(xn);
      tt += invH0(p) * 0.5 * (prevF + fn) * dx; prevF = fn; x = xn;
      t.push(tt); a.push(Math.exp(x));
    }
    return { t, a };
  }
  const L = Math.log(aMax), s0 = Math.sqrt(L - Math.log(1e-6));
  const g = (s: number) => (2 * s) / Math.sqrt(Math.max(1e-30, E2(Math.exp(L - s * s), p)));
  const steps = n * 2, ds = (s0 - 1e-4) / steps;
  const rise: [number, number][] = [];
  let acc = 0; // tempo medido de trás para frente a partir do ponto de retorno
  let prevG = g(1e-4);
  const pts: [number, number][] = [[0, 1e-4]];
  for (let i = 1; i <= steps; i++) { const s = 1e-4 + i * ds, gs = g(s); acc += invH0(p) * 0.5 * (prevG + gs) * ds; prevG = gs; pts.push([acc, s]); }
  const tTurn = acc;
  for (const [dt, s] of pts) rise.push([tTurn - dt, Math.exp(L - s * s)]);
  rise.reverse();
  t.length = 0; a.length = 0;
  for (const [tt, aa] of rise) { t.push(tt); a.push(aa); }
  for (let i = rise.length - 2; i >= 0; i--) { t.push(2 * tTurn - rise[i][0]); a.push(rise[i][1]); }
  return { t, a };
}

/** Tempo de viagem da luz (Gyr) emitida em z e recebida hoje. */
export const lookbackGyr = (z: number, p: Cosmos): number => ageNow(p) - timeAtScale(1 / (1 + z), p);
/** Idade do Universo (Gyr) quando a luz de redshift z foi emitida. */
export const ageAtRedshift = (z: number, p: Cosmos): number => timeAtScale(1 / (1 + z), p);
/** Distância comóvel (Mpc) ao longo da linha de visada até redshift z (distância "de hoje"). */
export function comovingMpc(z: number, p: Cosmos): number {
  const x1 = Math.log1p(z);
  return (C_KMS / p.h0) * simpson((x) => Math.exp(x) / Math.sqrt(E2(1 / Math.exp(x), p)), 0, x1, 900);
}
/** Frações de densidade (soma 1) em redshift z. */
export function densityFractions(z: number, p: Cosmos): { r: number; m: number; l: number; k: number } {
  const a = 1 / (1 + z), e = E2(a, p);
  return { r: (omegaR(p) * a ** -4) / e, m: (p.om * a ** -3) / e, l: p.ol / e, k: (omegaK(p) * a ** -2) / e };
}
export const cmbTemperature = (z: number): number => T_CMB * (1 + z);
export const wienPeakNm = (kelvin: number): number => WIEN_NM_K / kelvin;
export const observedWavelengthNm = (z: number, restNm = HALPHA_NM): number => restNm * (1 + z);

/** Redshift de matéria–radiação e de matéria–energia escura (ΩΛ = Ωm), para os marcos da escala. */
export const zEquality = (p: Cosmos): number => p.om / omegaR(p) - 1;
export const zLambdaMatter = (p: Cosmos): number => Math.cbrt(p.ol / p.om) - 1;
/** Redshift em que a expansão passou a acelerar (q = 0): (1+z)³ = 2ΩΛ/Ωm, ignorando radiação e curvatura. */
export const zAcceleration = (p: Cosmos): number => Math.cbrt((2 * p.ol) / p.om) - 1;

/** Ajuste por origem: H0 = Σ(v·d) / Σ(d²), com incerteza do erro-padrão do coeficiente. */
export function fitHubble(points: { d: number; v: number }[]): { h0: number; err: number } | null {
  if (points.length < 2) return null;
  const sdd = points.reduce((s, q) => s + q.d * q.d, 0);
  const h0 = points.reduce((s, q) => s + q.d * q.v, 0) / sdd;
  const res = points.reduce((s, q) => s + (q.v - h0 * q.d) ** 2, 0);
  const err = Math.sqrt(res / (points.length - 1) / sdd);
  return { h0, err };
}
