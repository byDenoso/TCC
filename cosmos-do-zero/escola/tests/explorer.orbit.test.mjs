import test from 'node:test';
import assert from 'node:assert/strict';
import {
  solar,
  trappist,
  orbitRadius,
  orbitalSymbols,
  orbitPoint,
  facing,
  initialCamera,
  stations,
} from '../src/components/explorer/explorer-data.ts';
import { makeField, webBoxSide } from '../src/components/explorer/explorer-geometry.ts';

for (const system of [solar, trappist]) {
  const outer = system.at(-1).a;
  for (const planet of system) {
    test(`Órbita circular, período e projeção de ${planet.name}`, () => {
      for (const linear of [true, false]) {
        const start = orbitPoint(planet, outer, linear, 0);
        const opposite = orbitPoint(planet, outer, linear, planet.days / 2);
        const end = orbitPoint(planet, outer, linear, planet.days);
        assert(Math.hypot(...start.map((x, i) => x - end[i])) < 1e-11);
        assert(Math.hypot(...start.map((x, i) => x + opposite[i])) < 1e-11);
        assert(Math.abs(Math.hypot(...start) - orbitRadius(planet.a, outer, linear)) < 1e-12);
        assert(Math.abs(Math.hypot(...start) - Math.hypot(...facing(start, initialCamera))) < 1e-12);
      }
    });
  }
}

for (const station of stations.slice(2)) {
  test(`Campo ilustrativo de ${station.name}`, () => {
    const field = makeField(station.id);
    assert(field.grains.length >= 100);
    assert(field.grains.every((g) => g.p.every(Number.isFinite)));
  });
}

test('Glifos solares separados nas escalas linear, logarítmica e de planetas rochosos', () => {
  for (const orbits of [solar, solar.slice(0, 4), trappist]) {
    for (const linear of [true, false]) {
      const sizes = orbitalSymbols(orbits, linear);
      const outer = orbits.at(-1).a;
      const tracks = orbits.map((p) => orbitRadius(p.a, outer, linear));
      assert(sizes.star + sizes.bodies[0] < tracks[0]);
      for (let i = 1; i < tracks.length; i++) {
        assert(sizes.bodies[i - 1] + sizes.bodies[i] < tracks[i] - tracks[i - 1]);
      }
    }
  }
});

test('A teia ocupa um cubo isotrópico e os traçadores são limitados ao recorte', () => {
  const { grains, wires } = makeField('teia');
  const nodes = wires.flatMap(({ a, b }) => [a, b]);
  for (let axis = 0; axis < 3; axis++) {
    const positions = nodes.map((point) => point[axis]);
    assert(Math.max(...positions) - Math.min(...positions) > 0.85 * webBoxSide);
    assert(grains.every(({ p }) => Math.abs(p[axis]) <= webBoxSide / 2));
  }
});
