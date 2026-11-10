import planck from '../assets/photos/planck-cmb.webp';
import lens from '../assets/photos/hubble-lens.webp';
import saturn from '../assets/photos/hubble-saturn.webp';
import { photos } from './images';
import { imageCredits } from '../data';
import type { ChapterId } from '../types';

interface CourseCover {
  image: ImageMetadata;
  caption: string;
  alt: string;
  source: { credit: string; href: string };
  position?: string;
}

export const additionalCoverCredits = [
  {
    title: 'Radiação cósmica de fundo',
    detail: 'Mapa de temperatura da publicação final da missão Planck, em cores atribuídas.',
    credit: 'ESA/Planck Collaboration.',
    href: 'https://www.esa.int/media/planck-s-view-of-the-cosmic-microwave-background-en-213137'
  },
  {
    title: 'Lente gravitacional GAL-CLUS-022058s',
    detail: 'Composição do Hubble. A gravidade do aglomerado distorce a imagem da galáxia de fundo.',
    credit: 'ESA/Hubble & NASA, S. Jha. Agradecimento a L. Shatz.',
    href: 'https://esahubble.org/images/potw2050a/'
  },
  {
    title: 'Retrato de Saturno',
    detail: 'Observação do Hubble de 20 de junho de 2019.',
    credit: 'NASA, ESA, A. Simon (Goddard Space Flight Center) e M.H. Wong (University of California, Berkeley).',
    href: 'https://esahubble.org/images/heic1917a/'
  }
];

export const courseCovers: Record<ChapterId, CourseCover> = {
  'galaxias-e-nebulosas': {
    image: photos['andromeda-wise'],
    caption: 'Andrômeda · WISE',
    source: imageCredits[0],
    alt: 'Mosaico infravermelho da galáxia de Andrômeda, com o núcleo brilhante e anéis de poeira.'
  },
  'origem-do-universo': {
    image: planck,
    caption: 'Fundo cósmico · Planck',
    source: additionalCoverCredits[0],
    alt: 'Mapa oval do céu inteiro com as flutuações de temperatura da radiação cósmica de fundo em cores atribuídas.'
  },
  'misterios-do-cosmos': {
    image: lens,
    caption: 'Lente gravitacional · Hubble',
    source: additionalCoverCredits[1],
    alt: 'Um arco dourado quase circular contorna as galáxias centrais do aglomerado GAL-CLUS-022058s.',
    position: '50% 48%'
  },
  'vida-das-estrelas': {
    image: photos['carina-cosmic-cliffs'],
    caption: 'Nebulosa de Carina · Webb',
    source: imageCredits[1],
    alt: 'Nuvens de gás e poeira recortam o campo estelar nos Penhascos Cósmicos da Nebulosa de Carina.',
    position: '50% 55%'
  },
  'sistema-solar': {
    image: saturn,
    caption: 'Saturno · Hubble',
    source: additionalCoverCredits[2],
    alt: 'Saturno em luz visível, com faixas na atmosfera e os anéis abertos em torno do planeta.'
  },
  'terra-e-atmosfera': {
    image: photos['iss-sunrise'],
    caption: 'Atmosfera terrestre · ISS',
    source: imageCredits[2],
    alt: 'Nascer do Sol visto da Estação Espacial Internacional, com faixas luminosas sobre a curvatura da Terra.'
  }
};
