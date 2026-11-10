import { AU_M, G_SI, orbitalPeriodYears, SOLAR_MASS_KG, YEAR_S } from './physics';

export const TAU = 2 * Math.PI;
export const JUPITER_IN_SOLAR_MASSES = 0.0009546;
const DAYS_PER_YEAR = YEAR_S / 86400;
const CIRCULAR_SPEED_AT_1_AU = Math.sqrt(G_SI * SOLAR_MASS_KG / AU_M) / 1000;
export const ORBIT_VIEW = { cx: 300, cy: 164, pixelsPerAu: 86 } as const;

export function orbitPeriod(semimajorAxis: number, totalMass = 1): number {
  return DAYS_PER_YEAR * orbitalPeriodYears(semimajorAxis, totalMass);
}

/** Órbita relativa kepleriana de dois corpos pontuais. Distâncias em UA, massa total em massas solares. */
export function orbitState(a: number, e: number, meanAnomaly: number, totalMass = 1) {
  let eccentricAnomaly = meanAnomaly;
  for (let i = 0; i < 12; i++) {
    eccentricAnomaly -= (eccentricAnomaly - e * Math.sin(eccentricAnomaly) - meanAnomaly)
      / (1 - e * Math.cos(eccentricAnomaly));
  }
  const x = a * (Math.cos(eccentricAnomaly) - e);
  const y = a * Math.sqrt(1 - e * e) * Math.sin(eccentricAnomaly);
  const radius = Math.hypot(x, y);
  const speed = CIRCULAR_SPEED_AT_1_AU * Math.sqrt(totalMass * (2 / radius - 1 / a));
  const specificEnergy = -(CIRCULAR_SPEED_AT_1_AU ** 2) * totalMass / (2 * a);
  return { x, y, radius, speed, specificEnergy, eccentricAnomaly };
}

export function orbitPoint(x: number, y: number) {
  return [ORBIT_VIEW.cx + x * ORBIT_VIEW.pixelsPerAu, ORBIT_VIEW.cy - y * ORBIT_VIEW.pixelsPerAu] as const;
}

export function orbitSectorPath(a: number, e: number, center: number): string {
  const edge = Array.from({ length: 33 }, (_, i) => {
    const { x, y } = orbitState(a, e, center + TAU * (i / 32 - 0.5) / 8);
    return orbitPoint(x, y).map((value) => value.toFixed(2)).join(' ');
  });
  return `M${ORBIT_VIEW.cx} ${ORBIT_VIEW.cy} L${edge.join(' L')} Z`;
}
