import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  corCorpoNegro,
  distanciaLuzKm,
  formatar,
  luminosidadeMesmoRaio,
  massaContida,
  periodoAnos,
  picoWienNm,
  raioSchwarzschildKm,
  razaoAneis,
  redshiftDeEscala,
  temperaturaCmb,
} from '../src/components/viagem/fisica.ts';

const perto = (a: number, b: number, tol: number) => assert.ok(Math.abs(a - b) <= tol, `${a} ≠ ${b} ± ${tol}`);

test('a luz leva 1,28 s até a Lua', () => {
  perto(distanciaLuzKm(1.2822), 384400, 200);
});

test('terceira lei de Kepler: Júpiter e Netuno', () => {
  perto(periodoAnos(5.2), 11.86, 0.05);
  perto(periodoAnos(30.1), 165.1, 0.3);
});

test('anéis de perfil e de frente', () => {
  perto(razaoAneis(0), 0, 1e-12);
  perto(razaoAneis(90), 1, 1e-12);
});

test('Wien e Stefan–Boltzmann para o Sol', () => {
  perto(picoWienNm(5772), 502, 1);
  perto(luminosidadeMesmoRaio(2 * 5772), 16, 1e-9);
});

test('horizonte de Sagitário A* em unidades astronômicas', () => {
  perto(raioSchwarzschildKm(4.3e6) / 149597870.7, 0.0849, 0.0005);
});

test('massa dentro da órbita do Sol na Via Láctea', () => {
  // 220 km/s a 8 kpc: cerca de 9 × 10¹⁰ massas solares
  perto(massaContida(8, 220) / 1e10, 9.0, 0.1);
});

test('redshift da luz emitida em a = 0,5 e temperatura da radiação de fundo', () => {
  perto(redshiftDeEscala(0.5), 1, 1e-12);
  perto(temperaturaCmb(1089), 2970.8, 0.5);
});

test('cor de corpo negro: estrelas frias avermelhadas, quentes azuladas', () => {
  const [r1, , b1] = corCorpoNegro(3000);
  const [r2, , b2] = corCorpoNegro(30000);
  assert.ok(r1 > b1);
  assert.ok(b2 > r2);
});

test('formatação brasileira', () => {
  assert.equal(formatar(384400), '384.400');
  assert.equal(formatar(0.5), '0,5');
  assert.match(formatar(9.0e10), /× 10¹⁰$/);
});
