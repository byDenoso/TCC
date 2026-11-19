import test from 'node:test';
import assert from 'node:assert/strict';
import {
  solar,
  trappist,
  orbitRadius,
  orbitPoint,
  facing,
  initialCamera,
  stations,
} from '../src/components/explorer/explorer-data.ts';
import { makeField } from '../src/components/explorer/explorer-geometry.ts';

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
