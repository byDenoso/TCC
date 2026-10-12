/** Tipos do domínio. Todo conteúdo vive em src/data/*.json e é tipado aqui. */

export const CHAPTER_IDS = [
  'origem-do-universo',
  'galaxias-e-nebulosas',
  'vida-das-estrelas',
  'sistema-solar',
  'terra-e-atmosfera',
  'misterios-do-cosmos'
] as const;
export type ChapterId = (typeof CHAPTER_IDS)[number];

/** Ordem da jornada principal apresentada na página inicial. */
export const PRIMARY_CHAPTER_IDS = [
  'galaxias-e-nebulosas',
  'origem-do-universo',
  'misterios-do-cosmos'
] as const satisfies readonly ChapterId[];
/** Jornadas suplementares, preservadas no progresso local legado. */
export const EXTRA_CHAPTER_IDS = [
  'vida-das-estrelas',
  'sistema-solar',
  'terra-e-atmosfera'
] as const satisfies readonly ChapterId[];

export type ChapterTrack = 'primary' | 'extra';

export const PLANET_IDS = ['mercurio', 'venus', 'terra', 'marte', 'jupiter', 'saturno', 'urano', 'netuno'] as const;
export type PlanetId = (typeof PLANET_IDS)[number];
export type PlanetType = 'Rochoso' | 'Gigante gasoso' | 'Gigante de gelo';

/**
 * Convenção única (NASA/NSSDCA Planetary Fact Sheet, unidades métricas):
 * raio EQUATORIAL; rotação SIDERAL com sinal (negativo = retrógrada); período orbital TROPICAL.
 */
export interface Planet {
  id: PlanetId;
  name: string;
  type: PlanetType;
  description: string;
  composition: string;
  /** km, equatorial */
  radius: number;
  /** kg */
  mass: number;
  /** m/s², equatorial, inclui efeito da rotação; gigantes: nível de 1 bar */
  gravity: number;
  /** °C. Rochosos: média de superfície. Gigantes: atmosfera a 1 bar */
  temperature: number;
  /** UA, semieixo maior */
  distance: number;
  /** dias terrestres, período orbital tropical */
  orbit: number;
  /** horas, rotação sideral; negativo = retrógrada */
  rotation: number;
  atmosphere: string;
  temperatureNote: string;
  fact: string;
}

export type EraVisual = 'cosmic' | 'star' | 'galaxy' | 'solar' | 'earth' | 'mystery';
export interface Era {
  id: string;
  title: string;
  short: string;
  time: string;
  text: string;
  chapter: ChapterId;
  visual: EraVisual;
  evidence: string;
}

export interface Question {
  id: string;
  chapter: ChapterId;
  question: string;
  answers: string[];
  /** índice em `answers` */
  correct: number;
  explanation: string;
}

export interface Term {
  term: string;
  definition: string;
  example: string;
  chapter: ChapterId;
}

export interface Source {
  title: string;
  href: string;
}

export type EvidenceKind = 'Observação' | 'Modelo físico' | 'Questão aberta';

export interface LessonSection {
  id: string;
  evidence: EvidenceKind;
  title: string;
  body: string;
  more: string | null;
  deep: string | null;
  equation?: { formula: string; caption: string; layer: 'more' | 'deep' };
  sources: Source[];
}

export interface Chapter {
  id: ChapterId;
  /** minutos de leitura */
  minutes: number;
  title: string;
  intro: string;
  idea: string;
  learningGoal?: string;
  experience?: 'scale' | 'expansion' | 'evidence';
  concept: 'cosmic' | 'solar' | 'mystery' | null;
  photo?: { alt: string; caption: string };
  sections: LessonSection[];
  refs: Source[];
  refNote: string;
  refHeading: string;
  checkTitle: string;
}

export interface ChapterRow {
  id: ChapterId;
  title: string;
  teaser: string;
  summary: string;
  aside: string;
}

export interface ImageCredit {
  kind: string;
  title: string;
  caption: string;
  credit: string;
  href: string;
  alt: string;
}

export type DepthLevel = 'essential' | 'more' | 'deep';
