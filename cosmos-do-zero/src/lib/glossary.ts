import type { ChapterId, Term } from '../types';
import { normalize } from './format';

/** Outras formas como um iniciante procura o mesmo termo. */
export const SYNONYMS: Record<string, string[]> = {
  'Ano-luz': ['ano luz', 'anos luz', 'distancia da luz'],
  'Redshift': ['desvio para o vermelho', 'desvio ao vermelho', 'luz esticada', 'avermelhamento'],
  'Radiação cósmica de fundo (CMB)': ['fundo cosmico', 'radiacao de fundo', 'luz mais antiga', 'micro-ondas', 'cmb'],
  'Big Bang quente': ['big bang', 'explosao inicial', 'comeco do universo', 'origem do universo'],
  'Expansão do Universo': ['universo crescendo', 'espaco crescendo', 'expansao'],
  'Matéria escura': ['materia invisivel'],
  'Energia escura': ['aceleracao da expansao'],
  'Fusão nuclear': ['fusao', 'reacao nuclear', 'energia das estrelas'],
  'Unidade astronômica': ['ua', 'distancia terra sol'],
  'Horizonte de eventos': ['buraco negro'],
  'Exoplaneta': ['planeta extrassolar', 'planeta de outra estrela'],
  'Zona habitável': ['zona habitavel', 'cachinhos dourados', 'agua liquida'],
  'Magnetosfera': ['campo magnetico', 'escudo magnetico'],
  'Efeito estufa': ['aquecimento', 'gases estufa'],
  'Gravidade': ['gravitacao', 'atracao'],
  'Nebulosa': ['nuvem de gas', 'nuvem de poeira'],
  'Universo observável': ['horizonte', 'borda do universo', 'limite do universo']
};

/** Acentos, caixa, hífens, travessões, pontuação e espaços repetidos não importam. */
export function searchNormalize(s: string): string {
  return normalize(s).replace(/[‐-―\-_/.,;:!?()[\]"'“”‘’«»]+/g, ' ').replace(/\s+/g, ' ').trim();
}

/** Distância de edição (Levenshtein), limitada a `max` para ser barata. */
export function editDistance(a: string, b: string, max = 3): number {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    let best = i;
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      best = Math.min(best, cur[j]);
    }
    if (best > max) return max + 1;
    prev = cur;
  }
  return prev[b.length];
}

const tolerance = (len: number): number => (len >= 7 ? 2 : len >= 4 ? 1 : 0);

function haystack(t: Term): { text: string; words: string[]; title: string; titles: string[] } {
  const names = [t.term, ...(SYNONYMS[t.term] ?? [])].map(searchNormalize);
  const text = searchNormalize(`${names.join(' ')} ${t.definition} ${t.example}`);
  return { text, words: [...new Set(text.split(' '))], title: names[0], titles: names };
}

/** Uma palavra da busca casa se aparece no texto, começa uma palavra ou tem um erro de digitação pequeno. */
function tokenHits(token: string, h: ReturnType<typeof haystack>): boolean {
  if (h.text.includes(token)) return true;
  const tol = tolerance(token.length);
  return tol > 0 && h.words.some((w) => w.length >= 3 && (editDistance(token, w, tol) <= tol || (w.length > token.length && editDistance(token, w.slice(0, token.length), tol) <= tol && token.length >= 5)));
}

/** Índices dos termos que casam com a busca e com o capítulo, se houver. */
export function filterTerms(terms: Term[], query: string, chapter: ChapterId | '' = ''): number[] {
  const q = searchNormalize(query);
  const compact = q.replace(/ /g, '');
  const tokens = q ? q.split(' ') : [];
  const out: number[] = [];
  terms.forEach((t, i) => {
    if (chapter && t.chapter !== chapter) return;
    if (!q) { out.push(i); return; }
    const h = haystack(t);
    if (h.titles.some((n) => n.replace(/ /g, '').includes(compact)) || tokens.every((tok) => tokenHits(tok, h))) out.push(i);
  });
  return out;
}

/** Quando nada casa: os termos com nome mais parecido com o que foi digitado. */
export function suggestTerms(terms: Term[], query: string, n = 3): number[] {
  const q = searchNormalize(query);
  if (!q) return [];
  const score = (t: Term): number => {
    const names = [t.term, ...(SYNONYMS[t.term] ?? [])].map(searchNormalize);
    let best = Infinity;
    for (const name of names) {
      best = Math.min(best, editDistance(q, name, 12) / Math.max(q.length, name.length));
      for (const w of name.split(' ')) for (const tok of q.split(' ')) if (w.length >= 3) best = Math.min(best, editDistance(tok, w, 6) / Math.max(tok.length, w.length) + 0.1);
    }
    return best;
  };
  return terms.map((t, i) => [i, score(t)] as const).filter(([, s]) => s < 0.6).sort((a, b) => a[1] - b[1]).slice(0, n).map(([i]) => i);
}

export const countLabel = (n: number): string => `${n} ${n === 1 ? 'termo' : 'termos'}`;
