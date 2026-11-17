import type { ChapterId } from '../types';

type Folio = {
  subject: string;
  question: string;
  station: string;
  bench: string;
  observation: string;
  prediction: string;
};

export const folios: Record<ChapterId, Folio> = {
  'galaxias-e-nebulosas': {
    subject: 'Galáxias e distâncias', question: 'Onde estamos no Universo?',
    station: 'paralaxe', bench: 'Paralaxe estelar',
    observation: 'No mosaico infravermelho de Andrômeda, a poeira desenha anéis em torno do núcleo. Da Terra, vemos esse disco inclinado.',
    prediction: 'Com a mesma órbita de observação, o que acontece com a paralaxe quando uma estrela está duas vezes mais longe?'
  },
  'origem-do-universo': {
    subject: 'Tempo e expansão', question: 'Como o Universo evoluiu?',
    station: 'expansao-modelos', bench: 'História da expansão',
    observation: 'Cada região do mapa de Planck corresponde a uma direção no céu. As cores ampliam diferenças de temperatura na luz antiga.',
    prediction: 'Para um mesmo modelo, como muda o fator de escala na emissão quando aumentamos o redshift?'
  },
  'misterios-do-cosmos': {
    subject: 'Luz e gravidade', question: 'Como sabemos disso?',
    station: 'lente-gravitacional', bench: 'Lentes gravitacionais',
    observation: 'O arco ao redor do aglomerado é a imagem distorcida de uma galáxia mais distante. Sua forma depende do alinhamento e da massa no caminho.',
    prediction: 'Que forma aparece quando fonte, lente simétrica e observador ficam alinhados?'
  },
  'vida-das-estrelas': {
    subject: 'Evolução estelar', question: 'Por que uma estrela brilha?',
    station: 'diagrama-hr', bench: 'Temperatura e luminosidade',
    observation: 'Em Carina, o contorno iluminado marca a borda de uma cavidade no gás. Estrelas jovens alteram a nuvem em que nasceram.',
    prediction: 'A temperatura fica fixa. O que acontece com a luminosidade se o raio estelar dobrar?'
  },
  'sistema-solar': {
    subject: 'Mundos em órbita', question: 'O que governa a órbita de um planeta?',
    station: 'orbitas', bench: 'Órbitas de Kepler',
    observation: 'A inclinação dos anéis de Saturno revela o plano de suas órbitas. Observe a faixa de sombra projetada no planeta.',
    prediction: 'Em uma órbita elíptica, o planeta passa mais rápido perto ou longe do Sol?'
  },
  'terra-e-atmosfera': {
    subject: 'A Terra vista de fora', question: 'Como a Terra se tornou nossa casa?',
    station: 'comparador', bench: 'Comparar mundos',
    observation: 'Vista da estação espacial, a atmosfera forma uma faixa luminosa sobre o horizonte. A luz atravessa mais ar nessa direção.',
    prediction: 'Na mesma escala, quantas vezes o diâmetro de Júpiter supera o da Terra?'
  }
};
