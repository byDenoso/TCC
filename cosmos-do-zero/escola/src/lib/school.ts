export const levels = [
  {
    name: 'Fundamentos',
    blurb: 'Aprenda a medir, representar e testar uma ideia.',
    image: 'escala.webp',
    subjects: [
      'Matemática básica',
      'Álgebra e funções',
      'Geometria e trigonometria',
      'Introdução à Física',
      'Método científico',
    ],
  },
  {
    name: 'Física Clássica',
    blurb: 'Descreva movimentos, forças, campos e ondas.',
    image: 'orbita.webp',
    subjects: [
      'Cinemática',
      'Dinâmica',
      'Gravitação',
      'Energia e momento',
      'Termodinâmica',
      'Eletromagnetismo',
      'Ondas e óptica',
    ],
  },
  {
    name: 'Astronomia',
    blurb: 'Leia a luz de planetas, estrelas e galáxias.',
    image: 'm51.webp',
    subjects: [
      'Sistema Solar',
      'Mecânica orbital',
      'Física estelar',
      'Evolução das estrelas',
      'Buracos negros',
      'Galáxias',
      'Observação astronômica',
    ],
  },
  {
    name: 'Física Moderna',
    blurb: 'Investigue espaço, tempo e matéria em condições extremas.',
    image: 'plasma.webp',
    subjects: [
      'Relatividade especial',
      'Relatividade geral',
      'Física quântica',
      'Física nuclear',
      'Partículas fundamentais',
    ],
  },
  {
    name: 'Cosmologia',
    blurb: 'Reconstrua a história da expansão a partir da luz.',
    image: 'cmb.webp',
    subjects: [
      'Expansão do Universo',
      'Lei de Hubble-Lemaître',
      'Modelo ΛCDM',
      'Radiação cósmica de fundo',
      'Formação de estruturas',
      'Matéria escura',
      'Energia escura',
      'História térmica do Universo',
    ],
  },
  {
    name: 'Cosmologia Avançada',
    blurb: 'Derive os modelos e confronte suas previsões com dados.',
    image: 'rede.webp',
    subjects: [
      'Equações de Einstein',
      'Métrica FLRW',
      'Equações de Friedmann',
      'Perturbações cosmológicas',
      'Espectro de potência',
      'Oscilações acústicas bariônicas',
      'Inferência bayesiana',
      'Tensões cosmológicas',
      'Modelos além de ΛCDM',
    ],
  },
];
export type Question = {
  kind: 'numeric' | 'choice' | 'graph' | 'experiment';
  prompt: string;
  answer: number;
  tolerance: number;
  unit: string;
  choices?: string[];
  feedback: string;
};
export type Lesson = {
  slug: string;
  level: number;
  subject: string;
  order: number;
  title: string;
  objective: string;
  summary: string;
  lab: string;
  reference: { name: string; url: string };
  exercise: Question;
  graph: { xLabel: string; yLabel: string; points: [number, number][]; caption: string };
};
export type Card = Pick<Lesson, 'slug' | 'level' | 'subject' | 'order' | 'title' | 'objective'>;
export function grade(q: Question, input: unknown) {
  if (typeof input !== 'string' && typeof input !== 'number') return false;
  const raw = String(input).trim().replace(',', '.');
  if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(raw)) return false;
  const n = Number(raw);
  return (
    Number.isFinite(n) &&
    Math.abs(n - q.answer) <= q.tolerance + Number.EPSILON * Math.max(1, Math.abs(q.answer)) * 4
  );
}
const numberFormat = new Intl.NumberFormat('pt-BR', { maximumSignificantDigits: 4 });
export function compact(n: number) {
  return numberFormat.format(n);
}
export function canon(s: string) {
  return s
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9λ]/g, '');
}
export function rank(l: Card) {
  return (
    l.level * 10000 +
    levels[l.level - 1].subjects.findIndex((s) => canon(s) === canon(l.subject)) * 10 +
    l.order
  );
}
export const NEXO = 'https://nexoresearch.org';
export const ORIGIN = 'https://cosmos.denerpereira.com.br';
