import { test } from 'node:test';
import assert from 'node:assert/strict';
import { labs, simulate, orbitUnitsPerAU, threeBodyDiagnostics } from '../src/lib/model.ts';

function close(got: number, expected: number, tolerance = 1e-8) {
  assert.ok(
    Math.abs(got - expected) <= tolerance,
    `${got} differs from ${expected} by more than ${tolerance}`
  );
}
function value(id: string, v: number[]) {
  return simulate(id, v).metric.value;
}

test('Fifteen unique definitions, valid controls, three comparison presets and sources', () => {
  assert.equal(new Set(labs.map((l) => l.id)).size, 15);
  for (const lab of labs) {
    assert.match(lab.reference.url, /^https:\/\//);
    assert.ok(lab.xLabel && lab.yLabel && lab.assumptions.length > 30);
    assert.equal(lab.presets.length, 3);
    assert.equal(lab.parameters.length, 2);
    for (const preset of lab.presets) {
      assert.equal(preset.values.length, lab.parameters.length);
      preset.values.forEach((val, i) => {
        const p = lab.parameters[i];
        assert.ok(val >= p.min && val <= p.max && p.min < p.max && p.step > 0, lab.id);
      });
    }
  }
});

for (const lab of labs)
  test(lab.id + ' · curves, geometry, control limits and presets', () => {
    const [p, q] = lab.parameters;
    const inputs = [
      [p.min, q.min],
      [p.max, q.max],
      [p.min, q.max],
      [p.max, q.min],
      ...lab.presets.map((s) => s.values),
    ];
    for (const values of inputs)
      for (const t of [0, 3.7, 25]) {
        const r = simulate(lab.id, values, t);
        assert.ok(r.points.length >= 24);
        assert.ok(r.dots.length >= 1 && r.segments.length >= 1);
        assert.ok(r.metric.label && r.metric.unit && Number.isFinite(r.metric.value));
        for (const [x, y] of r.points) assert.ok(Number.isFinite(x) && Number.isFinite(y));
        for (let i = 1; i < r.points.length; i++) assert.ok(r.points[i][0] > r.points[i - 1][0], lab.id);
        for (const a of [...r.dots, ...r.segments])
          assert.ok(
            a.every((v, axis) => {
              const center =
                lab.id === 'orbitas' && axis % 3 === 0 ? orbitUnitsPerAU * values[0] * values[1] : 0;
              return Number.isFinite(v) && Math.abs(v + center) < 2.6;
            }),
            lab.id + ' camera extent ' + a
          );
      }
    const base = simulate(lab.id, [p.min, q.min], 1.7);
    for (const v of [
      [p.max, q.min],
      [p.min, q.max],
    ])
      assert.notDeepEqual(simulate(lab.id, v, 1.7), base);
    assert.deepEqual(simulate(lab.id, [], NaN), simulate(lab.id, [p.initial, q.initial], 0));
    assert.deepEqual(simulate(lab.id, [p.min - 20, q.max + 70], 0), simulate(lab.id, [p.min, q.max], 0));
  });

test('Kepler: solar year, P∝a^(3/2), perihelion, aphelion and equal-area motion', () => {
  close(value('orbitas', [1, 0]), 365.2569, 0.0001);
  const atEarth = simulate('orbitas', [1, 0.5]),
    atTwo = simulate('orbitas', [2, 0.5]);
  close(atTwo.metric.value / atEarth.metric.value, Math.sqrt(8));
  close(atEarth.points[0][1], 0.5);
  close(atEarth.points[48][1], 1.5);
  close(atTwo.dots[1][0] / atEarth.dots[1][0], 2);
  const nextFrame = simulate('orbitas', [2, 0.5], 0.1);
  assert.equal(nextFrame.points, atTwo.points);
  assert.notDeepEqual(nextFrame.dots, atTwo.dots);
  const period = atEarth.metric.value / 30;
  const start = atEarth.dots[1],
    after = simulate('orbitas', [1, 0.5], 1e-4).dots[1];
  const ap = simulate('orbitas', [1, 0.5], period / 2).dots[1],
    apAfter = simulate('orbitas', [1, 0.5], period / 2 + 1e-4).dots[1];
  close(start[0] * after[1] - start[1] * after[0], ap[0] * apAfter[1] - ap[1] * apAfter[0], 1e-10);
});
test('Newton: standard surface gravity and inverse-square law', () => {
  close(value('gravitacao', [1, 1]), 9.82025, 0.0001);
  close(value('gravitacao', [1, 2]), value('gravitacao', [1, 1]) / 4);
  close(value('gravitacao', [2, 1]), 2 * value('gravitacao', [1, 1]));
});
test('Three-body Verlet: barycentre, energy, momentum and mutual perturbations', () => {
  for (const [mass, radius] of [
    [1, 3.2],
    [5, 2.2],
    [18, 1.8],
    [20, 1.8],
  ]) {
    const d = threeBodyDiagnostics(mass, radius);
    assert.ok(d.energyError < 4e-6 && d.barycentreDrift < 3e-13 && d.momentumDrift < 3e-13);
    const out = simulate('n-corpos', [mass, radius]);
    close(out.points[0][1], Math.sqrt(1 + radius * radius - 2 * radius * Math.cos(0.85)));
    assert.ok(out.metric.value <= Math.min(...out.points.map((p) => p[1])) + 1e-12);
  }
  const heavy = simulate('n-corpos', [20, 1.8]).points.at(-1)![1];
  const light = simulate('n-corpos', [1, 1.8]).points.at(-1)![1];
  assert.ok(Math.abs(heavy - light) > 0.05);
});
test('Waves: linear superposition, destructive phase and correct speed', () => {
  close(value('ondas', [2, 0]), 0.3);
  close(value('ondas', [2, 90]), Math.SQRT2 * 0.15);
  for (const [, y] of simulate('ondas', [2, 180], 0.73).points) close(y, 0, 2e-14);
  const time0 = simulate('ondas', [2, 0], 0),
    time1 = simulate('ondas', [2, 0], 0.25);
  close(time0.points[0][1], time1.points[8][1]);
});
test('Fields: magnetic radius and cyclotron chord with electric acceleration', () => {
  const out = simulate('campos', [0, 1]),
    E12 = simulate('campos', [12, 1]),
    E24 = simulate('campos', [24, 1]);
  close(out.metric.value, 1.04397, 0.00001);
  close(value('campos', [0, 2]), out.metric.value / 2);
  const end = out.points.at(-1)!,
    t = end[0] / 1e6;
  close(end[1], 2 * out.metric.value * Math.abs(Math.sin(((1e5 / out.metric.value) * t) / 2)));
  const z = ((0.5 * 1.602176634e-19) / 1.67262192595e-27) * 12 * t ** 2;
  close(E12.points.at(-1)![1], Math.hypot(end[1], z));
  close(E24.points.at(-1)![1], Math.hypot(end[1], 2 * z));
});
test('Relativity: proper time and invariant interval at rest and β=0.8', () => {
  close(value('relatividade', [0, 5]), 5);
  close(value('relatividade', [0.8, 5]), 3);
  const [dt, proper] = simulate('relatividade', [0.8, 5]).points.at(-1)!;
  close(proper * proper, dt ** 2 - (0.8 * dt) ** 2);
});
test('Curvature: proper distance agrees with quadrature of radial metric and scales with mass', () => {
  const rs = 2.95325 * 5,
    n = 10000,
    upper = Math.sqrt(2);
  // Integrate after r/rs = 1+s², removing the endpoint square-root singularity.
  let integral = 0;
  for (let j = 0; j < n; j++) integral += (2 * Math.sqrt(1 + (((j + 0.5) * upper) / n) ** 2) * upper) / n;
  close(value('curvatura', [5, 3]), rs * integral, 0.0002);
  close(value('curvatura', [10, 3]), 2 * value('curvatura', [5, 3]));
  close(simulate('curvatura', [5, 3]).points[0][1], 0);
});
test('Thin lens: Einstein ring, mass scaling and off-axis split', () => {
  const ring = value('lentes', [1, 0]);
  close(ring / 2, 1.00896, 0.001);
  close(value('lentes', [4, 0]), 2 * ring);
  close(value('lentes', [1, 2]) ** 2, 4 + ring ** 2);
  const [o, l, s, up, down] = simulate('lentes', [1, 0.5]).dots;
  assert.ok(o[0] < l[0] && l[0] < s[0] && up[1] > 0 && down[1] < 0);
});
test('Black hole: gravitational redshift and outgoing Schwarzschild null ray', () => {
  close(value('buracos-negros', [10, 2]), Math.SQRT2 - 1);
  close(value('buracos-negros', [20, 2]), value('buracos-negros', [10, 2]));
  const out = simulate('buracos-negros', [10, 2], 1);
  const r = (out.dots[1][0] / out.dots[0][0]) * 2;
  close(r + Math.log(r - 1), 3, 4e-8);
  close(simulate('buracos-negros', [20, 2]).points[8][0] / out.points[8][0], 2);
});
test('Hubble: velocity is the selected slope times distance', () => {
  close(value('expansao', [70, 100]), 7000);
  close(value('expansao', [70, 50]), 3500);
  close(value('expansao', [80, 100]), 8000);
});
test('Zel’dovich: comoving mass conserved after applying the Jacobian', () => {
  const out = simulate('estruturas', [0.4, 0.5]);
  close(out.metric.value, 25);
  close(out.points[48][1], 0.25);
  let integral = 0;
  for (let i = 1; i < out.points.length; i++) {
    const [x0, y0] = out.points[i - 1],
      [x1, y1] = out.points[i];
    integral += (x1 - x0) * (1 + (y0 + y1) / 2);
  }
  close(integral, 40, 0.002);
});
test('Rotation: point-mass asymptote, quadratic superposition and circular orbital speed', () => {
  const baryons = value('rotacao', [5, 0]),
    both = value('rotacao', [5, 160]);
  close(both * both - baryons * baryons, (160 ** 2 * 225) / 250);
  close(value('rotacao', [10, 0]) / baryons, Math.SQRT2);
  const outer = simulate('rotacao', [5, 0]).points.at(-1)![1];
  assert.ok(outer > 80 && outer < 84);
});
test('Friedmann: flat ΛCDM age, Einstein–de Sitter limit and Hubble-time scaling', () => {
  close(value('fator-de-escala', [70, 0.3]), 13.467, 0.001);
  close(value('fator-de-escala', [70, 1]), 9.3123, 0.001);
  const dust = simulate('fator-de-escala', [70, 1]);
  close(dust.points[48][1], 0.5 ** (2 / 3));
  close(dust.points.at(-1)![1], 1);
  close(value('fator-de-escala', [90, 0.3]) / value('fator-de-escala', [60, 0.3]), 2 / 3);
});
test('wCDM: Λ, deceleration and separate energy conservation', () => {
  close(value('energia-escura', [-1, 0.7]), -0.55);
  const constant = simulate('energia-escura', [-1, 0.7]).points;
  for (const [, y] of constant) close(y, 0.7);
  const z1 = simulate('energia-escura', [-0.6, 0.7]).points[20];
  close(z1[0], 1);
  close(z1[1], 0.7 * 2 ** 1.2);
  assert.ok(value('energia-escura', [-0.35, 0.1]) > 0);
});
test('CMB monopole: measured-temperature peak, Planck brightness, frequency and T³ scalings', () => {
  const today = simulate('cmb', [2.725, 0]),
    z1 = simulate('cmb', [2.725, 1]);
  close(today.metric.value, 160.2007, 0.001);
  close(today.points[40][0], today.metric.value);
  assert.ok(today.points[40][1] > today.points[39][1] && today.points[40][1] > today.points[41][1]);
  close(today.points[40][1], 383.7, 0.6);
  close(z1.metric.value / today.metric.value, 2);
  close(z1.points[40][1] / today.points[40][1], 8);
});
