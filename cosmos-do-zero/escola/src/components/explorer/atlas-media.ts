export type AtlasPoint = {
  name: string;
  x: number;
  y: number;
  detail: string;
};

export const atlasMedia = {
  solar: {
    file: 'saturno.webp',
    kind: 'Retratos modelados e mapas de missão',
    credit: 'Cosmos · mapas NASA/JPL-Caltech e USGS, com fontes por planeta',
    source: 'https://github.com/byDenoso/TCC/blob/cosmos-do-zero/cosmos-do-zero/assets/source/solar-materials/manifest.json',
    invitation: 'Compare o ritmo dos planetas.',
  },
  trappist: {
    file: 'trappist.webp',
    kind: 'Ilustração artística',
    credit: 'NASA/JPL-Caltech',
    source: 'https://science.nasa.gov/exoplanets/trappist1/',
    invitation: 'Veja a assinatura de um trânsito.',
  },
  orion: {
    file: 'orion-short.webp',
    kind: 'Mosaico observacional · Webb/NIRCam',
    credit: 'NASA, ESA, CSA, M. McCaughrean e S. Pearson · CC BY-SA 3.0 IGO · redimensionado',
    source: 'https://www.esa.int/media/slider-orion-nebula-in-nircam-short-versus-long-wavelength-channel-aligned',
    invitation: 'Compare duas faixas do infravermelho.',
  },
  m31: {
    file: 'm31.webp',
    kind: 'Mosaico observacional · Hubble',
    credit: 'NASA, ESA, B. Williams, Z. Chen, L. C. Johnson · processamento de J. DePasquale (STScI)',
    source: 'https://science.nasa.gov/asset/hubble/hubble-m31-phatphast-mosaic/',
    invitation: 'Do bojo às faixas de poeira.',
  },
  virgo: {
    file: 'virgo.webp',
    kind: 'Mapa observacional · SDSS',
    credit: 'Sloan Digital Sky Survey · composição SkyServer/DR18',
    source: 'https://skyserver.sdss.org/dr18/SkyServerWS/ImgCutout/getjpeg?ra=187.25&dec=10.65&scale=25.2&width=1200&height=900',
    invitation: 'Localize galáxias no aglomerado.',
  },
  teia: {
    file: 'desi.webp',
    kind: 'Mapa observacional · DESI',
    credit: 'David Kirkby / DESI Collaboration',
    source: 'https://data.desi.lbl.gov/doc/',
    invitation: 'Siga filamentos, nós e vazios.',
  },
} as const;

export type AtlasId = keyof typeof atlasMedia;

export const solarPortraits = ['mercurio', 'venus', 'terra', 'marte', 'jupiter', 'saturno', 'urano', 'netuno'];

export const orionPoints: AtlasPoint[] = [
  { name: 'Trapézio', x: 50, y: 40, detail: 'A região central abriga estrelas jovens e massivas. Sua radiação ultravioleta ioniza o gás ao redor.' },
  { name: 'Frente de ionização', x: 33, y: 66, detail: 'Na borda da cavidade, a luz ultravioleta encontra material molecular. Compare como essa fronteira aparece nas duas composições.' },
  { name: 'Cavidade', x: 44, y: 57, detail: 'O gás ionizado preenche a cavidade. No infravermelho longo, a composição destaca essa região em tons de violeta.' },
];

export const andromedaPoints: AtlasPoint[] = [
  { name: 'Bojo central', x: 41.7, y: 67, detail: 'A concentração mais luminosa marca o centro da galáxia, onde predominam populações estelares mais antigas.' },
  { name: 'Faixas de poeira', x: 29, y: 79, detail: 'A poeira absorve a luz das estrelas atrás dela e desenha filamentos escuros no disco.' },
  { name: 'Disco externo', x: 78, y: 45, detail: 'Regiões mais azuladas do disco contêm estrelas jovens. O mosaico resolve milhares de aglomerados estelares em toda a galáxia.' },
];

export const virgoPoints: AtlasPoint[] = [
  { name: 'M87', x: 44.7, y: 22.3, detail: 'Galáxia elíptica gigante próxima ao centro do aglomerado, a cerca de 54 milhões de anos-luz.' },
  { name: 'M49', x: 47.8, y: 92.1, detail: 'Outra galáxia elíptica gigante, ao sul de M87. Ela domina uma subestrutura do aglomerado de Virgem.' },
  { name: 'Cadeia de Markarian', x: 59.8, y: 14, detail: 'A faixa de galáxias passa por M84 e M86. Sua forma no céu é uma projeção das posições das galáxias.' },
];

export const webPoints: AtlasPoint[] = [
  { name: 'Região densa', x: 66, y: 28, detail: 'Nesta projeção, regiões mais povoadas concentram muitos dos objetos observados.' },
  { name: 'Filamentos', x: 45, y: 42, detail: 'Faixas de galáxias conectam concentrações em escalas maiores que um único aglomerado.' },
  { name: 'Região esparsa', x: 55, y: 73, detail: 'O mapa contém regiões com menos pontos. A densidade aparente também depende do recorte e da seleção do levantamento.' },
];
