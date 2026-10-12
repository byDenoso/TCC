import type { ChapterId, Term } from '../types';
import { normalize } from './format';

/** Índices dos termos que casam com a busca (acentos e caixa ignorados) e com o capítulo, se houver. */
export function filterTerms(terms: Term[], query: string, chapter: ChapterId | '' = ''): number[] {
  const q = normalize(query.trim());
  const out: number[] = [];
  terms.forEach((t, i) => {
    if (chapter && t.chapter !== chapter) return;
    if (!q || normalize(`${t.term} ${t.definition} ${t.example}`).includes(q)) out.push(i);
  });
  return out;
}
export const countLabel = (n: number): string => `${n} ${n === 1 ? 'termo' : 'termos'}`;
