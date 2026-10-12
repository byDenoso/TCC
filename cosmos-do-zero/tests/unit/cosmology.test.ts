import { describe, expect, it } from 'vitest';
import { PLANCK, ageAtRedshift, ageNow, cmbTemperature, comovingMpc, densityFractions, fate, fitHubble, flat, hasBounce, lookbackGyr, maxScale, observedWavelengthNm, scaleCurve, wienPeakNm, zAcceleration, zEquality, zLambdaMatter } from '../../src/lib/cosmology';

const near = (v: number, ref: number, tol: number) => expect(Math.abs(v - ref)).toBeLessThanOrEqual(tol);

describe('cosmologia FLRW', () => {
  it('idade do ΛCDM do Planck ≈ 13,8 Gyr', () => near(ageNow(PLANCK), 13.8, 0.06));
  it('Einstein–de Sitter: idade = (2/3)/H0', () => near(ageNow({ h0: 70, om: 1, ol: 0 }), (2 / 3) * (977.792 / 70), 0.03));
  it('H0 maior → Universo mais jovem', () => expect(ageNow({ ...PLANCK, h0: 73 })).toBeLessThan(ageNow(PLANCK)));
  it('tempo de viagem da luz em z=1 ≈ 7,9 Gyr', () => near(lookbackGyr(1, PLANCK), 7.9, 0.15));
  it('distância comóvel até o fundo cósmico ≈ 13,9 Gpc', () => near(comovingMpc(1089.9, PLANCK) / 1000, 13.9, 0.2));
  it('recombinação (z≈1090) ocorre ≈ 372 mil anos após o início', () => near(ageAtRedshift(1089.9, PLANCK) * 1e6, 372, 8));
  it('igualdade matéria–radiação em z ≈ 3400', () => near(zEquality(PLANCK), 3400, 80));
  it('matéria = energia escura em z ≈ 0,3', () => near(zLambdaMatter(PLANCK), 0.295, 0.01));
  it('a aceleração começa em z ≈ 0,63', () => near(zAcceleration(PLANCK), 0.633, 0.01));
  it('frações somam 1 e hoje ≈ 31,5% matéria / 68,5% Λ', () => {
    const f = densityFractions(0, PLANCK);
    near(f.r + f.m + f.l + f.k, 1, 1e-9); near(f.m, 0.315, 0.002); near(f.l, 0.685, 0.002);
  });
  it('em z=1089 domina matéria e radiação ≈ 0,1–0,2 (Λ desprezível)', () => {
    const f = densityFractions(1089, PLANCK);
    expect(f.l).toBeLessThan(1e-8); expect(f.r).toBeGreaterThan(0.1); expect(f.r).toBeLessThan(0.3);
  });
  it('temperatura do CMB e lei de Wien', () => {
    near(cmbTemperature(0), 2.7255, 1e-9); near(cmbTemperature(1089), 2970, 5);
    near(wienPeakNm(cmbTemperature(1089)), 976, 3);
  });
  it('Hα em z=2 chega em ≈ 1969 nm', () => near(observedWavelengthNm(2), 1968.84, 0.01));
});

describe('destino do Universo', () => {
  it('Planck: expansão eterna acelerada', () => { const f = fate(PLANCK); expect(f.kind).toBe('accelerating'); expect(f.q0).toBeLessThan(0); expect(maxScale(PLANCK)).toBeNull(); });
  it('só matéria plana: desacelera para sempre', () => expect(fate({ h0: 70, om: 1, ol: 0 }).kind).toBe('decelerating'));
  it('matéria fechada Ωm=2: Big Crunch em π·Ωm/(H0 (Ωm−1)^1,5)', () => {
    const f = fate({ h0: 70, om: 2, ol: 0 });
    expect(f.kind).toBe('crunch');
    near(f.crunchGyr!, (Math.PI * 2 * 977.792) / 70, 0.015 * 87.8);
  });
  it('detecta modelo sem Big Bang (ΩΛ alto, pouca matéria)', () => { expect(hasBounce({ h0: 70, om: 0.1, ol: 1.4 })).toBe(true); expect(hasBounce(PLANCK)).toBe(false); });
  it('curva a(t) chega a 1 na idade de hoje e é monótona na expansão', () => {
    const c = scaleCurve(PLANCK, 40); const age = ageNow(PLANCK);
    const i = c.t.findIndex((t) => t >= age);
    near(c.a[i], 1, 0.01);
    for (let k = 1; k < c.a.length; k++) expect(c.a[k]).toBeGreaterThanOrEqual(c.a[k - 1]);
  });
  it('curva do recolapso é simétrica e termina em ~0', () => {
    const p = { h0: 70, om: 2, ol: 0 }; const c = scaleCurve(p, 200);
    expect(c.a.at(-1)!).toBeLessThan(1e-3);
    near(c.t.at(-1)!, fate(p).crunchGyr!, 1);
  });
  it('universo plano com Ωm=0,3 equivale a ΩΛ=0,7', () => near(flat(70, 0.3).ol, 0.7, 1e-12));
});

describe('ajuste de Hubble', () => {
  it('recupera H0 de dados exatos', () => {
    const r = fitHubble([50, 120, 200, 310].map((d) => ({ d, v: 70 * d })))!;
    near(r.h0, 70, 1e-9); near(r.err, 0, 1e-9);
  });
  it('precisa de ≥ 2 pontos', () => expect(fitHubble([{ d: 1, v: 70 }])).toBeNull());
});

import { linkTerms } from '../../src/lib/terms';
describe('termos no texto', () => {
  const terms = [{ term: 'Galáxia', definition: 'd', example: 'e', chapter: 'galaxias-e-nebulosas' }, { term: 'Ano-luz', definition: 'd', example: 'e', chapter: 'galaxias-e-nebulosas' }] as never[];
  it('marca só a primeira ocorrência, com plural e sem quebrar palavras', () => {
    const used = new Set<string>();
    const seg = linkTerms('As galáxias ficam a milhões de anos-luz; outra galáxia também.', terms, used);
    const marked = seg.filter((s) => 'term' in s).map((s) => s.text);
    expect(marked).toEqual(['galáxias', 'anos-luz']);
    expect(seg.map((s) => s.text).join('')).toBe('As galáxias ficam a milhões de anos-luz; outra galáxia também.');
    expect(linkTerms('Uma galáxia.', terms, used).every((s) => !('term' in s))).toBe(true);
  });
});
