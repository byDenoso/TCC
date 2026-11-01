import { describe, expect, test } from 'vitest';
import {
  CMB_TODAY_K, LIGHT_RELEASE_GROWTH, angularSpeed, blackbodyRgb, galaxyField, growthAt, hubbleSample, isVisibleNm, lightName,
  lightTemperatureK, peakNm, planckShape, redshiftOf, rotationSpeed, seenFrom, seeded, slopeThroughOrigin, stretchNm, visibleGlow, wavelengthRgb, wrap
} from '../../src/lib/motion-lab';

describe('Luz esticada pelo espaço', () => {
  test('o comprimento de onda cresce na mesma proporção que o espaço', () => {
    expect(stretchNm(440, 1)).toBe(440);
    expect(stretchNm(440, 2)).toBe(880);
    expect(redshiftOf(1)).toBe(0);
    expect(redshiftOf(1.7)).toBeCloseTo(0.7, 12);
  });
  test('faixa visível e nomes de cor', () => {
    expect(isVisibleNm(379)).toBe(false);
    expect(isVisibleNm(380)).toBe(true);
    expect(isVisibleNm(750)).toBe(true);
    expect(isVisibleNm(751)).toBe(false);
    expect(lightName(440)).toBe('violeta');
    expect(lightName(470)).toBe('azul');
    expect(lightName(650)).toBe('vermelha');
    expect(lightName(900)).toBe('infravermelha');
    expect(lightName(1_063_000)).toBe('de micro-ondas');
  });
  test('cores: azul tem mais azul que vermelho, vermelho o inverso; fora da faixa é preto', () => {
    const [r1, , b1] = wavelengthRgb(470);
    const [r2, , b2] = wavelengthRgb(680);
    expect(b1).toBeGreaterThan(r1);
    expect(r2).toBeGreaterThan(b2);
    expect(wavelengthRgb(900)).toEqual([0, 0, 0]);
    for (let nm = 380; nm <= 750; nm += 5) for (const v of wavelengthRgb(nm)) { expect(v).toBeGreaterThanOrEqual(0); expect(v).toBeLessThanOrEqual(255); }
  });
});

describe('Expansão sem centro', () => {
  const field = galaxyField();
  test('é determinística e tem 77 galáxias', () => {
    expect(field).toHaveLength(77);
    expect(galaxyField()).toEqual(field);
  });
  test('a diferença é periódica: qualquer galáxia é vista no mesmo quadriculado', () => {
    expect(wrap(5.6, 11)).toBeCloseTo(-5.4, 12);
    expect(wrap(-5.6, 11)).toBeCloseTo(5.4, 12);
    expect(wrap(5.4, 11)).toBeCloseTo(5.4, 12);
    expect(wrap(0.3, 11)).toBeCloseTo(0.3, 12);
    expect(wrap(0.3 + 22, 11)).toBeCloseTo(0.3, 9);
  });
  test('todas as distâncias crescem pelo mesmo fator, de qualquer observador', () => {
    for (const o of [field[0], field[38], field[60]]) for (const p of field.slice(5, 40)) {
      const [x1, y1] = seenFrom(p, o, 1);
      const [x2, y2] = seenFrom(p, o, 2.2);
      if (Math.hypot(x1, y1) < 1e-9) continue;
      expect(Math.hypot(x2, y2) / Math.hypot(x1, y1)).toBeCloseTo(2.2, 9);
    }
  });
  test('a galáxia mais longe se afasta mais depressa (velocidade ∝ distância)', () => {
    const o = field[38];
    const d = (p: typeof o) => Math.hypot(...seenFrom(p, o, 1));
    const sorted = field.filter((p) => p !== o).sort((a, b) => d(a) - d(b));
    const near = sorted[0], far = sorted[sorted.length - 1];
    const speed = (p: typeof o) => Math.hypot(...seenFrom(p, o, 1.5)) - Math.hypot(...seenFrom(p, o, 1));
    expect(speed(far)).toBeGreaterThan(speed(near));
  });
});

describe('Diagrama de Hubble', () => {
  const sample = hubbleSample();
  test('é determinístico e tem 28 pontos positivos dentro do gráfico', () => {
    expect(sample).toHaveLength(28);
    expect(hubbleSample()).toEqual(sample);
    for (const p of sample) { expect(p.mpc).toBeGreaterThan(0); expect(p.mpc).toBeLessThanOrEqual(400); expect(p.kms).toBeGreaterThan(0); }
  });
  test('a reta pela origem recupera a taxa de expansão usada (≈ 70)', () => {
    expect(slopeThroughOrigin(sample)).toBeGreaterThan(62);
    expect(slopeThroughOrigin(sample)).toBeLessThan(78);
  });
  test('dobro da distância ≈ dobro da velocidade, em média', () => {
    const near = sample.filter((p) => p.mpc < 150), far = sample.filter((p) => p.mpc > 250);
    const mean = (a: typeof near, k: 'mpc' | 'kms') => a.reduce((s, p) => s + p[k], 0) / a.length;
    expect(mean(far, 'kms') / mean(near, 'kms')).toBeCloseTo(mean(far, 'mpc') / mean(near, 'mpc'), 0);
  });
  test('sem pontos, a inclinação é zero', () => { expect(slopeThroughOrigin([])).toBe(0); });
});

describe('Luz do começo esfriando', () => {
  test('o controle vai de hoje (×1) à luz mais antiga (×1.100), em escala logarítmica', () => {
    expect(growthAt(0)).toBe(1);
    expect(growthAt(1)).toBeCloseTo(LIGHT_RELEASE_GROWTH, 6);
    expect(growthAt(0.5)).toBeCloseTo(Math.sqrt(LIGHT_RELEASE_GROWTH), 6);
    expect(growthAt(-3)).toBe(1);
    expect(growthAt(7)).toBeCloseTo(LIGHT_RELEASE_GROWTH, 6);
  });
  test('temperaturas de hoje e da luz mais antiga', () => {
    expect(lightTemperatureK(1)).toBeCloseTo(CMB_TODAY_K, 9);
    expect(lightTemperatureK(1100)).toBeGreaterThan(2900);
    expect(lightTemperatureK(1100)).toBeLessThan(3100);
  });
  test('pico (Wien): ~0,97 µm a 3.000 K e ~1,06 mm a 2,725 K', () => {
    expect(peakNm(3000)).toBeCloseTo(965.9, 0);
    expect(peakNm(CMB_TODAY_K)).toBeGreaterThan(1.05e6);
    expect(peakNm(CMB_TODAY_K)).toBeLessThan(1.08e6);
  });
  test('curva de Planck normalizada: máximo 1 no pico, nunca acima de 1, cai nos dois lados', () => {
    for (const T of [2.725, 300, 3000, 5800]) {
      expect(planckShape(peakNm(T), T)).toBeCloseTo(1, 9);
      for (let nm = 300; nm <= 3e6; nm *= 1.3) { const v = planckShape(nm, T); expect(v).toBeGreaterThanOrEqual(0); expect(v).toBeLessThanOrEqual(1 + 1e-9); }
      expect(planckShape(peakNm(T) / 4, T)).toBeLessThan(0.5);
      expect(planckShape(peakNm(T) * 8, T)).toBeLessThan(0.5);
    }
  });
  test('cor e brilho: laranja-claro a 3.000 K, invisível abaixo de ~800 K', () => {
    const [r, g, b] = blackbodyRgb(3000);
    expect(r).toBe(255);
    expect(g).toBeGreaterThan(b);
    expect(r).toBeGreaterThan(g);
    expect(visibleGlow(3000)).toBe(1);
    expect(visibleGlow(2.725)).toBe(0);
    expect(visibleGlow(700)).toBe(0);
    expect(visibleGlow(1500)).toBeGreaterThan(0);
    expect(visibleGlow(1500)).toBeLessThan(1);
  });
});

describe('Curva de rotação da galáxia', () => {
  const radii = Array.from({ length: 40 }, (_, i) => 0.05 + (0.95 * i) / 39);
  const speeds = (dark: number) => radii.map((r) => rotationSpeed(r, dark));
  test('só com a matéria visível, a borda gira bem mais devagar que o pico', () => {
    const v = speeds(0);
    expect(v[v.length - 1]).toBeLessThan(0.8 * Math.max(...v));
  });
  test('com o halo, a rapidez fica quase constante da metade da galáxia até a borda', () => {
    const outer = radii.map((r, i) => ({ r, v: speeds(1)[i] })).filter((p) => p.r >= 0.3);
    const vs = outer.map((p) => p.v);
    expect((Math.max(...vs) - Math.min(...vs)) / Math.max(...vs)).toBeLessThan(0.12);
  });
  test('mais matéria escura nunca diminui a rapidez', () => {
    for (const r of radii) { expect(rotationSpeed(r, 1)).toBeGreaterThanOrEqual(rotationSpeed(r, 0.5)); expect(rotationSpeed(r, 0.5)).toBeGreaterThanOrEqual(rotationSpeed(r, 0)); }
  });
  test('estrelas de dentro dão voltas mais depressa que as de fora', () => {
    for (const d of [0, 0.5, 1]) expect(angularSpeed(0.15, d)).toBeGreaterThan(angularSpeed(0.9, d));
  });
  test('valores finitos até no centro', () => { for (const d of [0, 1]) expect(Number.isFinite(rotationSpeed(0, d))).toBe(true); });
});

describe('Gerador determinístico', () => {
  test('mesma semente, mesma sequência; valores em [0, 1)', () => {
    const a = seeded(3), b = seeded(3);
    for (let i = 0; i < 50; i++) { const x = a(); expect(x).toBe(b()); expect(x).toBeGreaterThanOrEqual(0); expect(x).toBeLessThan(1); }
  });
});
