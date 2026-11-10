export interface TransitModel {
  planet: number;
  star: number;
  inclination: number;
}

export const TRANSIT_PRESETS = {
  giant: { planet: 10, star: 1, inclination: 90 },
  earth: { planet: 1, star: 1, inclination: 90 },
  grazing: { planet: 10, star: 1, inclination: 84.3 },
  miss: { planet: 10, star: 1, inclination: 82.5 },
} satisfies Record<string, TransitModel>;

const EARTH_IN_SOLAR_RADII = 0.00916;
const ORBIT_IN_SOLAR_RADII = 10;
export const TRANSIT_PHASE_LIMIT = 3;

export function circleOverlapArea(r: number, s: number, d: number): number {
  if (d >= r + s) return 0;
  const smallerDisk = Math.PI * Math.min(r, s) ** 2;
  if (d <= Math.abs(r - s)) return smallerDisk;

  // Sum of the two circular segments on either side of the common chord.
  const acos = (value: number) => Math.acos(Math.max(-1, Math.min(1, value)));
  const rSegment = r ** 2 * acos((d ** 2 + r ** 2 - s ** 2) / (2 * d * r));
  const sSegment = s ** 2 * acos((d ** 2 + s ** 2 - r ** 2) / (2 * d * s));
  const twiceTriangle = Math.sqrt(Math.max(0, (-d + r + s) * (d + r - s) * (d - r + s) * (d + r + s)));
  return Math.max(0, Math.min(smallerDisk, rSegment + sSegment - twiceTriangle / 2));
}

export function transitSnapshot({ planet, star, inclination }: TransitModel, phase: number) {
  const radius = planet * EARTH_IN_SOLAR_RADII;
  const angle = phase * Math.PI / 50;
  const cosInclination = inclination === 90 ? 0 : Math.cos(inclination * Math.PI / 180);
  const x = ORBIT_IN_SOLAR_RADII * Math.sin(angle);
  const y = ORBIT_IN_SOLAR_RADII * cosInclination * Math.cos(angle);
  const distance = Math.hypot(x, y);
  const closest = ORBIT_IN_SOLAR_RADII * Math.abs(cosInclination);
  const loss = Math.cos(angle) > 0 ? circleOverlapArea(star, radius, distance) / (Math.PI * star ** 2) : 0;
  const kind = closest >= star + radius ? 'none' : closest > Math.abs(star - radius) ? 'grazing' : 'full';
  return { x, y, radius, loss, flux: 1 - loss, impact: closest / star, kind } as const;
}

export const TRANSIT_VIEW = {
  geometry: { x: 220, y: 119, solarRadius: 61 },
  chart: { left: 77, right: 412, top: 18, bottom: 122 },
} as const;

export function transitPlotPoint(phase: number, loss: number, scale: number) {
  const { left, right, top, bottom } = TRANSIT_VIEW.chart;
  return [left + (phase / TRANSIT_PHASE_LIMIT + 1) * (right - left) / 2, top + (bottom - top) * loss / scale] as const;
}

export function transitPlot(model: TransitModel) {
  const center = transitSnapshot(model, 0);
  const possibleLoss = (center.radius / model.star) ** 2;
  const order = 10 ** Math.floor(Math.log10(possibleLoss));
  const scale = ([1, 2, 5, 10].find((step) => step * order >= possibleLoss) ?? 10) * order;
  const { x, y, solarRadius } = TRANSIT_VIEW.geometry;
  const points = Array.from({ length: 241 }, (_, index) => {
    const phase = TRANSIT_PHASE_LIMIT * (index / 120 - 1);
    const sample = transitSnapshot(model, phase);
    return {
      sky: [x + sample.x * solarRadius, y + sample.y * solarRadius],
      chart: transitPlotPoint(phase, sample.loss, scale),
    };
  });
  const path = (key: 'sky' | 'chart') => points.map((point, index) =>
    `${index === 0 ? 'M' : 'L'}${point[key][0].toFixed(2)} ${point[key][1].toFixed(2)}`).join('');
  return { center, scale, track: path('sky'), curve: path('chart') };
}

const percent = new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 5 });
export const transitPercent = (fraction: number) => percent.format(fraction);

export const TRANSIT_KIND_LABELS = {
  full: 'Trânsito completo',
  grazing: 'Trânsito rasante',
  none: 'Sem trânsito',
} as const;
