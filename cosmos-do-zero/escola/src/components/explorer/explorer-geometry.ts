import type { Vec } from './explorer-data';

export const ink = [
  '#a1c0f0',
  '#f9d3a5',
  '#738cee',
  '#6cd1ff',
  '#e7efff',
  '#cca0c5',
  '#ffa777',
] as const;
export interface Grain {
  p: Vec;
  tone: number;
  width: number;
}
export interface Wire {
  a: Vec;
  b: Vec;
}
export interface Field {
  grains: Grain[];
  wires: Wire[];
}

function seeded(seed: number) {
  let state = seed >>> 0;
  return () => {
    state = (Math.imul(1664525, state) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}
export const webBoxSide = 4;
const fields = new Map<string, Field>();

export function makeField(id: string): Field {
  const cached = fields.get(id);
  if (cached) return cached;
  const rnd = seeded(
    ({ orion: 92, m31: 517, virgo: 309, teia: 792 } as Record<string, number>)[id] ?? 5
  );
  const n = () => Math.sqrt(-2 * Math.log(Math.max(1e-9, rnd()))) * Math.cos(2 * Math.PI * rnd());
  const f: Field = { grains: [], wires: [] };
  const put = (p: Vec, tone: number, width: number) => f.grains.push({ p, tone, width });
  if (id === 'orion') {
    // Séries de condensações ao redor de uma cavidade central.
    for (let i = 0; i < 3400; i++) {
      const filament = i % 5,
        t = rnd() * 2 - 1;
      const x = t * 2.65 + n() * 0.12;
      const rolled = Math.sin(t * 3.2 + filament * 0.5);
      const y = rolled * (0.68 + 0.1 * filament) + n() * 0.23;
      const z = Math.cos(t * 4 + filament * 0.94) * 0.81 + n() * 0.33;
      const cool = filament < 2 || x + y > 1.1;
      put([x, y, z], cool ? (rnd() > 0.48 ? 3 : 2) : rnd() > 0.48 ? 5 : 6, 2.2 + rnd() * 4.8);
    }
    [
      [-0.23, 0.17, 0.21],
      [0.07, 0.14, 0.02],
      [-0.06, -0.07, 0.14],
      [0.19, -0.03, 0.1],
    ].forEach((p) => put(p as Vec, 4, 8));
  } else if (id === 'm31') {
    for (let i = 0; i < 5300; i++) {
      const bulge = rnd() < 0.28;
      if (bulge) {
        const radius = Math.pow(rnd(), 1.65) * 0.7,
          phi = rnd() * Math.PI * 2,
          ct = rnd() * 2 - 1,
          st = Math.sqrt(1 - ct * ct);
        put(
          [radius * st * Math.cos(phi), radius * ct * 0.57, radius * st * Math.sin(phi)],
          rnd() < 0.72 ? 1 : 4,
          1 + rnd() * 3.1
        );
      } else {
        const radius = 0.24 + Math.pow(rnd(), 0.62) * 2.6;
        const phase = 1.9 * Math.log(radius + 0.08) + (i % 2) * Math.PI + n() * (0.14 + 0.05 * radius);
        const tone = radius < 0.85 ? 1 : rnd() < 0.42 ? 3 : rnd() < 0.45 ? 2 : 4;
        put(
          [radius * Math.cos(phase), n() * (0.055 + 0.018 * radius), radius * Math.sin(phase)],
          tone,
          0.85 + rnd() * 2.45
        );
      }
    }
  } else if (id === 'virgo') {
    for (let i = 0; i < 230; i++) {
      const p: Vec = i === 0 ? [0, 0, 0] : [n() * 0.95, n() * 0.56, n() * 0.82];
      const inner = i === 0 ? 0.5 : 0.017 + Math.pow(rnd(), 3) * 0.1;
      const tilt = rnd() * 3.14,
        spin = rnd() * 3.14;
      const count = i === 0 ? 440 : 8 + Math.round(inner * 125);
      for (let j = 0; j < count; j++) {
        const x = n() * inner,
          y = n() * inner * 0.42,
          z = n() * inner * 0.26;
        put(
          [
            p[0] + x * Math.cos(spin) + y * Math.sin(spin),
            p[1] - x * Math.sin(spin) * Math.sin(tilt) + z,
            p[2] + y * Math.cos(tilt) - x * Math.sin(spin) * Math.cos(tilt),
          ],
          i === 0 ? (rnd() < 0.5 ? 1 : 4) : i % 4 === 0 ? 2 : 0,
          i === 0 ? 2.5 + rnd() * 3.5 : 1.3 + rnd() * 2.6
        );
      }
    }
  } else if (id === 'teia') {
    const knots: Vec[] = [];
    for (let i = 0; i < 55; i++)
      knots.push([(rnd() - 0.5) * webBoxSide, (rnd() - 0.5) * webBoxSide, (rnd() - 0.5) * webBoxSide]);
    const seen = new Set<string>();
    knots.forEach((p, i) => {
      const closest = knots
        .map((q, k) => ({ q, k, d: Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]) }))
        .filter((x) => x.k !== i)
        .sort((a, b) => a.d - b.d)
        .slice(0, 3);
      for (const { q, k } of closest) {
        const key = [Math.min(i, k), Math.max(i, k)].join('-');
        if (seen.has(key)) continue;
        seen.add(key);
        f.wires.push({ a: p, b: q });
        const amplitude = 0.01 + rnd() * 0.1;
        for (let j = 0; j < 38; j++) {
          const t = rnd(),
            bend = Math.sin(t * Math.PI),
            scatter = 0.015 + bend * 0.028;
          put(
            [
              p[0] + (q[0] - p[0]) * t + n() * scatter,
              p[1] + (q[1] - p[1]) * t + bend * amplitude + n() * scatter,
              p[2] + (q[2] - p[2]) * t + n() * scatter,
            ],
            rnd() < 0.2 ? 3 : 2,
            1.1 + rnd() * 1.85
          );
        }
      }
      for (let j = 0; j < 23; j++)
        put(
          [p[0] + n() * 0.06, p[1] + n() * 0.06, p[2] + n() * 0.06],
          i % 4 === 0 ? 1 : 4,
          1.4 + rnd() * 2.35
        );
    });
  }
  if (id === 'teia')
    f.grains = f.grains.filter(({ p }) => p.every((value) => Math.abs(value) <= webBoxSide / 2));
  fields.set(id, f);
  return f;
}

const rand = seeded(851);
export const sky = Array.from({ length: 105 }, () => ({
  x: rand() * 700,
  y: rand() * 390,
  r: 0.4 + rand() ** 3 * 1.1,
  o: 0.18 + rand() * 0.66,
}));
