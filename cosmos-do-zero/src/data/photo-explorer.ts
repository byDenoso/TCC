/**
 * "Leia a imagem": pontos explicativos sobre as três imagens reais do site.
 * Posições em porcentagem da imagem original (x da esquerda, y do topo).
 * Cada afirmação vem da página da NASA indicada em site.json (credits), conferida em 10/11/2026;
 * as marcadas com `general` são fatos de óptica ou de órbita que a página da imagem não descreve.
 */
export type PhotoKey = 'carina-cosmic-cliffs' | 'andromeda-wise' | 'iss-sunrise';

export interface PhotoSpot { x: number; y: number; trace: string; title: string; text: string; general?: boolean }
export interface PhotoStory {
  key: PhotoKey;
  /** Índice do crédito em site.json. */
  credit: number;
  tab: string;
  title: string;
  lede: string;
  facts: { label: string; value: string }[];
  spots: PhotoSpot[];
}

export const photoStories: PhotoStory[] = [
  {
    key: 'carina-cosmic-cliffs', credit: 1,
    tab: 'Nebulosa de Carina',
    title: 'Um berçário de estrelas',
    lede: 'Esta parede de gás e poeira fica na borda de uma região onde estrelas estão nascendo. O telescópio Webb a registrou em luz infravermelha, que atravessa a poeira.',
    facts: [
      { label: 'Onde', value: 'NGC 3324, na Nebulosa de Carina' },
      { label: 'Distância', value: 'cerca de 7.600 anos-luz' },
      { label: 'Telescópio', value: 'James Webb (NIRCam e MIRI)' },
      { label: 'Tipo de luz', value: 'infravermelho, em cores atribuídas' }
    ],
    spots: [
      { x: 30, y: 44, trace: 'M22 28Q26 24 30 27T35 26L38 30M30 27V40', title: 'Os “penhascos”', text: 'A borda de uma grande cavidade de gás e poeira. Os picos mais altos desta imagem têm cerca de 7 anos-luz de altura.' },
      { x: 70, y: 13, trace: 'M70 22V3M67.7 9L70 3L72.3 9', title: 'Quem esculpiu a parede', text: 'Radiação ultravioleta intensa e ventos de estrelas jovens, quentes e muito massivas. Elas ficam no centro da bolha, acima da área mostrada.' },
      { x: 85, y: 82, trace: 'M84 91Q89 79 85.5 67M83.8 76L85.5 67L88.1 73', title: 'O “vapor” que sobe', text: 'Gás quente ionizado e poeira quente escapando da nebulosa, empurrados pela radiação ultravioleta.' },
      { x: 54, y: 58, trace: 'M49 52V46H51.5M56.5 46H59V52M59 64V70H56.5M51.5 70H49V64', title: 'Estrelas recém-nascidas', text: 'O infravermelho revela áreas de nascimento de estrelas que a luz visível esconde. O instrumento NIRCam mostrou centenas de estrelas antes ocultas.' },
      { x: 36, y: 27, trace: 'M36 13V22M36 32V41M31 27H34M38 27H41M32.5 17L34.7 23M37.3 31L39.5 37M32.5 37L34.7 31M37.3 23L39.5 17', title: 'As pontas da estrela', text: 'As pontas não fazem parte da estrela. Elas surgem quando a luz de um ponto muito brilhante passa pelos espelhos e pelas hastes do telescópio.', general: true }
    ]
  },
  {
    key: 'andromeda-wise', credit: 0,
    tab: 'Galáxia de Andrômeda',
    title: 'A vizinha da Via Láctea',
    lede: 'Andrômeda é a grande galáxia mais próxima da nossa. Neste mosaico em infravermelho, cada cor mostra um ingrediente diferente da galáxia.',
    facts: [
      { label: 'Distância', value: '2,5 milhões de anos-luz' },
      { label: 'Telescópio', value: 'WISE (quatro detectores)' },
      { label: 'Tipo de luz', value: 'infravermelho, em cores atribuídas' },
      { label: 'Azul / amarelo e vermelho', value: 'estrelas maduras / poeira aquecida' }
    ],
    spots: [
      { x: 50, y: 50, trace: 'M43 47C44 43 60 51 57 55S41 51 43 47Z', title: 'O centro azulado', text: 'O azul destaca estrelas maduras. Elas formam a espinha enevoada que atravessa a galáxia.' },
      { x: 62, y: 57.5, trace: 'M57 49Q67 54 65 58Q63 62 52 58', title: 'Os anéis amarelos e vermelhos', text: 'Poeira aquecida por estrelas massivas recém-nascidas. É nesses braços que novas estrelas estão se formando.' },
      { x: 46, y: 42.8, trace: 'M46 38.5A4.3 4.3 0 1 1 45.99 38.5Z', title: 'M32, uma galáxia satélite', text: 'Uma pequena galáxia presa a Andrômeda pela gravidade. Ela aparece logo acima do disco, à esquerda do centro.' },
      { x: 45.8, y: 61.6, trace: 'M45.8 56.2A3.8 5.4 0 1 1 45.79 56.2Z', title: 'M110, outra satélite', text: 'A mancha azul difusa abaixo do centro. M32 e M110 são as maiores entre as várias galáxias ligadas a Andrômeda.' }
    ]
  },
  {
    key: 'iss-sunrise', credit: 2,
    tab: 'A Terra vista da órbita',
    title: 'Um nascer do Sol em órbita',
    lede: 'Fotografia feita por um astronauta na Estação Espacial Internacional. Vista de lado, a atmosfera que nos protege aparece como uma faixa fina.',
    facts: [
      { label: 'De onde', value: 'Estação Espacial Internacional' },
      { label: 'Data', value: '29 de setembro de 2023' },
      { label: 'Tipo de luz', value: 'luz visível (fotografia)' },
      { label: 'Tratamento', value: 'recorte e contraste realçado' }
    ],
    spots: [
      { x: 49.5, y: 51.5, trace: 'M42 52.5L44 52.4M45 52.3A4.5 6 0 1 1 54 52.3A4.5 6 0 1 1 45 52.3M55 52.2L57 52.1', title: 'O Sol no horizonte', text: 'A estação dá uma volta na Terra a cada 90 minutos, aproximadamente. Por isso a tripulação vê cerca de 16 nasceres do Sol por dia.', general: true },
      { x: 26, y: 50.5, trace: 'M16 53Q26 52 36 51M16 55.8Q26 54.8 36 53.8M16 53V55.8M36 51V53.8', title: 'A faixa alaranjada', text: 'Perto do horizonte a luz atravessa muito mais ar. O azul se espalha pelo caminho, e chegam à câmera o laranja e o vermelho.', general: true },
      { x: 76, y: 42.5, trace: 'M66 41Q76 40 86 39M66 46Q76 45 86 44M66 41V46M86 39V44', title: 'A faixa azul', text: 'Mais acima o ar é mais rarefeito e espalha principalmente a luz azul, a mesma que deixa o céu azul visto do chão.', general: true },
      { x: 50, y: 14, trace: 'M43 11V7H46M54 7H57V11M57 17V21H54M46 21H43V17', title: 'O espaço escuro', text: 'Acima da atmosfera quase não há ar para espalhar a luz. O céu fica preto mesmo com o Sol à vista.', general: true }
    ]
  }
];
