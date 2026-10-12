// Curvas de rotação didáticas (km/s). Funções puras, sem DOM.

/** Velocidade só da massa visível: sobe no centro, cai como Kepler depois de r≈20. */
export const vLum = (r: number): number => (r < 20 ? r * 3.6 : 72 * Math.sqrt(20 / r));

/** Halo pseudo-isotérmico: v² = V0²·(1 − (rc/r)·atan(r/rc)). Massa não negativa, então nunca reduz a velocidade. */
export const vHalo = (r: number, rc = 12, V0 = 62): number =>
  r <= 0 ? 0 : V0 * Math.sqrt(Math.max(0, 1 - (rc / r) * Math.atan(r / rc)));

/** Soma quadrática: visível + halo. Como as componentes se somam em v², vTotal ≥ cada uma. */
export const vTotal = (r: number): number => Math.sqrt(vLum(r) ** 2 + vHalo(r) ** 2);
