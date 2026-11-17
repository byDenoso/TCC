import { u } from './url';

/** Preserve the synthetic CMB and early-universe teaching diagrams. */
const rendered = new Set(['earth','solar-system','milky-way','galaxies','cosmic-web','star']);
export function scenePlate(id: string, small = false): string {
  return u(`/${rendered.has(id) ? 'renders' : 'posters'}/${id}${small ? '-small' : ''}.webp`);
}
