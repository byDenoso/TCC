/** Didactic models. Graphs carry physical units; camera coordinates belong only to the diagram. */
type Point = [number, number];
type Dot = [number, number, number];
type Segment = [number, number, number, number, number, number];

export type Lab = {
  id: string;
  title: string;
  description: string;
  assumptions: string;
  reference: { name: string; url: string };
  parameters: { label: string; unit: string; min: number; max: number; step: number; initial: number }[];
  presets: { name: string; values: number[] }[];
  xLabel: string;
  yLabel: string;
};
export type Simulation = {
  points: Point[];
  dots: Dot[];
  segments: Segment[];
  metric: { label: string; value: number; unit: string };
  caption: string;
};
const tau = 2 * Math.PI;
const solarGM = 1.3271244e20; // nominal solar mass parameter, m³/s²
const earthGM = 3.986004e14; // nominal terrestrial mass parameter, m³/s²
const earthRadius = 6.371e6; // mean spherical radius, m
const c = 299792458; // m/s
const au = 149597870700; // m
const parsec = (au * 648000) / Math.PI;
const gyrSeconds = 1e9 * 365.25 * 86400;
const gravitationalSolar = solarGM / (1000 ** 2 * 1000 * parsec); // kpc (km/s)² / solar mass
const boltzmann = 1.380649e-23;
const planck = 6.62607015e-34;
const elementaryCharge = 1.602176634e-19;
const protonMass = 1.67262192595e-27;
const schwarzKm = (2 * solarGM) / (c * c * 1000);
const dim = 'adimensional';

function parameter(label: string, unit: string, min: number, max: number, step: number, initial: number) {
  return { label, unit, min, max, step, initial };
}
function preset(name: string, ...values: number[]) {
  return { name, values };
}
function source(name: string, url: string) {
  return { name, url };
}

export const labs: Lab[] = [
  {
    id: 'orbitas',
    title: 'Sistema Solar e mecânica orbital',
    description: 'Mude a forma de uma órbita e descubra em que trecho um planeta ganha velocidade.',
    assumptions:
      'Problema de dois corpos. O Sol ocupa um foco, a massa do planeta é desprezível e a órbita é kepleriana. Os presets arredondam os elementos dos planetas.',
    reference: source(
      'OpenStax · Leis de Kepler',
      'https://openstax.org/books/university-physics-volume-1/pages/13-5-keplers-laws-of-planetary-motion'
    ),
    parameters: [
      parameter('Semieixo maior', 'UA', 0.35, 3, 0.01, 1),
      parameter('Excentricidade', dim, 0, 0.7, 0.001, 0.017),
    ],
    presets: [preset('Terra', 1, 0.017), preset('Mercúrio', 0.39, 0.206), preset('Marte', 1.52, 0.093)],
    xLabel: 'Tempo desde o periélio (dias)',
    yLabel: 'Distância ao Sol (UA)',
  },
  {
    id: 'gravitacao',
    title: 'Gravitação newtoniana',
    description: 'Meça a queda do campo gravitacional ao afastar uma sonda de uma massa esférica.',
    assumptions:
      'Massa esfericamente simétrica com raio fixo de 6.371 km. O observador permanece no exterior. Rotação e outras massas são desprezadas.',
    reference: source(
      'OpenStax · Gravitação universal',
      'https://openstax.org/books/university-physics-volume-1/pages/13-1-newtons-law-of-universal-gravitation'
    ),
    parameters: [
      parameter('Massa central', 'M⊕', 0.25, 2, 0.05, 1),
      parameter('Distância ao centro', 'R⊕', 1, 5, 0.05, 1),
    ],
    presets: [
      preset('Superfície terrestre', 1, 1),
      preset('Dobro da distância', 1, 2),
      preset('Dobro da massa', 2, 1),
    ],
    xLabel: 'Distância ao centro (R⊕)',
    yLabel: 'Aceleração gravitacional (m/s²)',
  },
  {
    id: 'n-corpos',
    title: 'Problema de N corpos',
    description:
      'Acompanhe duas órbitas que se perturbam e meça a menor distância entre os planetas durante três anos.',
    assumptions:
      'Três massas pontuais em um plano. Estrela de 1 M☉ e planeta interno de 1 massa de Júpiter a 1 UA. Órbitas inicialmente quase circulares. Todas as forças são mútuas. Integração de Verlet em passos de 1/512 ano.',
    reference: source(
      'OpenStax · Força gravitacional e superposição',
      'https://openstax.org/books/university-physics-volume-1/pages/13-1-newtons-law-of-universal-gravitation'
    ),
    parameters: [
      parameter('Massa do planeta externo', 'M♃', 1, 20, 1, 5),
      parameter('Raio orbital externo inicial', 'UA', 1.8, 3.2, 0.05, 2.2),
    ],
    presets: [
      preset('Par de gigantes', 5, 2.2),
      preset('Vizinho massivo', 18, 1.8),
      preset('Órbitas afastadas', 1, 3.2),
    ],
    xLabel: 'Tempo (anos)',
    yLabel: 'Separação entre os planetas (UA)',
  },
  {
    id: 'ondas',
    title: 'Ondas e interferência',
    description: 'Ajuste a fase de duas ondas e acompanhe a soma de seus deslocamentos.',
    assumptions:
      'Duas ondas senoidais de amplitude 0,15 m e mesmo comprimento de onda propagam-se a 1 m/s no mesmo sentido em um meio linear unidimensional.',
    reference: source(
      'OpenStax · Interferência de ondas',
      'https://openstax.org/books/university-physics-volume-1/pages/16-5-interference-of-waves'
    ),
    parameters: [
      parameter('Comprimento de onda', 'm', 0.5, 4, 0.05, 2),
      parameter('Diferença de fase', '°', 0, 180, 1, 60),
    ],
    presets: [preset('Em fase', 2, 0), preset('Um quarto de ciclo', 2, 90), preset('Em oposição', 2, 180)],
    xLabel: 'Posição (m)',
    yLabel: 'Deslocamento resultante (m)',
  },
  {
    id: 'campos',
    title: 'Campo elétrico e magnético',
    description:
      'Lance um próton em campos paralelos e separe a rotação transversal da aceleração longitudinal.',
    assumptions:
      'Campos uniformes paralelos ao eixo axial. Próton com velocidade transversal inicial de 100 km/s e velocidade axial inicial nula. Aproximação não relativística, sem colisões.',
    reference: source(
      'OpenStax · Movimento de uma partícula carregada',
      'https://openstax.org/books/university-physics-volume-2/pages/11-3-motion-of-a-charged-particle-in-a-magnetic-field'
    ),
    parameters: [
      parameter('Campo elétrico axial', 'V/m', -30, 30, 1, 12),
      parameter('Campo magnético axial', 'mT', 0.5, 3, 0.05, 1),
    ],
    presets: [
      preset('Movimento helicoidal acelerado', 12, 1),
      preset('Somente campo magnético', 0, 1),
      preset('Campo elétrico invertido', -20, 1.5),
    ],
    xLabel: 'Tempo após o lançamento (µs)',
    yLabel: 'Distância ao ponto de lançamento (m)',
  },
  {
    id: 'relatividade',
    title: 'Relatividade especial',
    description: 'Compare um relógio de luz em movimento com o relógio do laboratório.',
    assumptions:
      'Movimento retilíneo uniforme no espaço-tempo plano. O viajante mede 1 µs por ciclo de ida e volta da luz entre os espelhos.',
    reference: source(
      'OpenStax · Dilatação do tempo',
      'https://openstax.org/books/university-physics-volume-3/pages/5-3-time-dilation'
    ),
    parameters: [
      parameter('Velocidade relativa', 'c', 0, 0.98, 0.01, 0.8),
      parameter('Intervalo no laboratório', 'µs', 1, 10, 0.1, 5),
    ],
    presets: [preset('Repouso', 0, 5), preset('A 80% da luz', 0.8, 5), preset('A 98% da luz', 0.98, 10)],
    xLabel: 'Tempo no laboratório (µs)',
    yLabel: 'Tempo próprio do viajante (µs)',
  },
  {
    id: 'curvatura',
    title: 'Curvatura do espaço-tempo',
    description: 'Compare o raio definido pela circunferência com a distância radial medida por réguas.',
    assumptions:
      'Exterior de Schwarzschild. Equador em uma fatia de tempo de Schwarzschild constante. A altura do paraboloide de Flamm é uma coordenada de imersão visual. O horizonte serve de limite inferior da integral.',
    reference: source(
      'Revista Brasileira de Ensino de Física · Geometria de Schwarzschild',
      'https://www.scielo.br/j/rbef/a/gYmz8wxpVN8w76sLNv9XLnB/?lang=en'
    ),
    parameters: [
      parameter('Massa central', 'M☉', 1, 20, 0.5, 5),
      parameter('Raio de medida', 'rₛ', 1.1, 8, 0.1, 3),
    ],
    presets: [
      preset('Próximo ao horizonte', 5, 1.2),
      preset('A três raios', 5, 3),
      preset('Maior massa', 15, 3),
    ],
    xLabel: 'Raio areal (km)',
    yLabel: 'Distância radial própria desde o horizonte (km)',
  },
  {
    id: 'lentes',
    title: 'Lenteamento gravitacional',
    description: 'Desalinhe uma fonte de uma lente pontual e acompanhe a separação angular das imagens.',
    assumptions:
      'Lente fina isolada, campo fraco e fonte pontual. Distâncias euclidianas de 4 kpc até a lente e de 8 kpc até a fonte. Alinhamento exato produz um anel de Einstein.',
    reference: source(
      'Universidade de Cambridge · Gravitational lensing',
      'https://people.ast.cam.ac.uk/~pettini/Intro%20Cosmology/Lecture16.pdf'
    ),
    parameters: [
      parameter('Massa da lente', 'M☉', 0.1, 9, 0.1, 1),
      parameter('Desalinhamento da fonte', 'mas', 0, 4, 0.05, 0.5),
    ],
    presets: [
      preset('Lente solar', 1, 0.5),
      preset('Anel de Einstein', 1, 0),
      preset('Lente massiva', 5, 1),
    ],
    xLabel: 'Desalinhamento da fonte (mas)',
    yLabel: 'Separação angular (mas)',
  },
  {
    id: 'buracos-negros',
    title: 'Buracos negros',
    description:
      'Emita luz de um ponto sustentado acima do horizonte e calcule o desvio gravitacional até o infinito.',
    assumptions:
      'Buraco negro de Schwarzschild, sem rotação. Emissor estático fora do horizonte e observador estático no infinito. A luz sai na direção radial. O gráfico usa o raio areal.',
    reference: source(
      'Universidade de Rochester · Gravitational time dilation',
      'https://www.pas.rochester.edu/~kdouglass/Classes/Astr142/lectures/09_lecture.pdf'
    ),
    parameters: [
      parameter('Massa do buraco negro', 'M☉', 1, 30, 0.5, 10),
      parameter('Raio de emissão', 'rₛ', 1.05, 12, 0.05, 2),
    ],
    presets: [
      preset('A dois raios', 10, 2),
      preset('Próximo do horizonte', 10, 1.1),
      preset('Fonte distante', 5, 8),
    ],
    xLabel: 'Raio de emissão (km)',
    yLabel: 'Desvio gravitacional z',
  },
  {
    id: 'expansao',
    title: 'Expansão cosmológica',
    description: 'Leia a inclinação da relação velocidade–distância e examine o campo de recessão radial.',
    assumptions:
      'Instantâneo FLRW no presente com separações próprias e galáxias comóveis. Velocidades peculiares são omitidas. A identificação observacional v ≈ cz vale em baixo desvio para o vermelho.',
    reference: source(
      'D. W. Hogg · Distance measures in cosmology',
      'https://arxiv.org/abs/astro-ph/9905116'
    ),
    parameters: [
      parameter('Constante de Hubble', 'km/s/Mpc', 45, 95, 1, 70),
      parameter('Distância da galáxia', 'Mpc', 5, 200, 1, 100),
    ],
    presets: [
      preset('A 100 Mpc', 70, 100),
      preset('Metade da distância', 70, 50),
      preset('Maior inclinação', 80, 100),
    ],
    xLabel: 'Distância própria hoje (Mpc)',
    yLabel: 'Velocidade de recessão (km/s)',
  },
  {
    id: 'estruturas',
    title: 'Formação de estruturas',
    description:
      'Comprima um traçador inicialmente uniforme e relacione a separação das partículas à densidade.',
    assumptions:
      'Aproximação de Zel’dovich para um modo plano, matéria fria, ausência de pressão e fundo Einstein–de Sitter. D(a) = a. O contraste usa o jacobiano antes do cruzamento de trajetórias. Comprimento de onda comóvel de 40 Mpc.',
    reference: source(
      'A. Dekel · Dynamics of Cosmic Flows',
      'https://ned.ipac.caltech.edu/level5/Dekel/Dekel2.html'
    ),
    parameters: [
      parameter('Amplitude linear atual', dim, 0.05, 0.65, 0.01, 0.35),
      parameter('Fator de escala', dim, 0.1, 1, 0.05, 0.8),
    ],
    presets: [
      preset('Inicial', 0.35, 0.2),
      preset('Crescimento', 0.35, 0.8),
      preset('Compressão forte', 0.65, 1),
    ],
    xLabel: 'Posição comóvel (Mpc)',
    yLabel: 'Contraste de densidade δ',
  },
  {
    id: 'rotacao',
    title: 'Matéria escura e curvas de rotação',
    description:
      'Separe a contribuição de uma distribuição bariônica compacta da contribuição de um halo estendido.',
    assumptions:
      'Órbitas circulares. Bárions em esfera de Plummer de escala 2 kpc e halo de potencial logarítmico com núcleo de 5 kpc. A curva ilustra a decomposição de massa em equilíbrio.',
    reference: source('J. Bovy · Dynamics and Astrophysics of Galaxies', 'https://galaxiesbook.org/'),
    parameters: [
      parameter('Massa de bárions', '10¹⁰ M☉', 1, 12, 0.1, 5),
      parameter('Velocidade assintótica do halo', 'km/s', 0, 240, 5, 160),
    ],
    presets: [
      preset('Bárions e halo', 5, 160),
      preset('Somente bárions', 5, 0),
      preset('Halo dominante', 2, 220),
    ],
    xLabel: 'Raio galactocêntrico (kpc)',
    yLabel: 'Velocidade circular (km/s)',
  },
  {
    id: 'fator-de-escala',
    title: 'Evolução do fator de escala',
    description: 'Integre a história de expansão de um universo com matéria e constante cosmológica.',
    assumptions:
      'Modelo FLRW plano com poeira e Λ, ΩΛ = 1 − Ωm e a(t₀) = 1. Solução analítica da primeira equação de Friedmann. A extrapolação até a = 0 desconsidera a era radiativa.',
    reference: source('D. W. Hogg · H(z), tempo e distância', 'https://arxiv.org/abs/astro-ph/9905116'),
    parameters: [
      parameter('Constante de Hubble', 'km/s/Mpc', 45, 95, 1, 70),
      parameter('Fração de matéria hoje', dim, 0.1, 1, 0.01, 0.3),
    ],
    presets: [
      preset('Matéria e Λ', 70, 0.3),
      preset('Somente matéria', 70, 1),
      preset('Mais matéria', 70, 0.7),
    ],
    xLabel: 'Idade do modelo (Ganos)',
    yLabel: 'Fator de escala a',
  },
  {
    id: 'energia-escura',
    title: 'Energia escura e equação de estado',
    description: 'Varie a pressão do componente escuro e meça o sinal da aceleração cósmica atual.',
    assumptions:
      'Modelo wCDM plano com matéria e fluido escuro de w = p/(ρc²) constante. Componentes conservados separadamente e radiação desprezada. A densidade do gráfico é normalizada à densidade crítica de hoje.',
    reference: source(
      'Frieman, Turner e Huterer · Dark Energy and the Accelerating Universe',
      'https://arxiv.org/abs/0803.0982'
    ),
    parameters: [
      parameter('Equação de estado w', dim, -1.4, -0.35, 0.01, -1),
      parameter('Fração de energia escura hoje', dim, 0.1, 0.9, 0.01, 0.7),
    ],
    presets: [
      preset('Constante cosmológica', -1, 0.7),
      preset('Pressão menos negativa', -0.6, 0.7),
      preset('Regime fantasma', -1.2, 0.7),
    ],
    xLabel: 'Desvio para o vermelho z',
    yLabel: 'Densidade escura / densidade crítica atual',
  },
  {
    id: 'cmb',
    title: 'Radiação cósmica de fundo',
    description:
      'Desloque o máximo espectral de um corpo negro e compare a temperatura em diferentes épocas.',
    assumptions:
      'Espectro médio de Planck em equilíbrio, T(z) = T₀(1 + z). Frequência e radiância no referencial comóvel da época selecionada. Os pontos são previsões do modelo e a referência FIRAS contém o espectro observado.',
    reference: source(
      'NASA LAMBDA · COBE/FIRAS',
      'https://lambda.gsfc.nasa.gov/product/cobe/firas_overview.html'
    ),
    parameters: [
      parameter('Temperatura atual T₀', 'K', 2, 4, 0.001, 2.725),
      parameter('Desvio para o vermelho', dim, 0, 3, 0.05, 0),
    ],
    presets: [
      preset('Universo atual', 2.725, 0),
      preset('Época z = 1', 2.725, 1),
      preset('Época z = 3', 2.725, 3),
    ],
    xLabel: 'Frequência na época selecionada (GHz)',
    yLabel: 'Radiância espectral (MJy/sr)',
  },
];

const settings = new Map(labs.map((lab) => [lab.id, lab]));
const lastStatic = new Map<string, { key: string; result: Simulation }>();

function samples(n: number, left: number, right: number, f: (x: number) => number): Point[] {
  return Array.from({ length: n + 1 }, (_, i) => {
    const x = left + ((right - left) * i) / n;
    return [x, f(x)];
  });
}
function line(a: Dot, b: Dot): Segment {
  return [...a, ...b];
}
function stroke(dots: Dot[]): Segment[] {
  return dots.slice(1).map((to, i) => line(dots[i], to));
}
function circle(radius: number, altitude = 0, count = 40): Segment[] {
  return stroke(
    Array.from({ length: count + 1 }, (_, i) => [
      radius * Math.cos((tau * i) / count),
      altitude,
      radius * Math.sin((tau * i) / count),
    ])
  );
}
function orbitPlane(x: number, y: number): Dot {
  return [x, 0.54 * y, 0.841665 * y];
}
function orbitSegments(radius: number): Segment[] {
  return stroke(
    Array.from({ length: 57 }, (_, i) =>
      orbitPlane(radius * Math.cos((tau * i) / 56), radius * Math.sin((tau * i) / 56))
    )
  );
}
function arrow(base: Dot, tip: Dot): Segment[] {
  const dx = tip[0] - base[0],
    dy = tip[1] - base[1],
    dz = tip[2] - base[2];
  const len = Math.hypot(dx, dy, dz);
  if (len === 0) return [];
  const alongZ = Math.abs(dz) > len * 0.8;
  const side: Dot = alongZ ? [0, dz, -dy] : [-dy, dx, 0];
  const scale = (len * 0.13) / Math.hypot(...side);
  const neck: Dot = [tip[0] - dx * 0.28, tip[1] - dy * 0.28, tip[2] - dz * 0.28];
  const left: Dot = [neck[0] + scale * side[0], neck[1] + scale * side[1], neck[2] + scale * side[2]];
  const right: Dot = [neck[0] - scale * side[0], neck[1] - scale * side[1], neck[2] - scale * side[2]];
  return [line(base, tip), line(tip, left), line(tip, right)];
}
function result(
  points: Point[],
  dots: Dot[],
  segments: Segment[],
  label: string,
  value: number,
  unit: string,
  caption: string
): Simulation {
  return { points, dots, segments, metric: { label, value, unit }, caption };
}

// The frame uses one distance scale for every orbit. Body diameters are enlarged markers.
export const orbitUnitsPerAU = 0.82;
export const orbitGuide = orbitSegments(orbitUnitsPerAU).filter((_, i) => i % 2 === 0);
let orbitCache: { a: number; e: number; period: number; points: Point[]; ring: Segment[] } | undefined;
function eccentricAnomaly(fraction: number, e: number) {
  const mean = tau * fraction;
  let E = mean;
  for (let i = 0; i < 8; i++) E -= (E - e * Math.sin(E) - mean) / (1 - e * Math.cos(E));
  return E;
}
function orbit([a, e]: number[], time: number) {
  const position = (E: number) =>
    orbitPlane(
      orbitUnitsPerAU * a * (Math.cos(E) - e),
      orbitUnitsPerAU * a * Math.sqrt(1 - e * e) * Math.sin(E)
    );
  if (!orbitCache || orbitCache.a !== a || orbitCache.e !== e) {
    const period = (tau * Math.sqrt((a * au) ** 3 / solarGM)) / 86400;
    const points = samples(96, 0, period, (t) => a * (1 - e * Math.cos(eccentricAnomaly(t / period, e))));
    const ring = stroke(Array.from({ length: 97 }, (_, i) => position((tau * i) / 96)));
    orbitCache = { a, e, period, points, ring };
  }
  const { period, points, ring } = orbitCache;
  const planet = position(eccentricAnomaly(((time * 30) % period) / period, e));
  return result(
    points,
    [[0, 0, 0], planet],
    [...ring, line([0, 0, 0], planet)],
    'Período orbital',
    period,
    'dias',
    'O Sol ocupa um foco da elipse. A escala de distância permanece fixa ao alterar a órbita. Os diâmetros dos corpos estão ampliados. Cada segundo de animação corresponde a 30 dias.'
  );
}

function gravity([mass, selected]: number[]) {
  const g = (r: number) => (mass * earthGM) / (earthRadius * r) ** 2;
  const segments: Segment[] = [];
  for (const radius of [1.45, 2.6, 4.1]) {
    for (let j = 0; j < 12; j++) {
      const angle = (tau * j) / 12,
        x = Math.cos(angle),
        y = Math.sin(angle);
      const start = 0.36 * radius,
        end = start - (0.22 * mass) / (radius * radius);
      segments.push(...arrow(orbitPlane(start * x, start * y), orbitPlane(end * x, end * y)));
    }
  }
  segments.push(...orbitSegments(0.36));
  return result(
    samples(80, 1, 5, g),
    [[0, 0, 0], orbitPlane(0.36 * selected, 0)],
    segments,
    'Campo na sonda',
    g(selected),
    'm/s²',
    'O círculo delimita a superfície e o ponto externo é a sonda. As setas apontam para o centro e seu comprimento segue o módulo do campo.'
  );
}

// Barycentric Newtonian dynamics in AU, Julian years and solar mass parameters.
const yearSeconds = 365.25 * 86400;
const gravAU = (solarGM * yearSeconds ** 2) / au ** 3;
const jupiter = 1.2668653e17 / solarGM;
type Body = { m: number; x: number; y: number; vx: number; vy: number };
type Snapshot = [Point, Point, Point];
type Triple = {
  curve: Point[];
  positions: Snapshot[];
  closest: number;
  energyError: number;
  barycentreDrift: number;
  momentumDrift: number;
};
const tripleCache = new Map<string, Triple>();

function accelerations(b: Body[]): Point[] {
  const acc: Point[] = b.map(() => [0, 0]);
  for (let i = 0; i < b.length - 1; i++) {
    for (let j = i + 1; j < b.length; j++) {
      const dx = b[j].x - b[i].x,
        dy = b[j].y - b[i].y;
      const g = gravAU / Math.pow(dx * dx + dy * dy, 1.5);
      acc[i][0] += g * b[j].m * dx;
      acc[i][1] += g * b[j].m * dy;
      acc[j][0] -= g * b[i].m * dx;
      acc[j][1] -= g * b[i].m * dy;
    }
  }
  return acc;
}
function totalEnergy(b: Body[]): number {
  let total = 0;
  for (let i = 0; i < b.length; i++) {
    total += 0.5 * b[i].m * (b[i].vx ** 2 + b[i].vy ** 2);
    for (let j = i + 1; j < b.length; j++)
      total -= (gravAU * b[i].m * b[j].m) / Math.hypot(b[i].x - b[j].x, b[i].y - b[j].y);
  }
  return total;
}
function integrateTriple(mass: number, outer: number): Triple {
  const key = mass + '/' + outer;
  const cached = tripleCache.get(key);
  if (cached) return cached;

  const angle = 0.85;
  const innerV = Math.sqrt(gravAU * (1 + jupiter));
  const outerV = Math.sqrt((gravAU * (1 + mass * jupiter)) / outer);
  const b: Body[] = [
    { m: 1, x: 0, y: 0, vx: 0, vy: 0 },
    { m: jupiter, x: 1, y: 0, vx: 0, vy: innerV },
    {
      m: mass * jupiter,
      x: outer * Math.cos(angle),
      y: outer * Math.sin(angle),
      vx: -outerV * Math.sin(angle),
      vy: outerV * Math.cos(angle),
    },
  ];
  const totalMass = b.reduce((s, p) => s + p.m, 0);
  const center = (key: 'x' | 'y' | 'vx' | 'vy') => b.reduce((s, p) => s + p.m * p[key], 0) / totalMass;
  for (const key of ['x', 'y', 'vx', 'vy'] as const) {
    const offset = center(key);
    for (const p of b) p[key] -= offset;
  }

  const curve: Point[] = [],
    positions: Snapshot[] = [];
  const energy0 = totalEnergy(b);
  let energyError = 0,
    barycentreDrift = 0,
    momentumDrift = 0,
    closest = Infinity;
  const stepsPerYear = 512,
    steps = 3 * stepsPerYear,
    dt = 1 / stepsPerYear;
  let acc = accelerations(b);
  for (let step = 0; step <= steps; step++) {
    const separation = Math.hypot(b[1].x - b[2].x, b[1].y - b[2].y);
    closest = Math.min(closest, separation);
    if (step % 8 === 0) {
      curve.push([step * dt, separation]);
      positions.push([
        [b[0].x, b[0].y],
        [b[1].x, b[1].y],
        [b[2].x, b[2].y],
      ]);
      energyError = Math.max(energyError, Math.abs((totalEnergy(b) - energy0) / energy0));
      barycentreDrift = Math.max(barycentreDrift, Math.hypot(center('x'), center('y')));
      momentumDrift = Math.max(momentumDrift, totalMass * Math.hypot(center('vx'), center('vy')));
    }
    if (step === steps) break;
    for (let i = 0; i < b.length; i++) {
      const p = b[i];
      p.vx += (acc[i][0] * dt) / 2;
      p.vy += (acc[i][1] * dt) / 2;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
    }
    acc = accelerations(b);
    for (let i = 0; i < b.length; i++) {
      b[i].vx += (acc[i][0] * dt) / 2;
      b[i].vy += (acc[i][1] * dt) / 2;
    }
  }
  const table: Triple = { curve, positions, closest, energyError, barycentreDrift, momentumDrift };
  if (tripleCache.size >= 6) tripleCache.delete(tripleCache.keys().next().value!);
  tripleCache.set(key, table);
  return table;
}
export function threeBodyDiagnostics(massJupiter: number, radiusAU: number) {
  const { energyError, barycentreDrift, momentumDrift } = integrateTriple(massJupiter, radiusAU);
  return { energyError, barycentreDrift, momentumDrift };
}
function nbody([mass, outer]: number[], time: number) {
  const table = integrateTriple(mass, outer);
  const frame = (((time / 8) % 3) * (table.positions.length - 1)) / 3;
  const i = Math.floor(frame),
    f = frame - i;
  const before = table.positions[i],
    after = table.positions[i + 1] ?? before;
  const scale = 1.65 / outer;
  const dots = before.map(([x, y], j) =>
    orbitPlane(scale * (x + (after[j][0] - x) * f), scale * (y + (after[j][1] - y) * f))
  );
  const segments: Segment[] = [];
  for (const body of [1, 2]) {
    const orbit = table.positions
      .filter((_, j) => j % 3 === 0)
      .map((p) => orbitPlane(scale * p[body][0], scale * p[body][1]));
    segments.push(...stroke(orbit));
  }
  return result(
    table.curve,
    dots,
    segments,
    'Menor separação em três anos',
    table.closest,
    'UA',
    'As trilhas mostram toda a integração. O tempo parte da configuração inicial e repete após três anos. Oito segundos de exibição representam um ano.'
  );
}

function waves([wavelength, degrees]: number[], time: number) {
  const phase = (degrees * Math.PI) / 180;
  const wave = (x: number, phaseShift: number) =>
    0.15 * Math.sin((tau * (x - time)) / wavelength + phaseShift);
  const sum = (x: number) => wave(x, 0) + wave(x, phase);
  const points = samples(128, 0, 4, sum);
  const lane = (z: number, f: (x: number) => number) =>
    stroke(points.map(([x]) => [(x - 2) * 0.85, f(x) * 2, z]));
  const segments = [
    ...lane(-0.75, (x) => wave(x, 0)),
    ...lane(0, sum),
    ...lane(0.75, (x) => wave(x, phase)),
  ];
  return result(
    points,
    [[0, sum(2) * 2, 0]],
    segments,
    'Amplitude da superposição',
    0.3 * Math.cos(phase / 2),
    'm',
    'As duas faixas externas mostram as ondas individuais. A faixa central e o gráfico mostram a soma. Um segundo na tela corresponde a um segundo do modelo.'
  );
}

function fields([electric, fieldMT]: number[], time: number) {
  const omega = (elementaryCharge * fieldMT * 1e-3) / protonMass;
  const radius = 1e5 / omega,
    acceleration = (elementaryCharge * electric) / protonMass;
  // Initial motion is +x; B is +z, so the positive charge turns toward −y.
  const pos = (us: number): Dot => {
    const t = us / 1e6;
    return [radius * Math.sin(omega * t), radius * (Math.cos(omega * t) - 1), 0.5 * acceleration * t * t];
  };
  const times = samples(120, 0, 60, (x) => Math.hypot(...pos(x)));
  const center = pos(30);
  const map = ([x, y, z]: Dot): Dot => [
    0.35 * (z - center[2]),
    0.35 * (x - center[0]),
    0.35 * (y - center[1]),
  ];
  const path = times.map(([t]) => map(pos(t)));
  const segments = stroke(path);
  // E and B are collinear; draw their vectors at separate heights. Display units differ.
  const bStart: Dot = [-1.4, -0.85, 0],
    eStart: Dot = [0, -1, 0];
  segments.push(
    ...arrow(bStart, [bStart[0] + 0.34 * fieldMT, bStart[1], 0]),
    ...arrow(eStart, [0.032 * electric, eStart[1], 0])
  );
  return result(
    times,
    [map(pos((time * 5) % 60))],
    segments,
    'Raio de Larmor',
    radius,
    'm',
    'O próton contorna a direção axial. A seta inferior acompanha E e a seta acima dela acompanha B, em escalas próprias. Cada segundo exibe 5 µs.'
  );
}

function relativity([beta, interval]: number[], time: number) {
  const rate = Math.sqrt(1 - beta * beta);
  const phase = (time / 8) % 1,
    elapsed = phase * interval,
    proper = elapsed * rate;
  const x = (t: number) => -1.5 + (3 * beta * t) / interval;
  const y = (t: number) => -0.48 + 0.96 * (1 - Math.abs(((t * rate) % 1) * 2 - 1));
  const points = samples(40, 0, interval, (t) => t * rate);
  const path: Dot[] = [[x(0), y(0), 0]];
  for (let reflection = 0.5 / rate; reflection < interval; reflection += 0.5 / rate)
    path.push([x(reflection), y(reflection), 0]);
  path.push([x(interval), y(interval), 0]);
  const nowX = x(elapsed);
  const mirrors: Segment[] = [-0.48, 0.48].map((h) => line([nowX - 0.16, h, 0], [nowX + 0.16, h, 0]));
  return result(
    points,
    [[nowX, -0.48 + 0.96 * (1 - Math.abs((proper % 1) * 2 - 1)), 0]],
    [...stroke(path), ...mirrors],
    'Tempo próprio no intervalo',
    interval * rate,
    'µs',
    'O ponto é um pulso entre os espelhos do viajante. A cena amplia a distância vertical. Oito segundos de exibição percorrem o intervalo escolhido no laboratório.'
  );
}

function curvature([mass, u]: number[]) {
  const rs = schwarzKm * mass;
  const length = (r: number) => {
    const v = Math.max(1, r / rs);
    return rs * (Math.sqrt(v * (v - 1)) + Math.acosh(Math.sqrt(v)));
  };
  const segments: Segment[] = [];
  const embedded = (v: number, angle: number): Dot => [
    0.2 * v * Math.cos(angle),
    0.4 * Math.sqrt(v - 1) - 0.6,
    0.2 * v * Math.sin(angle),
  ];
  for (let j = 0; j <= 8; j++) {
    const v = 1 + 7 * (j / 8) ** 2;
    segments.push(...stroke(Array.from({ length: 33 }, (_, m) => embedded(v, (tau * m) / 32))));
  }
  for (let m = 0; m < 12; m++)
    segments.push(
      ...stroke(Array.from({ length: 13 }, (_, j) => embedded(1 + 7 * (j / 12) ** 2, (tau * m) / 12)))
    );
  return result(
    samples(96, rs, 8 * rs, length),
    [embedded(u, 0)],
    segments,
    'Distância radial própria',
    length(u * rs),
    'km',
    'O ponto marca o raio escolhido sobre a superfície de Flamm. As três dimensões visuais usam a mesma escala em unidades de raio de Schwarzschild.'
  );
}

function lens([mass, beta]: number[]) {
  const dl = 4000 * parsec,
    ds = 8000 * parsec;
  const masPerRad = (180 / Math.PI) * 3600 * 1000;
  const einstein = Math.sqrt(((4 * solarGM * mass) / c ** 2) * ((ds - dl) / dl / ds)) * masPerRad;
  const separation = (b: number) => Math.hypot(b, 2 * einstein);
  const split = separation(beta),
    plus = (beta + split) / 2,
    minus = (beta - split) / 2;
  const scale = 0.19;
  const observer: Dot = [-1.65, 0, 0],
    galaxy: Dot = [1.65, 2 * beta * scale, 0],
    centre: Dot = [0, 0, 0];
  const high: Dot = [0, plus * scale, 0],
    low: Dot = [0, minus * scale, 0];
  const segments = [line(observer, high), line(high, galaxy), line(observer, low), line(low, galaxy)];
  if (beta === 0)
    segments.push(
      ...stroke(
        Array.from({ length: 49 }, (_, j) => [
          0,
          plus * scale * Math.cos((tau * j) / 48),
          plus * scale * Math.sin((tau * j) / 48),
        ])
      )
    );
  return result(
    samples(64, 0, 4, separation),
    [observer, centre, galaxy, high, low],
    segments,
    'Separação das imagens',
    split,
    'mas',
    'Trajetos na aproximação de lente fina, com observador à esquerda, lente no centro e fonte à direita. Desvios laterais ampliados. Para alinhamento exato mede-se o diâmetro do anel.'
  );
}

function blackHole([mass, u]: number[], time: number) {
  const rs = schwarzKm * mass;
  const redshift = (radius: number) => 1 / Math.sqrt(1 - rs / radius) - 1;
  const end = u + 4;
  const scale = 1.65 / end;
  const segments = [...orbitSegments(scale), ...circle(scale)];
  const meridian = Array.from({ length: 41 }, (_, j): Dot => [
    0,
    scale * Math.sin((tau * j) / 40),
    scale * Math.cos((tau * j) / 40),
  ]);
  segments.push(...stroke(meridian), line([u * scale, 0, 0], [end * scale, 0, 0]));
  // Outgoing radial photon: r* = r + rs log(r/rs−1); dr*/dt = c.
  const target = u + Math.log(u - 1) + (time % 4);
  let lo = u,
    hi = end;
  for (let i = 0; i < 28; i++) {
    const r = (lo + hi) / 2;
    if (r + Math.log(r - 1) < target) lo = r;
    else hi = r;
  }
  return result(
    samples(100, 1.05 * rs, 12 * rs, redshift),
    [
      [u * scale, 0, 0],
      [(scale * (lo + hi)) / 2, 0, 0],
    ],
    segments,
    'Desvio para o infinito',
    redshift(u * rs),
    'adimensional',
    'A esfera indica o horizonte e o segmento, um raio luminoso emitido para fora. Um segundo de exibição equivale a rₛ/c de tempo de Schwarzschild. O pulso reinicia a cada quatro segundos.'
  );
}

function hubble([h0, distance]: number[]) {
  const segments: Segment[] = [],
    dots: Dot[] = [[0, 0, 0]];
  const chosen: Dot = [(1.35 * distance) / 200, 0, 0];
  dots.push(chosen);
  for (const r of [0.62, 1.15]) {
    for (let i = 0; i < 12; i++) {
      // Fixed directions on a sphere, so H0 changes only the velocity vectors.
      const height = 1 - (2 * (i + 0.5)) / 12;
      const angle = i * Math.PI * (3 - Math.sqrt(5)),
        horizontal = Math.sqrt(1 - height * height);
      const p: Dot = [r * horizontal * Math.cos(angle), r * height, r * horizontal * Math.sin(angle)];
      const vectorScale = 1 + h0 / 250;
      dots.push(p);
      segments.push(...arrow(p, [p[0] * vectorScale, p[1] * vectorScale, p[2] * vectorScale]));
    }
  }
  segments.push(...arrow(chosen, [chosen[0] * (1 + h0 / 250), 0, 0]));
  return result(
    samples(64, 0, 200, (r) => h0 * r),
    dots,
    segments,
    'Recessão da galáxia escolhida',
    h0 * distance,
    'km/s',
    'A posição representa distância e a seta representa velocidade. A galáxia escolhida fica no eixo horizontal positivo. O campo também seria radial em torno de outro observador comóvel.'
  );
}

function structures([amplitude, a]: number[]) {
  const growth = amplitude * a,
    k = tau / 40;
  const position = (q: number) => q - (growth * Math.sin(k * q)) / k;
  const points: Point[] = Array.from({ length: 97 }, (_, i) => {
    const q = -20 + (40 * i) / 96;
    return [position(q), 1 / (1 - growth * Math.cos(k * q)) - 1];
  });
  const dots: Dot[] = [];
  for (let i = 0; i <= 14; i++) {
    const x = position(-20 + (40 * i) / 14) / 12;
    for (const y of [-0.55, 0, 0.55]) for (const z of [-0.7, 0, 0.7]) dots.push([x, y, z]);
  }
  return result(
    points,
    dots,
    [line([-1.66, -0.8, 0], [1.66, -0.8, 0])],
    'Sobredensidade máxima',
    100 * (1 / (1 - growth) - 1),
    '%',
    'Cada ponto carrega a mesma massa. A camada central ganha densidade à medida que os pontos convergem. A cena usa coordenadas comóveis e o fator de escala seleciona a época.'
  );
}

function rotation([baryonMass, halo]: number[], time: number) {
  const speed = (r: number) =>
    Math.sqrt(
      (gravitationalSolar * baryonMass * 1e10 * r ** 2) / (r ** 2 + 4) ** 1.5 +
        (halo ** 2 * r ** 2) / (r ** 2 + 25)
    );
  const segments: Segment[] = [],
    dots: Dot[] = [[0, 0, 0]];
  const tSeconds = time * 0.02 * gyrSeconds;
  for (const r of [3, 6, 10, 15, 22, 30]) {
    const radius = r / 18;
    segments.push(...orbitSegments(radius));
    const angle = (speed(r) * 1000 * tSeconds) / (r * 1000 * parsec);
    for (let j = 0; j < 3; j++) {
      const phase = angle + (tau * j) / 3 + 0.13 * r;
      dots.push(orbitPlane(radius * Math.cos(phase), radius * Math.sin(phase)));
    }
  }
  return result(
    samples(96, 0, 32, speed),
    dots,
    segments,
    'Velocidade a 15 kpc',
    speed(15),
    'km/s',
    'Os traçadores seguem órbitas circulares com frequência v(r)/r. Cada segundo de exibição corresponde a 20 milhões de anos. O halo contribui para a gravidade.'
  );
}

function cube(center: Dot, half: number): { dots: Dot[]; segments: Segment[] } {
  const dots: Dot[] = [],
    segments: Segment[] = [];
  for (let i = 0; i < 8; i++) {
    dots.push([
      center[0] + (i & 1 ? half : -half),
      center[1] + (i & 2 ? half : -half),
      center[2] + (i & 4 ? half : -half),
    ]);
  }
  for (let i = 0; i < 8; i++)
    for (const bit of [1, 2, 4]) if (!(i & bit)) segments.push(line(dots[i], dots[i | bit]));
  return { dots, segments };
}
function expansionHistory([h0, matter]: number[], time: number) {
  const hubbleTime = (parsec * 1000) / (h0 * gyrSeconds); // (Mpc expressed in km) divided by H0
  const lambda = 1 - matter;
  const age = (a: number) =>
    lambda === 0
      ? (2 * hubbleTime * a ** 1.5) / 3
      : ((2 * hubbleTime) / (3 * Math.sqrt(lambda))) * Math.asinh(Math.sqrt(lambda / matter) * a ** 1.5);
  const scaleFactor = (t: number) =>
    lambda === 0
      ? ((1.5 * t) / hubbleTime) ** (2 / 3)
      : (Math.sqrt(matter / lambda) * Math.sinh((1.5 * Math.sqrt(lambda) * t) / hubbleTime)) ** (2 / 3);
  const ageNow = age(1);
  const points = samples(96, 0, ageNow, scaleFactor);
  const current = scaleFactor(ageNow * (0.1 + (0.9 * (time % 16)) / 16));
  const box = cube([0, 0, 0], current);
  return result(
    points,
    [[0, 0, 0], ...box.dots],
    box.segments,
    'Idade até a = 1',
    ageNow,
    'Ganos',
    'O cubo delimita uma região comóvel. Seu lado físico cresce com a(t). Cada ciclo visual de 16 segundos percorre de 10% a 100% da idade calculada.'
  );
}

function darkEnergy([w, dark]: number[]) {
  const density = (z: number) => dark * (1 + z) ** (3 * (1 + w));
  const segments: Segment[] = [],
    dots: Dot[] = [];
  for (const z of [0, 1, 2]) {
    const de = density(z),
      matter = (1 - dark) * (1 + z) ** 3,
      sum = de + matter;
    for (const [column, fraction] of [
      [-1, matter / sum],
      [1, de / sum],
    ]) {
      const center: Dot = [column * 0.76, 0.83 - 0.83 * z, 0];
      const box = cube(center, 0.36 * Math.cbrt(fraction));
      segments.push(...box.segments);
      dots.push(center);
    }
  }
  return result(
    samples(80, 0, 4, density),
    dots,
    segments,
    'Desaceleração atual q₀',
    0.5 + 1.5 * dark * w,
    'adimensional',
    'O volume dos cubos representa a fração instantânea de matéria (esquerda) e energia escura (direita) nas épocas z = 0, 1 e 2, de cima para baixo. q₀ negativo indica expansão acelerada.'
  );
}

function background([temperature, redshift]: number[]) {
  const T = temperature * (1 + redshift);
  const peak = (2.8214393721220787 * boltzmann * T) / planck / 1e9;
  const brightness = (ghz: number) => {
    if (ghz === 0) return 0;
    const nu = ghz * 1e9;
    return (2 * planck * nu ** 3) / (c * c * Math.expm1((planck * nu) / (boltzmann * T))) / 1e-20;
  };
  const points = samples(120, 0, 3 * peak, brightness);
  const maximum = brightness(peak);
  const profile = (i: number, angle: number): Dot => {
    const [f, b] = points[i];
    return [
      -1.6 + (3.2 * f) / (3 * peak),
      ((0.7 * b) / maximum) * Math.cos(angle),
      ((0.7 * b) / maximum) * Math.sin(angle),
    ];
  };
  const segments: Segment[] = [];
  for (let j = 0; j < 8; j++) {
    segments.push(
      ...stroke(points.filter((_, i) => i % 4 === 0).map((_, i) => profile(i * 4, (tau * j) / 8)))
    );
  }
  for (let i = 8; i < points.length; i += 8)
    segments.push(...stroke(Array.from({ length: 17 }, (_, j) => profile(i, (tau * j) / 16))));
  return result(
    points,
    [profile(40, 0)],
    segments,
    'Frequência do pico de Bν',
    peak,
    'GHz',
    'A superfície de revolução mostra a forma do espectro calculado: posição axial indica frequência e raio indica radiância. A cena normaliza o pico; o gráfico mantém as unidades físicas.'
  );
}

const kernels: Record<string, (v: number[], time: number) => Simulation> = {
  orbitas: orbit,
  gravitacao: gravity,
  'n-corpos': nbody,
  ondas: waves,
  campos: fields,
  relatividade: relativity,
  curvatura: curvature,
  lentes: lens,
  'buracos-negros': blackHole,
  expansao: hubble,
  estruturas: structures,
  rotacao: rotation,
  'fator-de-escala': expansionHistory,
  'energia-escura': darkEnergy,
  cmb: background,
};
const timeIndependent = new Set([
  'gravitacao',
  'curvatura',
  'lentes',
  'expansao',
  'estruturas',
  'energia-escura',
  'cmb',
]);
export function hasTimeEvolution(id: string) {
  return !timeIndependent.has(id);
}
export function simulate(id: string, values: number[], time = 0): Simulation {
  const lab = settings.get(id);
  if (!lab) throw new RangeError('Laboratório desconhecido: ' + id);
  const controls = lab.parameters.map((p, i) =>
    Number.isFinite(values[i]) ? Math.min(p.max, Math.max(p.min, values[i])) : p.initial
  );
  if (timeIndependent.has(id)) {
    const key = controls.join('/');
    const cached = lastStatic.get(id);
    if (cached?.key === key) return cached.result;
    const result = kernels[id](controls, 0);
    lastStatic.set(id, { key, result });
    return result;
  }
  return kernels[id](controls, Number.isFinite(time) ? Math.max(0, time) : 0);
}
