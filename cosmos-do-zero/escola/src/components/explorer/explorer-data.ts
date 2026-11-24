export type Vec = [number, number, number];
export type Orbit = {
  name: string;
  a: number;
  days: number;
  color: string;
  symbolSize: number;
  angle: number;
  note: string;
};
export type Station = {
  id: string;
  name: string;
  short: string;
  family: string;
  measure: string;
  value: string;
  frame: string;
  text: string;
  guide: string;
  convention: string;
  source: string;
  url: string;
};
export const stations: Station[] = [
  {
    id: 'solar',
    name: 'Sistema Solar',
    short: 'Sistema Solar',
    family: 'Sistema planetário',
    measure: 'Semieixo da órbita de Netuno',
    value: '30,07 au',
    frame: 'Órbitas de Mercúrio a Netuno',
    text: 'O Sol concentra a maior parte da massa do sistema. Compare o percurso rápido dos planetas internos com a lenta revolução dos gigantes. Uma unidade astronômica (au) equivale a 149,6 milhões de quilômetros.',
    guide:
      'Selecione Mercúrio, avance alguns dias e repita com Netuno. Qual deles percorreu o maior ângulo em torno do Sol?',
    convention:
      'Órbitas circulares e coplanares com períodos siderais arredondados. As fases iniciais são ilustrativas e os corpos aparecem ampliados.',
    source: 'JPL · Elementos orbitais J2000',
    url: 'https://ssd.jpl.nasa.gov/planets/approx_pos.html',
  },
  {
    id: 'trappist',
    name: 'TRAPPIST-1',
    short: 'TRAPPIST-1',
    family: 'Estrela e exoplanetas',
    measure: 'Distância da Terra',
    value: '≈ 40 anos-luz',
    frame: 'Sete órbitas em 0,062 au',
    text: 'Sete planetas passam diante de uma anã vermelha. Cada trânsito produz uma pequena queda no brilho da estrela. Variações no horário dos trânsitos ajudam a medir a interação gravitacional entre os planetas.',
    guide:
      'O planeta h orbita a aproximadamente 0,062 au. Compare esse valor com os 0,39 au de Mercúrio. Quantas vezes o semieixo de Mercúrio é maior que o do planeta h?',
    convention:
      'Semieixos e períodos são arredondados a partir do catálogo. As fases, cores e dimensões dos símbolos são ilustrativas. As órbitas circulares simplificam a geometria.',
    source: 'NASA Exoplanet Archive · TRAPPIST-1',
    url: 'https://exoplanetarchive.ipac.caltech.edu/overview/TRAPPIST-1',
  },
  {
    id: 'orion',
    name: 'Nebulosa de Órion',
    short: 'Órion',
    family: 'Região de formação estelar',
    measure: 'Distância da Terra',
    value: '≈ 1.300 anos-luz',
    frame: 'Campo de referência de 3,4 anos-luz',
    text: 'Estrelas jovens aquecem e ionizam o gás que as rodeia. Próximo do Trapézio, a radiação ultravioleta escava uma cavidade. A mesma nebulosa reúne gás luminoso, poeira que absorve luz e estrelas em formação.',
    guide:
      'Localize o Trapézio e alterne os dois canais do Webb. Onde o gás ganha mais destaque em relação às estrelas?',
    convention:
      'As duas composições estão alinhadas. As cores representam filtros do infravermelho, que o olho humano não vê.',
    source: 'ESA/Webb · mosaico e filtros de Órion',
    url: 'https://www.esa.int/media/slider-orion-nebula-in-nircam-short-versus-long-wavelength-channel-aligned',
  },
  {
    id: 'm31',
    name: 'Galáxia de Andrômeda',
    short: 'Andrômeda',
    family: 'Galáxia espiral',
    measure: 'Distância da Terra',
    value: '≈ 2,5 milhões de anos-luz',
    frame: 'Disco e bojo de uma espiral',
    text: 'Em Andrômeda, a concentração de luz no centro traça o bojo. Braços no disco reúnem gás, poeira e estrelas jovens. Vemos o disco inclinado a partir da Terra. As faixas mais escuras acompanham a poeira no disco.',
    guide:
      'Compare o bojo central com o disco externo. Onde aparecem mais regiões azuladas?',
    convention:
      'As bordas recortadas mostram os limites da cobertura observacional de cada parte do mosaico.',
    source: 'NASA/Hubble · Messier 31',
    url: 'https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-messier-catalog/messier-31/',
  },
  {
    id: 'virgo',
    name: 'Aglomerado de Virgem',
    short: 'Virgem',
    family: 'Aglomerado de galáxias',
    measure: 'Distância da Terra até M87',
    value: '≈ 54 milhões de anos-luz',
    frame: 'Concentração de galáxias em torno de M87',
    text: 'A galáxia elíptica M87 domina a região central do aglomerado de Virgem. M49 marca outro subgrupo ao sul. O campo óptico registra galáxias do aglomerado e objetos em primeiro e segundo plano.',
    guide:
      'Localize M87 e a Cadeia de Markarian. Depois procure M49 e compare a posição dos dois subgrupos no céu.',
    convention:
      'Composição óptica do SDSS com norte para cima. As marcas indicam posições projetadas no céu.',
    source: 'NASA/Hubble · M87 e o aglomerado de Virgem',
    url: 'https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-messier-catalog/messier-87/',
  },
  {
    id: 'teia',
    name: 'Teia cósmica',
    short: 'Teia cósmica',
    family: 'Estrutura em grande escala',
    measure: 'Lado de uma caixa de referência',
    value: '110,7 Mpc comóveis',
    frame: 'Volume ilustrativo com filamentos e vazios',
    text: 'A gravidade amplifica diferenças de densidade. A matéria se concentra em nós e filamentos que delimitam regiões extensas de baixa densidade. Uma coordenada comóvel retira a expansão média do Universo ao comparar épocas diferentes.',
    guide:
      'Siga uma faixa de galáxias no mapa DESI. Depois alterne as fatias do modelo para ver como o padrão muda com a profundidade.',
    convention:
      'Rede sintética de nós e filamentos, com a mesma escala nos três eixos. O lado do cubo corresponde ao da caixa TNG100. A cena usa uma distribuição própria e identifica uma extensão espacial, sem uma distância observacional à Terra.',
    source: 'Nelson et al. · dimensões das caixas IllustrisTNG',
    url: 'https://doi.org/10.1093/mnras/stx3040',
  },
];

// Semieixos J2000 em au e períodos siderais em anos julianos de 365,25 dias (JPL).
const solarData: [string, number, number, string, number, number, string][] = [
  ['Mercúrio', 0.3871, 0.2408467, '#bbbec8', 0.049, 252, 'A órbita mais curta entre os oito planetas.'],
  [
    'Vênus',
    0.72334,
    0.61519726,
    '#e7b88b',
    0.066,
    182,
    'Uma volta ao redor do Sol leva cerca de 225 dias.',
  ],
  [
    'Terra',
    1.0,
    1.0000174,
    '#60b9ea',
    0.071,
    100,
    'A órbita da Terra fornece a referência histórica da unidade astronômica.',
  ],
  [
    'Marte',
    1.52371,
    1.8808476,
    '#e58e69',
    0.059,
    356,
    'Um ano marciano dura quase dois anos terrestres.',
  ],
  [
    'Júpiter',
    5.20289,
    11.862615,
    '#e5c19e',
    0.13,
    34,
    'O gigante gasoso completa uma revolução em quase doze anos terrestres.',
  ],
  [
    'Saturno',
    9.53668,
    29.447498,
    '#e0c790',
    0.108,
    50,
    'O sistema de anéis aparece ampliado para facilitar a identificação.',
  ],
  [
    'Urano',
    19.18916,
    84.016846,
    '#91d7cf',
    0.086,
    313,
    'Uma revolução dura cerca de 84 anos terrestres.',
  ],
  [
    'Netuno',
    30.06992,
    164.79132,
    '#789cfc',
    0.085,
    305,
    'No mesmo intervalo de dias, Netuno percorre um ângulo muito menor que Mercúrio.',
  ],
];
export const solar: Orbit[] = solarData.map(([name, a, years, color, symbolSize, angle, note]) => ({
  name,
  a,
  days: years * 365.25,
  color,
  symbolSize,
  angle,
  note,
}));

export const trappist: Orbit[] = [
  [0.01154, 1.51083],
  [0.0158, 2.42194],
  [0.02227, 4.04922],
  [0.02925, 6.10101],
  [0.03849, 9.20754],
  [0.04683, 12.35245],
  [0.06189, 18.77287],
].map(([a, days], i) => ({
  name: 'TRAPPIST-1 ' + 'bcdefgh'[i],
  a,
  days,
  color: ['#cd745a', '#d5ae85', '#dad2a5', '#a3c9a8', '#88b9ca', '#829dd2', '#c4b9ce'][i],
  symbolSize: 0.062,
  angle: [215, 126, 284, 48, 171, 326, 90][i],
  note: 'O intervalo entre trânsitos sucessivos aproxima o período orbital.',
}));

export interface CameraView {
  azimuth: number;
  tilt: number;
  zoom: number;
}
export const initialCamera: CameraView = { azimuth: 16, tilt: 32, zoom: 1 };
export const rad = Math.PI / 180;
export function orbitRadius(a: number, max: number, linear: boolean) {
  return 2.92 * (linear ? a / max : Math.log1p((200 * a) / max) / Math.log(201));
}
// Os glifos crescem só até caber entre as órbitas representadas.
export function orbitalSymbols(orbits: Orbit[], linear: boolean) {
  if (!orbits.length) return { star: 0, bodies: [] as number[] };
  const outer = orbits[orbits.length - 1].a;
  const tracks = orbits.map((orbit) => orbitRadius(orbit.a, outer, linear));
  const star = Math.min(0.105, tracks[0] * 0.3);
  const bodies = orbits.map(({ symbolSize }, i) => {
    const inside = tracks[i] - (tracks[i - 1] ?? 0);
    const outside = i + 1 < tracks.length ? tracks[i + 1] - tracks[i] : inside;
    return Math.min(symbolSize, Math.min(inside, outside) * 0.3);
  });
  return { star, bodies };
}
export function orbitPoint(orbit: Orbit, max: number, linear: boolean, day: number): Vec {
  const radius = orbitRadius(orbit.a, max, linear);
  const phase = orbit.angle * rad + (day / orbit.days) * 2 * Math.PI;
  return [radius * Math.cos(phase), 0, radius * Math.sin(phase)];
}
export function facing([x, y, z]: Vec, camera: CameraView): Vec {
  const a = camera.azimuth * rad,
    b = camera.tilt * rad;
  const dx = x * Math.cos(a) + z * Math.sin(a),
    dz = z * Math.cos(a) - x * Math.sin(a);
  return [dx, y * Math.cos(b) - dz * Math.sin(b), y * Math.sin(b) + dz * Math.cos(b)];
}
export function formatN(value: number, digits = 2) {
  return value.toLocaleString('pt-BR', { maximumFractionDigits: digits });
}
export function bound(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}
