/**
 * Única porta de entrada do conteúdo. Hoje lê JSON local, em build.
 * Se um CMS/API for adotado, troque apenas este arquivo (mantendo os tipos de ../types).
 */
import planetsJson from './planets.json';
import erasJson from './eras.json';
import questionsJson from './questions.json';
import termsJson from './terms.json';
import chaptersJson from './chapters.json';
import siteJson from './site.json';
import { EXTRA_CHAPTER_IDS, PRIMARY_CHAPTER_IDS, type Chapter, type ChapterId, type ChapterRow, type ChapterTrack, type Era, type ImageCredit, type Planet, type Question, type Source, type Term } from '../types';

export { CHAPTER_IDS, EXTRA_CHAPTER_IDS, PRIMARY_CHAPTER_IDS } from '../types';

export const chapterOrder: readonly ChapterId[] = [...PRIMARY_CHAPTER_IDS, ...EXTRA_CHAPTER_IDS];

export const planets = planetsJson as Planet[];
export const eras = erasJson as Era[];
export const questions = questionsJson as Question[];
export const terms = termsJson as Term[];
const byChapterOrder = <T extends { id: ChapterId }>(items: T[]): T[] =>
  items.slice().sort((a, b) => chapterOrder.indexOf(a.id) - chapterOrder.indexOf(b.id));

export const chapters = byChapterOrder(chaptersJson as unknown as Chapter[]);
export const chapterRows = siteJson.rows as ChapterRow[];
export const primaryChapters = chapters.filter((chapter) => (PRIMARY_CHAPTER_IDS as readonly ChapterId[]).includes(chapter.id));
export const extraChapters = chapters.filter((chapter) => (EXTRA_CHAPTER_IDS as readonly ChapterId[]).includes(chapter.id));
export const primaryRows = byChapterOrder(chapterRows.filter((row) => (PRIMARY_CHAPTER_IDS as readonly ChapterId[]).includes(row.id)));
export const extraRows = byChapterOrder(chapterRows.filter((row) => (EXTRA_CHAPTER_IDS as readonly ChapterId[]).includes(row.id)));
export const imageCredits = siteJson.credits as ImageCredit[];
export const referenceIndex = siteJson.refIndex as Source[];

export const getChapter = (id: string): Chapter | undefined => chapters.find((c) => c.id === id);
export const chapterTrack = (id: ChapterId): ChapterTrack =>
  (PRIMARY_CHAPTER_IDS as readonly ChapterId[]).includes(id) ? 'primary' : 'extra';
export const trackChapterIds = (id: ChapterId): readonly ChapterId[] =>
  chapterTrack(id) === 'primary' ? PRIMARY_CHAPTER_IDS : EXTRA_CHAPTER_IDS;
export const chapterNumber = (id: ChapterId): number => trackChapterIds(id).indexOf(id) + 1;
export const adjacentChapters = (id: ChapterId): { prev?: Chapter; next?: Chapter } => {
  const ids = trackChapterIds(id);
  const i = ids.indexOf(id);
  return { prev: i > 0 ? getChapter(ids[i - 1]) : undefined, next: i < ids.length - 1 ? getChapter(ids[i + 1]) : undefined };
};
export const chapterQuestions = (id: ChapterId): Question[] => questions.filter((q) => q.chapter === id);
export const chapterTitleShort: Record<ChapterId, string> = {
  'origem-do-universo': 'Como o Universo evoluiu?',
  'galaxias-e-nebulosas': 'Onde estamos no Universo?',
  'vida-das-estrelas': 'A vida das estrelas',
  'sistema-solar': 'O Sistema Solar',
  'terra-e-atmosfera': 'Terra e atmosfera',
  'misterios-do-cosmos': 'Como sabemos disso?'
};
/** Foto oficial associada a cada capítulo (arquivo em src/assets/photos) e o índice do crédito em site.json. */
export const chapterPhotoKey: Partial<Record<ChapterId, 'andromeda-wise' | 'carina-cosmic-cliffs' | 'iss-sunrise'>> = {
  'galaxias-e-nebulosas': 'andromeda-wise',
  'vida-das-estrelas': 'carina-cosmic-cliffs',
  'terra-e-atmosfera': 'iss-sunrise'
};
