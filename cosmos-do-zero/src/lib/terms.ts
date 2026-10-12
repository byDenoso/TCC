import type { Term } from '../types';

export type Segment = { text: string } | { text: string; term: Term; index: number };

const EXTRA: Record<string, string[]> = {
  'Radiação cósmica de fundo (CMB)': ['radiação cósmica de fundo', 'CMB'],
  'Big Bang quente': ['Big Bang quente', 'Big Bang'],
  'Expansão do Universo': ['expansão do Universo', 'expansão'],
  'Ano-luz': ['anos-luz', 'ano-luz'],
  'Galáxia': ['galáxias', 'galáxia'],
  'Nebulosa': ['nebulosas', 'nebulosa'],
  'Fusão nuclear': ['fusão nuclear'],
  'Supernova': ['supernovas', 'supernova'],
  'Exoplaneta': ['exoplanetas', 'exoplaneta'],
  'Anã branca': ['anãs brancas', 'anã branca'],
  'Estrela de nêutrons': ['estrelas de nêutrons', 'estrela de nêutrons']
};
const variants = (t: Term): string[] => (EXTRA[t.term] ?? [t.term]).slice().sort((a, b) => b.length - a.length);
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * Marca a primeira aparição de cada termo do dicionário num texto. `used` é compartilhado entre
 * os trechos da mesma página, para não repetir o mesmo termo a cada parágrafo.
 */
export function linkTerms(text: string, terms: Term[], used: Set<string>): Segment[] {
  const found: { start: number; end: number; term: Term; index: number }[] = [];
  terms.forEach((term, index) => {
    if (used.has(term.term)) return;
    for (const v of variants(term)) {
      const re = new RegExp(`(?<![\\p{L}\\p{N}-])${esc(v)}(?![\\p{L}\\p{N}])`, 'iu');
      const m = re.exec(text);
      if (m && !found.some((f) => m.index < f.end && m.index + m[0].length > f.start)) {
        found.push({ start: m.index, end: m.index + m[0].length, term, index });
        used.add(term.term);
        break;
      }
    }
  });
  found.sort((a, b) => a.start - b.start);
  const out: Segment[] = [];
  let pos = 0;
  for (const f of found) {
    if (f.start > pos) out.push({ text: text.slice(pos, f.start) });
    out.push({ text: text.slice(f.start, f.end), term: f.term, index: f.index });
    pos = f.end;
  }
  if (pos < text.length) out.push({ text: text.slice(pos) });
  return out;
}
