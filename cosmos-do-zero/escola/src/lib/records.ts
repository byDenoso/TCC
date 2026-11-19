import { grade, type Question } from './school.ts';
export type Action = 'open' | 'attempt' | 'favorite' | 'note' | 'assessment' | 'lab';
export type Entry = {
  id: string;
  at: number;
  kind: Action;
  lesson: string;
  value: string;
  correct?: boolean;
  score?: number;
  total?: number;
};
export type ExamItem = { slug: string; exercise: Question };
export function scoreExam(items: ExamItem[], answers: Record<string, string>) {
  return items.reduce((n, i) => n + Number(grade(i.exercise, answers[i.slug])), 0);
}
export function summarize(entries: Entry[], now = Date.now()) {
  const done = new Set<string>(),
    favorites = new Set<string>(),
    notes: Record<string, string> = {},
    due: Record<string, number> = {},
    streaks: Record<string, number> = {};
  let latest = '';
  for (const e of entries) {
    if (e.kind === 'open') latest = e.lesson;
    if (e.kind === 'favorite') {
      if (e.value === 'yes') favorites.add(e.lesson);
      else favorites.delete(e.lesson);
    }
    if (e.kind === 'note') notes[e.lesson] = e.value;
    if (e.kind === 'attempt') {
      if (e.correct) done.add(e.lesson);
      const count = e.correct ? (streaks[e.lesson] ?? 0) + 1 : 0;
      streaks[e.lesson] = count;
      due[e.lesson] = e.at + [0, 1, 3, 7, 21][Math.min(4, count)] * 86400000;
    }
  }
  return {
    done,
    favorites,
    notes,
    latest,
    reviews: Object.keys(due)
      .filter((s) => due[s] <= now)
      .sort((a, b) => due[a] - due[b]),
    attempts: entries.filter((e) => e.kind === 'attempt'),
    assessments: entries.filter((e) => e.kind === 'assessment'),
    due,
  };
}
