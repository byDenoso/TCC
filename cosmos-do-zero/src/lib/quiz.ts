import type { ChapterId, Question } from '../types';

export interface QuizState {
  pool: Question[];
  position: number;
  answered: boolean;
  /** resposta escolhida na pergunta atual */
  choice: number | null;
  /** respostas dadas por id de pergunta */
  history: { id: string; choice: number; correct: boolean }[];
  finished: boolean;
}
export const poolFor = (all: Question[], chapter: ChapterId | '' | undefined): Question[] => all.filter((q) => !chapter || q.chapter === chapter);
export const createQuiz = (pool: Question[]): QuizState => ({ pool, position: 0, answered: false, choice: null, history: [], finished: false });
export const score = (s: QuizState): number => s.history.filter((h) => h.correct).length;
export function answer(s: QuizState, choice: number): QuizState {
  if (s.answered || s.finished) return s;
  const q = s.pool[s.position];
  if (!q || choice < 0 || choice >= q.answers.length) return s;
  return { ...s, answered: true, choice, history: [...s.history, { id: q.id, choice, correct: choice === q.correct }] };
}
export function advance(s: QuizState): QuizState {
  if (s.finished) return createQuiz(s.pool);
  if (!s.answered) return s;
  if (s.position < s.pool.length - 1) return { ...s, position: s.position + 1, answered: false, choice: null };
  return { ...s, finished: true };
}
/** Perguntas erradas, na ordem em que foram respondidas. */
export const missed = (s: QuizState): Question[] => s.history.filter((h) => !h.correct).map((h) => s.pool.find((q) => q.id === h.id)!).filter(Boolean);
export function verdict(total: number, hits: number): string {
  if (total === 0) return '';
  if (hits === total) return 'Todas certas. Agora procure o que ainda pode ser contestado: boas respostas também têm limites.';
  if (hits >= Math.ceil(total * 0.6)) return 'Boa leitura. Revise as ideias das perguntas erradas para fechar as lacunas.';
  return 'Conectar as explicações vale mais que decorar as respostas. Volte aos capítulos para aprofundar as ideias que despertaram dúvidas.';
}
