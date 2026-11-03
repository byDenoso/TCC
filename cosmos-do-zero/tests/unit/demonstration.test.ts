import { describe, expect, it } from 'vitest';
import { advanceDemonstration, type DemonstrationState, type DemonstrationSpec } from '../../src/lib/demonstration';

const initial: DemonstrationState = { value: 0, phase: 0, hold: 0 };
const spec = { kind: 'stages' as const, min: 0, max: 2, duration: 1000, hold: 500 };
const run = (time: number, dt: number, config: DemonstrationSpec = spec) => {
  let state = { ...initial };
  for (let t = 0; t < time; t += dt) state = advanceDemonstration(state, Math.min(dt, time - t), config);
  return state;
};
describe('demonstração guiada', () => {
  it('mostra uma etapa inteira antes de avançar', () => {
    expect(run(1200, 20)).toEqual({ value: 0, phase: 1, hold: 200 });
    expect(run(1600, 20)).toEqual({ value: 1, phase: 0.1, hold: 0 });
  });
  it('repete as etapas depois de mostrar a última', () => {
    const state = run(4600, 20);
    expect(state.value).toBe(0);
    expect(state.phase).toBeCloseTo(0.1);
  });
  it('percorre escolhas, permitindo comparar todas as opções', () => {
    const state = run(3100, 20, { ...spec, kind: 'choice' });
    expect(state.value).toBe(2);
  });
  it('anima uma grandeza continuamente e espera no máximo', () => {
    const config = { ...spec, kind: 'sweep' as const, min: 1, max: 3 };
    let state: DemonstrationState = { value: 1, phase: 0, hold: 0 };
    state = advanceDemonstration(state, 750, config);
    expect(state.value).toBeCloseTo(2.5);
    state = advanceDemonstration(state, 500, config);
    expect(state.value).toBe(3);
    expect(state.hold).toBeCloseTo(250);
    state = advanceDemonstration(state, 350, config);
    expect(state.value).toBeCloseTo(1.2);
  });
  it('mantém o mesmo resultado em diferentes taxas de quadros', () => {
    const a = run(7700, 1000 / 60), b = run(7700, 1000 / 120);
    expect(a.value).toBe(b.value);
    expect(a.phase).toBeCloseTo(b.phase, 8);
    expect(a.hold).toBeCloseTo(b.hold, 8);
  });
  it('não avança com tempo zero e preserva o valor de cenas temporais', () => {
    expect(advanceDemonstration(initial, 0, spec)).toEqual(initial);
    const state = advanceDemonstration({ value: 1.7, phase: 0, hold: 0 }, 2500, { ...spec, kind: 'time' });
    expect(state.value).toBe(1.7);
  });
});
