/** Relações físicas das estações da viagem. Unidades no nome de cada função. */

export const C_KM_S = 299792.458;
export const KM_POR_UA = 149597870.7;
export const MLY_POR_MPC = 3.26156;
export const G_KPC = 4.30091e-6; // kpc (km/s)² por massa solar
export const RS_SOL_KM = 2.95325; // raio de Schwarzschild de uma massa solar
export const T_SOL = 5772; // K
export const T_CMB = 2.7255; // K
export const H0 = 70; // km/s/Mpc, valor de referência da estação

/** Distância percorrida pela luz no vácuo, em km. */
export const distanciaLuzKm = (segundos: number) => C_KM_S * segundos;

/** Terceira lei de Kepler para o Sol: período em anos para semieixo em UA. */
export const periodoAnos = (semieixoUA: number) => semieixoUA ** 1.5;

/** Escala visual comprimida das órbitas (a mesma do construtor no Blender). */
export const raioOrbitaVisual = (semieixoUA: number) => 2.6 + 3.2 * semieixoUA ** 0.55;

/** Razão entre os eixos da elipse que os anéis projetam, para inclinação B em graus. */
export const razaoAneis = (graus: number) => Math.sin((graus * Math.PI) / 180);

/** Lei de Wien: pico de emissão em nanômetros. */
export const picoWienNm = (kelvin: number) => 2.897771955e6 / kelvin;

/** Luminosidade relativa ao Sol para o mesmo raio (Stefan–Boltzmann). */
export const luminosidadeMesmoRaio = (kelvin: number) => (kelvin / T_SOL) ** 4;

/** Raio de Schwarzschild em km para massa em massas solares. */
export const raioSchwarzschildKm = (massasSolares: number) => RS_SOL_KM * massasSolares;

/** Massa contida numa órbita circular (M = v² r / G), em massas solares. */
export const massaContida = (raioKpc: number, vKmS: number) => (vKmS * vKmS * raioKpc) / G_KPC;

/** Tempo que a luz leva para atravessar uma distância em Mpc, em milhões de anos. */
export const travessiaMilhoesAnos = (mpc: number) => mpc * MLY_POR_MPC;

/** Desvio para o vermelho da luz emitida quando o fator de escala valia a. */
export const redshiftDeEscala = (a: number) => 1 / a - 1;

/** Lei de Hubble com H0 de referência, em km/s. */
export const velocidadeHubble = (mpc: number) => H0 * mpc;

/** Temperatura da radiação de fundo no desvio z, em K. */
export const temperaturaCmb = (z: number) => T_CMB * (1 + z);

/** Cor aproximada de um corpo negro (ajuste de Tanner Helland), canais sRGB 0–1. */
export function corCorpoNegro(kelvin: number): [number, number, number] {
  const t = kelvin / 100;
  const r = t <= 66 ? 255 : 329.698727446 * Math.pow(t - 60, -0.1332047592);
  const g = t <= 66 ? 99.4708025861 * Math.log(t) - 161.1195681661 : 288.1221695283 * Math.pow(t - 60, -0.0755148492);
  const b = t >= 66 ? 255 : t <= 19 ? 0 : 138.5177312231 * Math.log(t - 10) - 305.0447927307;
  const clamp = (x: number) => Math.min(1, Math.max(0, x / 255));
  return [clamp(r), clamp(g), clamp(b)];
}

const inteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
const dois = new Intl.NumberFormat('pt-BR', { maximumSignificantDigits: 3 });

/** Número com três algarismos e potência de dez em notação brasileira quando necessário. */
export function formatar(x: number): string {
  if (!Number.isFinite(x)) return '–';
  const abs = Math.abs(x);
  if (abs !== 0 && (abs >= 1e7 || abs < 0.01)) {
    const e = Math.floor(Math.log10(abs));
    const m = x / 10 ** e;
    return `${dois.format(m)} × 10${sobrescrito(e)}`;
  }
  return abs >= 1000 ? inteiro.format(x) : dois.format(x);
}

function sobrescrito(n: number) {
  const mapa: Record<string, string> = { '-': '⁻', '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹' };
  return String(n).split('').map((c) => mapa[c]).join('');
}

const REFERENCIAS: [number, string][] = [
  [12, 'estrela de nêutrons'],
  [6371, 'raio da Terra'],
  [384400, 'órbita da Lua'],
  [696340, 'raio do Sol'],
  [5.79e7, 'órbita de Mercúrio'],
  [1.496e8, 'órbita da Terra'],
  [7.785e8, 'órbita de Júpiter'],
  [4.495e9, 'órbita de Netuno'],
];

/**
 * Círculo de comparação para o horizonte de um buraco negro de massa M (em massas solares).
 * Escolhe a maior referência conhecida que caiba entre 1,8 e 12 raios do horizonte (a região do
 * disco); sem nenhuma, a maior potência de dez em km nesse intervalo. Assim, conforme a massa
 * cresce, o círculo encolhe de forma contínua até dar lugar à referência seguinte.
 * `razao` é o raio do círculo em raios do horizonte.
 */
export function referenciaHorizonte(massasSolares: number): { rotulo: string; raioKm: number; razao: number } {
  const rs = raioSchwarzschildKm(massasSolares);
  const cabem = REFERENCIAS.filter(([r]) => r / rs >= 1.8 && r / rs <= 12);
  if (cabem.length) {
    const [r, rotulo] = cabem[cabem.length - 1];
    return { rotulo, raioKm: r, razao: r / rs };
  }
  const k = Math.floor(Math.log10(12 * rs));
  const r = 10 ** k;
  return { rotulo: `círculo de ${formatar(r)} km`, raioKm: r, razao: r / rs };
}
