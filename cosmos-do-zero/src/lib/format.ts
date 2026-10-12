const SUP = '⁰¹²³⁴⁵⁶⁷⁸⁹';
const nf = new Map<number, Intl.NumberFormat>();
/** Número em pt-BR com no máximo `digits` casas. */
export function format(n: number, digits = 1): string {
  let f = nf.get(digits);
  if (!f) nf.set(digits, (f = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: digits })));
  return f.format(n).replace('-', '\u2212');
}
/** Massa em notação científica: 5,97 × 10²⁴ kg */
export function mass(n: number): string {
  const e = Math.floor(Math.log10(n));
  const sup = String(e).replace(/\d/g, (d) => SUP[Number(d)]);
  return `${format(n / 10 ** e, 3)} × 10${sup} kg`;
}
/** Remove acentos e caixa para busca tolerante. */
export function normalize(s: string): string {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLocaleLowerCase('pt-BR');
}
export const pad2 = (n: number): string => String(n).padStart(2, '0');
export const chapterHref = (id: string): string => `/capitulos/${id}/`;
