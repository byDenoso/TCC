import { C_KMS, flat, GYR_PER_INV_H0, omegaK, omegaR, PLANCK } from './cosmology';

export interface ExpansionModel {
  h0: number;
  om: number;
  ode: number;
  w0: number;
  wa: number;
}

export interface ExpansionPoint {
  z: number;
  a: number;
  h: number;
  lookback: number;
  comoving: number;
  luminosity: number;
}

const matterRich = flat(PLANCK.h0, 0.5);
export const EXPANSION_PRESETS = {
  planck: { h0: PLANCK.h0, om: PLANCK.om, ode: PLANCK.ol, w0: -1, wa: 0 },
  dynamic: { h0: PLANCK.h0, om: PLANCK.om, ode: PLANCK.ol, w0: -0.85, wa: 0.65 },
  matter: { h0: matterRich.h0, om: matterRich.om, ode: matterRich.ol, w0: -1, wa: 0 },
} satisfies Record<string, ExpansionModel>;

export const EXPANSION_MAX_Z = 3;
export const EXPANSION_DEFAULT_Z = 1;

export const expansionCurvature = (p: ExpansionModel): number => omegaK({ h0: p.h0, om: p.om, ol: p.ode });

/**
 * Past FLRW expansion over the exhibit domain, 0 ≤ z ≤ 3. H in km/s/Mpc, lookback in Gyr,
 * and distances in Mpc. Radiation follows cosmology.ts. Ωk > 0 is open, Ωk < 0 is closed.
 */
export function expansionHistory(p: ExpansionModel, zMax = EXPANSION_MAX_Z): ExpansionPoint[] {
  const r = omegaR({ h0: p.h0, om: p.om, ol: p.ode });
  const k = expansionCurvature(p);
  const hubbleDistance = C_KMS / p.h0;
  const hubbleTime = GYR_PER_INV_H0 / p.h0;
  const curvatureRoot = Math.sqrt(Math.abs(k));
  const steps = 120;
  const dz = zMax / steps;
  const invE = (z: number): number => {
    const x = 1 + z;
    // w(a) = w₀ + wₐ(1 − a); integration of the continuity equation gives this density factor.
    const de = Math.exp(3 * (1 + p.w0 + p.wa) * Math.log1p(z) - 3 * p.wa * z / x);
    return 1 / Math.sqrt(r * x ** 4 + p.om * x ** 3 + k * x ** 2 + p.ode * de);
  };

  const points: ExpansionPoint[] = [{ z: 0, a: 1, h: p.h0, lookback: 0, comoving: 0, luminosity: 0 }];
  let radial = 0;
  let time = 0;
  let previous = 1;
  let previousTime = 1;
  // Accumulate the two line-of-sight integrals with Simpson's rule on each interval.
  for (let i = 1; i <= steps; i++) {
    const z = i === steps ? zMax : i * dz;
    const midpoint = z - dz / 2;
    const a = 1 / (1 + z);
    const middle = invE(midpoint);
    const end = invE(z);
    const endTime = a * end;
    radial += dz * (previous + 4 * middle + end) / 6;
    time += dz * (previousTime + 4 * middle / (1 + midpoint) + endTime) / 6;
    previous = end;
    previousTime = endTime;

    const transverse = Math.abs(k) < 1e-10
      ? radial
      : (k > 0 ? Math.sinh(curvatureRoot * radial) : Math.sin(curvatureRoot * radial)) / curvatureRoot;
    points.push({
      z, a, h: p.h0 / end,
      lookback: hubbleTime * time,
      comoving: hubbleDistance * radial,
      luminosity: (1 + z) * hubbleDistance * transverse,
    });
  }
  return points;
}

export function expansionPoint(z: number, p: ExpansionModel): ExpansionPoint {
  const history = expansionHistory(p, z);
  return history[z === 0 ? 0 : history.length - 1];
}

export const EXPANSION_PLOT = { width: 340, height: 187, left: 48, right: 318, top: 12, bottom: 139 };
export const EXPANSION_CHARTS = {
  h: {
    name: 'Taxa de expansão',
    unit: 'H(z) · km/s/Mpc',
    xTitle: 'Redshift z',
    xTicks: [0, 1, 2, 3],
    yTicks: [0, 200, 400, 600, 800],
    xy: (p: ExpansionPoint) => [p.z, p.h],
  },
  scale: {
    name: 'Evolução da escala',
    unit: 'Fator de escala a(t)',
    xTitle: 'Tempo em relação a hoje (Gyr)',
    xTicks: [-28, -21, -14, -7, 0],
    yTicks: [0, 0.25, 0.5, 0.75, 1],
    xy: (p: ExpansionPoint) => [-p.lookback, p.a],
  },
  distance: {
    name: 'Distância de luminosidade',
    unit: 'Dₗ(z) · Gpc',
    xTitle: 'Redshift z',
    xTicks: [0, 1, 2, 3],
    yTicks: [0, 15, 30, 45, 60],
    xy: (p: ExpansionPoint) => [p.z, p.luminosity / 1000],
  },
};

export type ExpansionChart = (typeof EXPANSION_CHARTS)[keyof typeof EXPANSION_CHARTS];

export function expansionPlotPosition(chart: ExpansionChart, x: number, y: number): [number, number] {
  const { left, right, top, bottom } = EXPANSION_PLOT;
  const xMin = chart.xTicks[0];
  const xMax = chart.xTicks[chart.xTicks.length - 1];
  const yMax = chart.yTicks[chart.yTicks.length - 1];
  return [left + (right - left) * (x - xMin) / (xMax - xMin), bottom - (bottom - top) * y / yMax];
}

export function expansionPlotPoint(chart: ExpansionChart, point: ExpansionPoint): [number, number] {
  const [x, y] = chart.xy(point);
  return expansionPlotPosition(chart, x, y);
}

export function expansionPlotPath(chart: ExpansionChart, history: ExpansionPoint[]): string {
  return history.map((point, index) => {
    const [x, y] = expansionPlotPoint(chart, point);
    return `${index === 0 ? 'M' : 'L'}${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join('');
}

export const EXPANSION_FIELDS = [
  { key: 'h0', label: 'H₀', help: 'Taxa hoje · km/s/Mpc', min: 50, max: 90, step: 0.1, digits: 1 },
  { key: 'om', label: 'Ωₘ', help: 'Matéria hoje', min: 0.1, max: 0.6, step: 0.005, digits: 3 },
  { key: 'ode', label: 'Ωde', help: 'Energia escura hoje', min: 0, max: 0.9, step: 'any', digits: 3 },
  { key: 'w0', label: 'w₀', help: 'Equação de estado hoje', min: -1.5, max: -0.5, step: 0.05, digits: 2 },
  { key: 'wa', label: 'wₐ', help: 'Variação de w com a escala', min: -0.8, max: 0.8, step: 0.05, digits: 2 },
] as const;

export const EXPANSION_READINGS = [
  { key: 'h', label: 'Taxa de expansão', unit: 'km/s/Mpc', digits: 1 },
  { key: 'lookback', label: 'Tempo de viagem', unit: 'Gyr', digits: 2 },
  { key: 'comoving', label: 'Distância comóvel radial', unit: 'Mpc', digits: 0 },
  { key: 'luminosity', label: 'Distância de luminosidade', unit: 'Mpc', digits: 0 },
] as const;

export function expansionNumber(value: number, digits: number): string {
  const rounded = Math.abs(value) < 0.5 * 10 ** -digits ? 0 : value;
  return rounded.toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits }).replace('-', '−');
}
