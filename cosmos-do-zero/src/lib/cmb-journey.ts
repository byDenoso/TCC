/**
 * Física e texto da experiência da radiação cósmica de fundo (CMB), sem DOM.
 * Desenho, painel numérico e legenda leem o mesmo estado daqui.
 *
 * Valores: temperatura da CMB hoje T0 = 2,7255 K (FIRAS/COBE); desacoplamento em z ≈ 1090
 * (Planck 2018), ou seja, fator de escala a ≈ 1/1091; idade ≈ 380 mil anos.
 * Pico de Wien: λ_pico = b / T, com b = 2897,77 µm·K.
 */
export const T0 = 2.7255; // K, hoje
export const Z_DEC = 1090; // desvio para o vermelho do desacoplamento
export const A_DEC = 1 / (1 + Z_DEC); // fator de escala quando a luz se soltou
export const T_DEC = T0 * (1 + Z_DEC); // ≈ 2 970 K
export const WIEN_UM_K = 2897.77; // µm·K

export type StepId = 'quente' | 'atomos' | 'expansao';
export const STEPS: StepId[] = ['quente', 'atomos', 'expansao'];

/** Temperatura da radiação para um fator de escala a (T ∝ 1/a). */
export const tempAt = (a: number): number => T0 / a;
/** Comprimento de onda do pico do espectro (µm) para um fator de escala a. Cresce na mesma proporção que a. */
export const peakUm = (a: number): number => WIEN_UM_K / tempAt(a);

/** Fator de escala ao longo da etapa C: interpolação logarítmica de A_DEC até 1 (hoje), k ∈ [0, 1]. */
export const scaleAt = (k: number): number => Math.exp(Math.log(A_DEC) * (1 - Math.min(1, Math.max(0, k))));

export type Band = 'visível' | 'infravermelho' | 'micro-ondas';
/** Faixa do espectro de um comprimento de onda em µm. Micro-ondas: de 1 mm a 1 m. */
export function bandOf(um: number): Band {
  if (um < 0.75) return 'visível';
  if (um < 1000) return 'infravermelho';
  return 'micro-ondas';
}
/** Posição (0 a 1) de um comprimento de onda numa régua logarítmica de 0,3 µm a 30 mm, usada no painel. */
export const SCALE_MIN_UM = 0.3, SCALE_MAX_UM = 30000;
export const rulerPos = (um: number): number =>
  Math.min(1, Math.max(0, Math.log(um / SCALE_MIN_UM) / Math.log(SCALE_MAX_UM / SCALE_MIN_UM)));

/** Texto de comprimento de onda em unidade legível. */
export function fmtLength(um: number): string {
  const f = (n: number, d: number) => n.toLocaleString('pt-BR', { maximumFractionDigits: d, minimumFractionDigits: 0 });
  if (um < 1000) return `${f(um, um < 10 ? 1 : 0)} µm`;
  return `${f(um / 1000, 2)} mm`;
}
export function fmtScale(a: number): string {
  if (a > 0.999) return '1 (hoje)';
  return `1/${Math.round(1 / a).toLocaleString('pt-BR')}`;
}
export function fmtTemp(K: number): string {
  if (K < 100) return `${K.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} K`;
  return `${String(Math.round(K / 10) * 10).replace(/\B(?=(\d{3})+(?!\d))/g, ' ')} K`;
}

export interface StepText {
  id: StepId;
  /** Rótulo curto da etapa (controles) */
  label: string;
  /** Pergunta simples da etapa */
  ask: string;
  /** Duas ou três frases essenciais */
  say: string;
  /** O que fazer/observar */
  act: string;
  /** O que mudou em relação à etapa anterior */
  changed: string;
}
export const STEP_TEXT: StepText[] = [
  {
    id: 'quente',
    label: 'Universo quente',
    ask: 'Havia luz no começo?',
    say: 'Havia, e muita. Mas o Universo era quente demais para os elétrons ficarem presos aos núcleos. Elétrons livres desviam a luz a todo instante.',
    act: 'Siga uma trilha dourada: cada curva é um encontro com um elétron.',
    changed: 'A luz já existe. O que falta é caminho livre: cada trecho em linha reta é curto, como farol na neblina.'
  },
  {
    id: 'atomos',
    label: 'Formação de átomos',
    ask: 'O que muda quando o Universo esfria?',
    say: 'Por volta de 380 mil anos, a temperatura cai para cerca de 3 000 K. Os elétrons se prendem aos núcleos e formam átomos.',
    act: 'Observe os elétrons sendo capturados e as trilhas da luz ficando retas.',
    changed: 'Com quase nenhum elétron livre no caminho, a mesma luz passa a viajar livremente. Ela não nasceu agora: só deixou de ser desviada.'
  },
  {
    id: 'expansao',
    label: 'Expansão',
    ask: 'Por que essa luz chega hoje como micro‑ondas?',
    say: 'Enquanto a luz viaja, o espaço se expande. O comprimento de onda cresce na mesma proporção que as distâncias: desde então, cerca de 1 100 vezes.',
    act: 'Acompanhe a grade do espaço e a onda crescendo juntas, e o marcador andando na régua do espectro.',
    changed: 'A temperatura da radiação cai na mesma proporção, de quase 3 000 K para 2,7 K. Hoje ela chega principalmente como micro‑ondas, invisíveis aos olhos.'
  }
];

/** Parâmetro de URL da etapa (1 a 3). */
export const URL_PARAM = 'luz';
export function stepFromParam(v: string | null): number {
  const n = Number(v);
  return Number.isInteger(n) && n >= 1 && n <= STEPS.length ? n - 1 : 0;
}
