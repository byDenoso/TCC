import { describe, expect, it } from 'vitest';
import { A_DEC, T0, T_DEC, bandOf, fmtScale, fmtTemp, peakUm, rulerPos, scaleAt, stepFromParam, tempAt, STEP_TEXT } from '../../src/lib/cmb-journey';

describe('CMB: física do painel', () => {
  it('a luz se solta perto de 3 000 K e chega hoje a 2,7 K', () => {
    expect(T_DEC).toBeGreaterThan(2900);
    expect(T_DEC).toBeLessThan(3050);
    expect(tempAt(1)).toBeCloseTo(T0, 6);
  });
  it('o comprimento de onda cresce na mesma proporção que o fator de escala', () => {
    for (const a of [A_DEC, 0.01, 0.1, 0.5, 1]) expect(peakUm(a) / peakUm(A_DEC)).toBeCloseTo(a / A_DEC, 6);
  });
  it('na emissão o pico está no infravermelho próximo; hoje, em micro-ondas', () => {
    expect(peakUm(A_DEC)).toBeGreaterThan(0.9);
    expect(peakUm(A_DEC)).toBeLessThan(1.1);
    expect(bandOf(peakUm(A_DEC))).toBe('infravermelho');
    expect(bandOf(peakUm(1))).toBe('micro-ondas');
  });
  it('scaleAt vai de 1/1091 até 1 sem voltar', () => {
    expect(scaleAt(0)).toBeCloseTo(A_DEC, 9);
    expect(scaleAt(1)).toBeCloseTo(1, 9);
    let prev = 0;
    for (let k = 0; k <= 1.0001; k += 0.01) { const a = scaleAt(k); expect(a).toBeGreaterThan(prev); prev = a; }
  });
  it('régua do espectro é monótona e limitada', () => {
    expect(rulerPos(0.1)).toBe(0);
    expect(rulerPos(1e6)).toBe(1);
    expect(rulerPos(peakUm(1))).toBeGreaterThan(rulerPos(peakUm(A_DEC)));
  });
  it('formatação legível', () => {
    expect(fmtTemp(T_DEC)).toBe('2 970 K');
    expect(fmtTemp(T0)).toBe('2,7 K');
    expect(fmtScale(1)).toBe('1 (hoje)');
    expect(fmtScale(A_DEC)).toBe('1/1.091');
  });
  it('URL da etapa', () => {
    expect(stepFromParam('2')).toBe(1);
    expect(stepFromParam('9')).toBe(0);
    expect(stepFromParam(null)).toBe(0);
  });
  it('textos não dizem que a cor se estica nem tratam micro-ondas como cor', () => {
    const all = STEP_TEXT.map((s) => Object.values(s).join(' ')).join(' ').toLowerCase();
    expect(all).not.toMatch(/cor se estica|cor esticada|micro-ondas (vermelh|azul|laranj)/);
    expect(all).not.toMatch(/antes da expansão|depois da expansão/);
    expect(all).toContain('380 mil anos');
  });
});
