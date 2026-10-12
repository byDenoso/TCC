export type MassClass = 'low' | 'medium' | 'high';
export interface StellarPath {
  category: string;
  title: string;
  summary: string;
  time: string;
  steps: string[];
  note: string;
  orb: MassClass;
}
export const STAR_MIN = 0.2;
export const STAR_MAX = 30;
/** Limiares pedagógicos (massas solares): 0,6 e 8. Ver nota em cada percurso. */
export function stellarPath(m: number): StellarPath {
  const birth = ['Nuvem molecular', 'Protoestrela'];
  if (m < 0.6)
    return { orb: 'low', category: 'BAIXA MASSA', title: 'Um brilho para muito depois de nós.', summary: 'Uma anã vermelha consome hidrogênio lentamente. Seus estágios tardios são previstos por modelos; ainda não vimos seu fim normal.', time: 'Escala de vida: centenas de bilhões de anos ou mais, dependendo da massa.', steps: [...birth, 'Anã vermelha', 'Fases tardias previstas', 'Anã branca prevista'], note: 'As estrelas de massa muito baixa podem seguir caminhos sem a fase clássica de gigante vermelha. O Universo ainda é jovem demais para observar seus finais.' };
  if (m < 8)
    return { orb: 'medium', category: m < 1.5 ? 'SEMELHANTE AO SOL' : 'MASSA INTERMEDIÁRIA', title: 'Um núcleo que vai esfriar.', summary: 'Depois da sequência principal, fases de gigante e perda das camadas externas deixam um núcleo compacto: uma anã branca.', time: m < 1.5 ? 'Escala de vida: bilhões de anos. O Sol tem cerca de 4,6 bilhões de anos.' : 'Escala de vida: de dezenas de milhões a poucos bilhões de anos nesta faixa.', steps: [...birth, 'Sequência principal', 'Gigante / perda de gás', 'Anã branca'], note: 'Este é um caminho típico de uma estrela isolada. Composição, perda de massa e interação em sistemas binários mudam a evolução.' };
  return { orb: 'high', category: 'ALTA MASSA', title: 'O colapso abre mais de um caminho.', summary: 'Após fases de fusão e expansão, o núcleo pode colapsar. Uma estrela de nêutrons ou um buraco negro pode permanecer; uma supernova luminosa não é obrigatória.', time: 'Escala de vida: milhões a dezenas de milhões de anos.', steps: [...birth, 'Estrela massiva', 'Colapso · explosão possível', 'Estrela de nêutrons ou buraco negro'], note: 'O corte em 8 massas solares é pedagógico, não exato. Massa inicial sozinha não determina o remanescente: metalicidade, rotação, ventos e companheiras importam.' };
}
export const massLabel = (m: number, fmt: (n: number) => string): string => `${fmt(m)} ${m === 1 ? 'massa solar' : 'massas solares'}`;
export const clampMass = (v: number): number => (Number.isFinite(v) ? Math.min(STAR_MAX, Math.max(STAR_MIN, Math.round(v * 10) / 10)) : 1);

/** Raio aproximado na sequência principal (massas solares → raios solares). Só para a ilustração. */
export const mainSequenceRadius = (m: number): number => (m < 1 ? m ** 0.9 : m ** 0.6);
/** Diâmetro da esfera ilustrativa em px, de 60 (0,2 M☉) a 190 (30 M☉). */
export function orbDiameter(m: number): number {
  const lo = mainSequenceRadius(STAR_MIN), hi = mainSequenceRadius(STAR_MAX);
  return Math.round(60 + 130 * (Math.log(mainSequenceRadius(m) / lo) / Math.log(hi / lo)));
}
type RGB = [number, number, number];
const STOPS: { m: number; c: RGB }[] = [
  { m: 0.2, c: [255, 143, 85] }, { m: 0.6, c: [255, 179, 107] }, { m: 1, c: [255, 226, 160] },
  { m: 2, c: [255, 244, 224] }, { m: 5, c: [220, 233, 255] }, { m: 15, c: [183, 210, 255] }, { m: 30, c: [159, 195, 255] }
];
/** Cor ilustrativa por massa (laranja → amarelo → branco-azulado), interpolada em escala logarítmica. */
export function orbColor(m: number): RGB {
  const x = Math.min(STAR_MAX, Math.max(STAR_MIN, m));
  let i = 0;
  while (i < STOPS.length - 2 && x > STOPS[i + 1].m) i++;
  const a = STOPS[i], b = STOPS[i + 1];
  const t = Math.min(1, Math.max(0, Math.log(x / a.m) / Math.log(b.m / a.m)));
  return [0, 1, 2].map((k) => Math.round(a.c[k] + (b.c[k] - a.c[k]) * t)) as RGB;
}
export const rgb = (c: RGB, k = 1): string => `rgb(${c.map((v) => Math.round(Math.min(255, v * k))).join(',')})`;
