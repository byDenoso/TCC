import { describe, expect, it } from 'vitest';
import { luminosityInSuns, projectHR } from '../../src/lib/hr';

describe('diagrama H–R', () => {
  it('normaliza a referência solar', () => {
    expect(luminosityInSuns(5772, 1)).toBe(1);
  });

  it('multiplica a luminosidade por 16 ao dobrar a temperatura com raio fixo', () => {
    expect(luminosityInSuns(11544, 1)).toBe(16);
  });

  it('multiplica a luminosidade por 4 ao dobrar o raio com temperatura fixa', () => {
    expect(luminosityInSuns(5772, 2)).toBe(4);
  });

  it('dispõe as estrelas mais quentes à esquerda e as mais luminosas acima', () => {
    expect(projectHR(20000, 100).x).toBeLessThan(projectHR(4000, 1).x);
    expect(projectHR(20000, 100).y).toBeLessThan(projectHR(4000, 1).y);
  });

  it('dá o mesmo espaçamento a décadas sucessivas de luminosidade', () => {
    const bright = projectHR(5772, 10).y;
    const solar = projectHR(5772, 1).y;
    const faint = projectHR(5772, 0.1).y;
    expect(solar - bright).toBeCloseTo(faint - solar);
  });
});
