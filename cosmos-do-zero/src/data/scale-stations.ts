const au = 149_597_870_700;
const lightYear = 9.4607e15;

export const scaleStations = [
  {
    id: 'proton', name: 'Próton', image: 'scale-proton', extent: '≈ 0,84 fm', meters: 8.4075e-16,
    dimension: 'Raio de carga',
    text: 'O próton está no núcleo do hidrogênio. A força forte liga seus quarks. O raio de carga mede como a carga elétrica se espalha, como revelam os experimentos de espalhamento.',
    alt: 'Volume de partículas concentradas representando a carga do próton.',
    caption: 'Distribuição de carga ilustrativa. Um femtômetro é um quadrilionésimo de metro.',
    source: 'https://physics.nist.gov/cgi-bin/cuu/Value?rp%7Csearch_for=charge', sourceLabel: 'NIST · Raio de carga do próton',
  },
  {
    id: 'hidrogenio', name: 'Átomo de hidrogênio', image: 'scale-hydrogen', extent: '≈ 53 pm', meters: 5.2917721e-11,
    dimension: 'Raio de Bohr',
    text: 'O próton atrai o elétron pela força elétrica. O elétron ocupa uma nuvem de probabilidade. Nas regiões com mais pontos, há maior chance de detectá-lo.',
    alt: 'Nuvem esférica de pontos que se torna mais densa perto do próton.',
    caption: 'Amostras da distribuição do elétron no estado fundamental; núcleo ampliado.',
    source: 'https://physics.nist.gov/cuu/pdf/JPCRD2022CODATA.pdf', sourceLabel: 'NIST · Raio de Bohr',
  },
  {
    id: 'hemacia', name: 'Hemácia', image: 'scale-cell', extent: '≈ 8 μm', meters: 8e-6,
    dimension: 'Diâmetro de uma hemácia humana',
    text: 'Já estamos na escala das células. A hemácia tem o centro mais fino dos dois lados. Seu formato e sua flexibilidade ajudam a célula a atravessar vasos estreitos enquanto transporta oxigênio.',
    alt: 'Célula vermelha do sangue com formato de disco côncavo dos dois lados.',
    caption: 'Modelo ilustrativo de uma hemácia. Cor e iluminação estilizadas.',
    source: 'https://pubs.rsc.org/en/content/articlehtml/2020/ra/d0ra05421f', sourceLabel: 'RSC Advances · Medidas de hemácias',
  },
  {
    id: 'metro', name: 'Um metro', image: 'scale-meter', extent: '1 m', meters: 1,
    dimension: 'Comprimento de referência',
    text: 'Uma régua deste tamanho é fácil de percorrer com a mão. A luz cruza a mesma distância em pouco mais de três bilionésimos de segundo. Essa relação define o metro.',
    alt: 'Régua de um metro com marcações gravadas em uma superfície clara.',
    caption: 'Cada divisão maior equivale a um décimo do comprimento total.',
    source: 'https://www.bipm.org/en/si-base-units/metre', sourceLabel: 'BIPM · Definição do metro',
  },
  {
    id: 'terra', name: 'Terra', image: 'earth', extent: '12.756 km', meters: 12_756_000,
    dimension: 'Diâmetro equatorial',
    text: 'A gravidade mantém o ar perto da Terra. Na superfície, ela também faz objetos caírem em direção ao centro do planeta. A luz atravessaria uma distância igual ao diâmetro da Terra em cerca de 0,04 segundo.',
    alt: 'Globo terrestre iluminado, com oceanos, continentes e nuvens.',
    caption: 'Mapa terrestre MODIS da NASA. Iluminação ilustrativa.',
    source: 'https://science.nasa.gov/earth/facts/', sourceLabel: 'NASA · Terra',
  },
  {
    id: 'sistema-solar', name: 'Sistema Solar', image: 'solar-system', extent: '≈ 60 UA', meters: 60 * au,
    dimension: 'Diâmetro de referência até a órbita de Netuno',
    text: 'A gravidade do Sol curva as trajetórias dos planetas em órbitas. Uma unidade astronômica (UA) é aproximadamente a distância da Terra ao Sol. Netuno fica a cerca de 30 UA do Sol. Há corpos além dessa órbita.',
    alt: 'Oito planetas representados por esferas em torno do Sol, com tamanhos ampliados.',
    caption: 'Ilustração com o tamanho dos planetas e o espaçamento das órbitas ampliados.',
    source: 'https://science.nasa.gov/solar-system/planets/planet-sizes-and-locations-in-our-solar-system/', sourceLabel: 'NASA · Órbitas dos planetas',
  },
  {
    id: 'via-lactea', name: 'Via Láctea', image: 'galaxies', extent: '≈ 100 mil anos-luz', meters: 100_000 * lightYear,
    dimension: 'Diâmetro aproximado do disco estelar',
    text: 'O Sistema Solar fica longe do centro do disco galáctico. A gravidade mantém as estrelas em órbita, e os movimentos delas revelam o efeito da matéria escura. Um ano-luz mede a distância que a luz percorre em um ano.',
    alt: 'Galáxia espiral vista em perspectiva, com braços ao redor de um núcleo luminoso.',
    caption: 'Representação da Via Láctea de fora. A luz visível vem da matéria comum.',
    source: 'https://science.nasa.gov/universe/exoplanets/our-milky-way-galaxy-how-big-is-space/', sourceLabel: 'NASA · Via Láctea',
  },
  {
    id: 'grupo-local', name: 'Grupo Local', image: 'group-local', extent: '≈ 10 milhões de anos-luz', meters: 10_000_000 * lightYear,
    dimension: 'Extensão aproximada do grupo',
    text: 'A Via Láctea e Andrômeda são duas das maiores galáxias do Grupo Local. Dezenas de galáxias menores também fazem parte desse grupo mantido pela gravidade, mesmo num Universo em expansão.',
    alt: 'Conjunto ilustrado de galáxias, com duas espirais maiores.',
    caption: 'Ilustração. Posições e tamanhos aparentes estilizados.',
    source: 'https://science.nasa.gov/earth/earth-observatory/the-galaxy-next-door/', sourceLabel: 'NASA · Grupo Local',
  },
  {
    id: 'teia-cosmica', name: 'Teia cósmica', image: 'cosmic-web', extent: '≈ 500 milhões de anos-luz', meters: 500_000_000 * lightYear,
    dimension: 'Comprimento da Muralha de Coma, um exemplo',
    text: 'Com o tempo, a gravidade acumulou mais matéria nas regiões já densas. Galáxias, grupos e aglomerados desenham essa rede de filamentos e paredes. Entre eles, há vazios com menos galáxias.',
    alt: 'Rede tridimensional de aglomerados e filamentos separados por vazios.',
    caption: 'Ilustração da teia em geral. A medida se refere à Muralha de Coma.',
    source: 'https://science.nasa.gov/universe/galaxies/large-scale-structures/', sourceLabel: 'NASA · Estruturas em grande escala',
  },
  {
    id: 'universo-observavel', name: 'Universo observável', image: 'scale-horizon', extent: '≈ 93 bilhões de anos-luz', meters: 93_000_000_000 * lightYear,
    dimension: 'Diâmetro estimado hoje',
    text: 'Só vemos regiões de onde a luz teve tempo de chegar até nós. Enquanto ela viajava, o espaço se expandia. Os círculos marcam o alcance da observação em três direções. O Universo pode ir muito além desse horizonte.',
    alt: 'Volume esférico com galáxias dispersas e linhas que indicam o alcance da observação.',
    caption: 'Horizonte de observação ilustrativo em torno de quem observa.',
    source: 'https://kids.esa.int/the_universe/', sourceLabel: 'ESA · Universo observável',
  },
] as const;

export const scaleLogs = scaleStations.map(station => Math.log10(station.meters));
