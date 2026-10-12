import { describe, expect, test } from 'vitest';
import { chapters } from '../../src/data';
import { MICRO } from '../../src/data/micro';
import { scenes as galaxias } from '../../src/scripts/micro/galaxias';
import { scenes as origem } from '../../src/scripts/micro/origem';
import { scenes as misterios } from '../../src/scripts/micro/misterios';
import { scenes as estrelas } from '../../src/scripts/micro/estrelas';
import { cometPosition, scenes as sistema } from '../../src/scripts/micro/sistema';
import { scenes as terra } from '../../src/scripts/micro/terra';

describe('Cobertura das subseções da escola', () => {
  const factories = { ...galaxias, ...origem, ...misterios, ...estrelas, ...sistema, ...terra };
  const sections = chapters.flatMap((c) => c.sections.map((s) => s.id));
  test('cada uma das 36 subseções tem conteúdo e um mecanismo próprio', () => {
    expect(sections).toHaveLength(36);
    expect(Object.keys(MICRO).sort()).toEqual(sections.slice().sort());
    expect(Object.keys(factories).sort()).toEqual(sections.slice().sort());
  });
  for (const id of sections) test(id, () => {
    const spec = MICRO[id];
    expect(spec.ask.trim().length).toBeGreaterThan(10);
    expect(spec.alt.trim().length).toBeGreaterThan(30);
    expect(spec.limit.trim().length).toBeGreaterThan(15);
    for (const q of [spec.guess, spec.check]) {
      expect(q.right).toBeGreaterThanOrEqual(0);
      expect(q.right).toBeLessThan(q.options.length);
      expect(Number.isInteger(q.right)).toBe(true);
      expect(new Set(q.options).size).toBe(q.options.length);
      expect(q.why.trim().length).toBeGreaterThan(10);
    }
    const c = spec.control;
    if (c.kind === 'range') {
      expect(c.min).toBeLessThan(c.max);
      expect(c.value).toBeGreaterThanOrEqual(c.min);
      expect(c.value).toBeLessThanOrEqual(c.max);
      expect(c.step).toBeGreaterThan(0);
    } else expect(c.options.length).toBeGreaterThan(1);
    const scene = factories[id]();
    expect(typeof scene.init).toBe('function');
    expect(typeof scene.draw).toBe('function');
  });
});

describe('Movimento do cometa em torno do foco desenhado', () => {
  const sun = [260 - 190 * 0.8, 135];
  const velocity = (f: number) => {
    const dt = 1e-6, before = cometPosition(f - dt), after = cometPosition(f + dt);
    return [(after[0] - before[0]) / (2 * dt), (after[1] - before[1]) / (2 * dt)];
  };
  test('fica mais rápido perto do Sol e mais lento longe', () => {
    const peri = cometPosition(0), apo = cometPosition(0.5);
    expect(Math.hypot(peri[0] - sun[0], peri[1] - sun[1])).toBeCloseTo(38, 6);
    expect(Math.hypot(apo[0] - sun[0], apo[1] - sun[1])).toBeCloseTo(342, 6);
    expect(Math.hypot(...velocity(0)) / Math.hypot(...velocity(0.5))).toBeCloseTo(9, 4);
  });
  test('varre áreas iguais em tempos iguais em torno do mesmo Sol', () => {
    const areaRate = (f: number) => {
      const p = cometPosition(f), v = velocity(f);
      return Math.abs((p[0] - sun[0]) * v[1] - (p[1] - sun[1]) * v[0]);
    };
    const reference = areaRate(0);
    for (const f of [0.05, 0.1, 0.2, 0.35, 0.5, 0.7, 0.85]) expect(areaRate(f) / reference).toBeCloseTo(1, 5);
  });
  test('completa uma órbita contínua e periódica', () => {
    expect(cometPosition(1)).toEqual(cometPosition(0));
    expect(cometPosition(1.1)[0]).toBeCloseTo(cometPosition(0.1)[0], 6);
  });
});
