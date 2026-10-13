/** Demonstrações calculadas: unidades explícitas, sem ajuste a dados observacionais. */
export const G_SI = 6.67430e-11;
export const C_SI = 299792458;
export const AU_M = 149597870700;
export const SOLAR_MASS_KG = 1.98847e30;
export const YEAR_S = 365.25 * 86400;
/** Terceira lei de Kepler para dois corpos, a em AU e massas em massas solares. */
export function orbitalPeriodYears(aAU: number, primaryMass = 1, secondaryMass = 0): number {
  if (!(aAU>0 && primaryMass>0 && secondaryMass>=0)) throw new RangeError('Órbita exige a>0 e massas válidas.');
  return 2*Math.PI*Math.sqrt((aAU*AU_M)**3/(G_SI*(primaryMass+secondaryMass)*SOLAR_MASS_KG))/YEAR_S;
}
/** Raio do horizonte Schwarzschild, sem rotação/carga, em km. Não é tamanho da sombra. */
export const horizonKm = (solarMass: number): number => 2*G_SI*solarMass*SOLAR_MASS_KG/C_SI**2/1000;
/** Lente fina pontual; distâncias angulares em metros, resultado em radianos. */
export function einsteinAngle(massKg: number, dLensM: number, dSourceM: number, dLensSourceM: number): number {
  // D_A não é monótona em z. Ordem fonte/lente deve ser validada pelo chamador em redshift.
  if (!(massKg>0 && dLensM>0 && dSourceM>0 && dLensSourceM>0)) throw new RangeError('Geometria da lente inválida.');
  return Math.sqrt(4*G_SI*massKg/C_SI**2*dLensSourceM/(dLensM*dSourceM));
}
/** Coordenadas em unidades do raio angular de Einstein; lente na origem. */
export function lensSource(thetaX: number, thetaY: number): [number,number] {
  const r2=thetaX**2+thetaY**2;
  if(r2<1e-12)return [Infinity,Infinity];
  return [thetaX*(1-1/r2),thetaY*(1-1/r2)];
}
export function pointImages(beta: number): [number,number] {
  const q=Math.sqrt(beta*beta+4); return [(beta+q)/2,(beta-q)/2];
}
