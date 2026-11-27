import {
  C_KM_S,
  KM_POR_UA,
  MLY_POR_MPC,
  T_SOL,
  corCorpoNegro,
  distanciaLuzKm,
  formatar,
  luminosidadeMesmoRaio,
  massaContida,
  periodoAnos,
  picoWienNm,
  raioSchwarzschildKm,
  razaoAneis,
  redshiftDeEscala,
  temperaturaCmb,
} from './fisica';

export type Leitura = { rotulo: string; valor: string; unidade?: string };
export type Controle = {
  rotulo: string;
  unidade: string;
  min: number;
  max: number;
  passo: number;
  inicial: number;
  /** escala logarítmica no controle deslizante */
  log?: boolean;
  formato?: (v: number) => string;
};
export type Estacao = {
  id: string;
  rotulo: string;
  titulo: string;
  texto: string[];
  controle: Controle;
  leituras: (v: number) => Leitura[];
  nota: string;
  aprofundar: { href: string; texto: string }[];
};

const LUA_KM = 384400;
const IDA_LUA_S = LUA_KM / C_KM_S;
const KPC_KM = 3.0857e16;
const MYR_S = 3.15576e13;

function comprimento(nm: number): Leitura {
  if (nm >= 1e6) return { rotulo: 'Pico da emissão', valor: formatar(nm / 1e6), unidade: 'mm' };
  if (nm >= 1e4) return { rotulo: 'Pico da emissão', valor: formatar(nm / 1e3), unidade: 'µm' };
  return { rotulo: 'Pico da emissão', valor: formatar(nm), unidade: 'nm' };
}

/** Período orbital na última órbita estável, P = 2π 6^{3/2} GM/c³ ≈ (M/M☉)/2198 s. */
function duracao(s: number): { valor: string; unidade: string } {
  if (s < 1) return { valor: formatar(s * 1000), unidade: 'ms' };
  if (s < 120) return { valor: formatar(s), unidade: 's' };
  if (s < 7200) return { valor: formatar(s / 60), unidade: 'min' };
  if (s < 2 * 86400) return { valor: formatar(s / 3600), unidade: 'h' };
  return { valor: formatar(s / 86400), unidade: 'dias' };
}

function tipoEspectral(T: number) {
  if (T < 3700) return 'M';
  if (T < 5200) return 'K';
  if (T < 6000) return 'G';
  if (T < 7500) return 'F';
  if (T < 10000) return 'A';
  if (T < 30000) return 'B';
  return 'O';
}

export const PLANETAS: [string, number][] = [
  ['Mercúrio', 0.387],
  ['Vênus', 0.723],
  ['Terra', 1],
  ['Marte', 1.524],
  ['Júpiter', 5.2],
  ['Saturno', 9.58],
  ['Urano', 19.2],
  ['Netuno', 30.1],
];

export const estacoes: Estacao[] = [
  {
    id: 'luz',
    rotulo: 'Lua',
    titulo: 'A Lua fica a pouco mais de um segundo-luz',
    texto: [
      'Um pulso de laser disparado de um observatório volta da Lua cerca de 2,56 segundos depois, devolvido pelos refletores que as missões Apollo deixaram na superfície. Metade desse tempo, multiplicada pela velocidade da luz, dá a distância média de 384 400 km.',
      'Boa parte das distâncias da astronomia é medida assim, pelo tempo que a luz leva. Avance o pulso e acompanhe quantos quilômetros cabem em cada fração de segundo.',
    ],
    controle: { rotulo: 'Tempo desde o disparo', unidade: 's', min: 0, max: Math.round(IDA_LUA_S * 100) / 100, passo: 0.01, inicial: 0.64 },
    leituras: (t) => [
      { rotulo: 'Distância percorrida', valor: formatar(distanciaLuzKm(t)), unidade: 'km' },
      { rotulo: 'Fração do caminho até a Lua', valor: formatar((100 * t) / IDA_LUA_S), unidade: '%' },
    ],
    nota: 'Mapas da Terra e da Lua: NASA (Blue Marble Next Generation, julho de 2004, e LROC). Tamanhos e distância fora de escala; a Lua fica a 60 raios terrestres.',
    aprofundar: [
      { href: '/aulas/medir-com-a-luz/', texto: 'Quantos quilômetros cabem em um minuto de luz?' },
      { href: '/aulas/o-relogio-de-luz-do-sistema-solar/', texto: 'O relógio de luz do Sistema Solar' },
    ],
  },
  {
    id: 'sistema-solar',
    rotulo: 'Sistema Solar',
    titulo: 'Quanto mais longe do Sol, mais longo o ano',
    texto: [
      'Kepler publicou em 1619 que o quadrado do período de um planeta é proporcional ao cubo do tamanho da órbita. Com o período em anos e o semieixo maior em unidades astronômicas, a relação fica T² = a³.',
      'Os planetas da cena giram com os períodos relativos reais: enquanto Netuno completa uma volta, a Terra dá 165. Mude o semieixo da órbita clara e compare com o planeta mais próximo.',
    ],
    controle: { rotulo: 'Semieixo maior', unidade: 'UA', min: 0.3, max: 40, passo: 0.01, inicial: 1, log: true },
    leituras: (a) => {
      const T = periodoAnos(a);
      const perto = PLANETAS.reduce((m, p) => (Math.abs(Math.log(p[1] / a)) < Math.abs(Math.log(m[1] / a)) ? p : m));
      return [
        T < 2
          ? { rotulo: 'Período orbital', valor: formatar(T * 365.25), unidade: 'dias' }
          : { rotulo: 'Período orbital', valor: formatar(T), unidade: 'anos' },
        { rotulo: 'Planeta mais próximo', valor: `${perto[0]} (${formatar(perto[1])} UA)` },
      ];
    },
    nota: 'Mapas planetários: NASA/JPL-Caltech, Hubble (OPAL) e USGS. Tamanhos e distâncias comprimidos; os períodos seguem a proporção real.',
    aprofundar: [
      { href: '/aulas/o-periodo-revela-a-orbita/', texto: 'O que o período revela sobre a órbita?' },
      { href: '/laboratorios/orbitas/', texto: 'Laboratório de órbitas' },
    ],
  },
  {
    id: 'saturno',
    rotulo: 'Saturno',
    titulo: 'Duas vezes por órbita, os anéis somem de perfil',
    texto: [
      'Os anéis principais medem cerca de 270 mil km de diâmetro e, na maior parte, de dez metros a um quilômetro de espessura. O eixo de Saturno é inclinado 26,7°, então o ângulo com que a Terra vê o plano dos anéis muda ao longo dos 29,5 anos da órbita.',
      'Quando esse ângulo passa por zero, os anéis quase desaparecem num telescópio. Isso aconteceu em março de 2025 e volta a acontecer entre 2038 e 2039. Da Terra, o ângulo não passa de cerca de 27°; acima disso, só uma sonda vê.',
    ],
    controle: { rotulo: 'Inclinação do plano dos anéis', unidade: '°', min: 0, max: 90, passo: 0.5, inicial: 27 },
    leituras: (B) => [
      { rotulo: 'Eixo menor ÷ eixo maior', valor: formatar(razaoAneis(B)) },
      { rotulo: 'Largura aparente do anel externo', valor: formatar(273000 * razaoAneis(B)), unidade: 'km' },
    ],
    nota: 'Cores das faixas tiradas do mapa da NASA/JPL-Caltech e ampliadas no Blender com estrias geradas; divisões finas dos anéis e iluminação ilustrativas.',
    aprofundar: [
      { href: '/niveis/3/', texto: 'Nível 3 · Astronomia' },
      { href: '/laboratorios/gravitacao/', texto: 'Laboratório de gravitação' },
    ],
  },
  {
    id: 'estrelas',
    rotulo: 'Estrelas',
    titulo: 'A cor de uma estrela é um termômetro',
    texto: [
      'A superfície de uma estrela emite aproximadamente como um corpo negro. A lei de Wien liga o pico do espectro à temperatura: λ = 2,898 mm·K / T. O Sol, a 5 772 K, tem o pico perto de 500 nm e parece branco porque emite em todas as cores.',
      'Com o mesmo raio, a luminosidade cresce com a quarta potência da temperatura. Uma estrela duas vezes mais quente que o Sol brilharia 16 vezes mais.',
    ],
    controle: { rotulo: 'Temperatura da superfície', unidade: 'K', min: 2500, max: 40000, passo: 1, inicial: T_SOL, log: true },
    leituras: (T) => [
      comprimento(picoWienNm(T)),
      { rotulo: 'Luminosidade com o raio do Sol', valor: formatar(luminosidadeMesmoRaio(T)), unidade: '× Sol' },
      { rotulo: 'Tipo espectral', valor: tipoEspectral(T) },
    ],
    nota: 'Granulação e campo de estrelas gerados no Blender. Cor de corpo negro pelo ajuste de Tanner Helland.',
    aprofundar: [
      { href: '/aulas/temperatura-pela-cor-da-estrela/', texto: 'Temperatura pela cor da estrela' },
      { href: '/aulas/raio-estelar-por-luz-e-temperatura/', texto: 'Raio estelar por luz e temperatura' },
    ],
  },
  {
    id: 'buraco-negro',
    rotulo: 'Buraco negro',
    titulo: 'O horizonte cresce na proporção da massa',
    texto: [
      'O raio de Schwarzschild, r = 2GM/c², marca a superfície de onde nem a luz escapa. Para uma massa solar ele mede 2,95 km, e dobrar a massa dobra o raio.',
      'O gás que espirala para dentro forma um disco que brilha até cerca de três raios do horizonte, onde fica a última órbita circular estável. A gravidade curva a luz desse disco: a parte de trás aparece por cima e por baixo da sombra, e o lado que gira em nossa direção brilha mais, pelo efeito Doppler relativístico. A sombra mede cerca de 2,6 vezes o raio do horizonte.',
    ],
    controle: {
      rotulo: 'Massa',
      unidade: 'log₁₀ M/M☉',
      min: 0,
      max: 10,
      passo: 0.01,
      inicial: 6.63,
      formato: (v) => formatar(10 ** v) + ' M☉',
    },
    leituras: (lm) => {
      const r = raioSchwarzschildKm(10 ** lm);
      return [
        r > 0.05 * KM_POR_UA
          ? { rotulo: 'Raio do horizonte', valor: formatar(r / KM_POR_UA), unidade: 'UA' }
          : { rotulo: 'Raio do horizonte', valor: formatar(r), unidade: 'km' },
        { rotulo: 'Raio da sombra', ...(2.598 * r > 0.05 * KM_POR_UA ? { valor: formatar((2.598 * r) / KM_POR_UA), unidade: 'UA' } : { valor: formatar(2.598 * r), unidade: 'km' }) },
        { rotulo: 'Uma volta na última órbita estável', ...duracao((10 ** lm) / 2198) },
        { rotulo: 'Referência', valor: lm > 9 ? 'M87*: 6,5 × 10⁹ M☉' : lm > 5 ? 'Sagitário A*: 4,3 × 10⁶ M☉' : 'buraco negro estelar' },
      ];
    },
    nota: 'Imagem calculada em tempo real: cada pixel segue um raio de luz na geometria de Schwarzschild (sem rotação do buraco). Disco fino com o perfil de Shakura e Sunyaev e céu de fundo gerados no Blender. Arraste para mudar a inclinação. A aparência é a mesma para qualquer massa; só a escala muda.',
    aprofundar: [
      { href: '/aulas/o-tamanho-do-horizonte/', texto: 'Como a massa define o tamanho do horizonte?' },
      { href: '/aulas/a-ultima-orbita-circular-estavel/', texto: 'A última órbita circular estável' },
      { href: '/laboratorios/buracos-negros/', texto: 'Laboratório de buracos negros' },
    ],
  },
  {
    id: 'galaxias',
    rotulo: 'Galáxias',
    titulo: 'A velocidade das estrelas pesa a galáxia',
    texto: [
      'Numa órbita circular, a gravidade da massa interna fornece a força centrípeta: M = v²r/G. Nas espirais, a velocidade de rotação fica quase constante longe do centro, perto de 220 km/s na Via Láctea, e a massa contida continua crescendo com o raio.',
      'A luz das estrelas não acompanha esse crescimento. A diferença, medida por Vera Rubin e Kent Ford a partir de 1970, é uma das evidências mais antigas de matéria escura nas galáxias.',
    ],
    controle: { rotulo: 'Raio da órbita', unidade: 'kpc', min: 1, max: 25, passo: 0.1, inicial: 8 },
    leituras: (r) => [
      { rotulo: 'Massa dentro da órbita', valor: formatar(massaContida(r, 220)), unidade: 'M☉' },
      { rotulo: 'Uma volta a 220 km/s', valor: formatar((2 * Math.PI * r * KPC_KM) / 220 / MYR_S), unidade: 'milhões de anos' },
    ],
    nota: 'Espiral barrada inspirada em NGC 1300; as posições das estrelas são geradas por um modelo de disco, barra e bojo.',
    aprofundar: [
      { href: '/aulas/pesar-galaxias-com-orbitas/', texto: 'Pesar galáxias com órbitas' },
      { href: '/aulas/um-disco-galactico-em-aneis/', texto: 'Um disco galáctico em anéis' },
      { href: '/laboratorios/rotacao/', texto: 'Laboratório de rotação' },
    ],
  },
  {
    id: 'teia-cosmica',
    rotulo: 'Teia cósmica',
    titulo: 'As galáxias formam filamentos em volta de vazios',
    texto: [
      'Levantamentos de redshift como o SDSS e o DESI mostram que as galáxias não se espalham ao acaso: elas se alinham em filamentos e paredes que se cruzam em aglomerados, em volta de vazios com dezenas de megaparsecs. A estrutura cresceu por gravidade a partir de flutuações pequenas na densidade do Universo jovem.',
      'A região da cena tem 124 Mpc de diâmetro, recortada de uma caixa de 160 Mpc. Escolha um comprimento e compare com o tamanho da nossa galáxia.',
    ],
    controle: { rotulo: 'Comprimento', unidade: 'Mpc', min: 1, max: 124, passo: 1, inicial: 40 },
    leituras: (d) => [
      { rotulo: 'Em anos-luz', valor: formatar(d * MLY_POR_MPC * 1e6) },
      { rotulo: 'Discos da Via Láctea enfileirados', valor: formatar(d / 0.03) },
    ],
    nota: 'Distribuição gerada no Blender pela aproximação de Zel’dovich: um campo gaussiano com o espectro da matéria escura fria desloca 2 milhões de partículas numa caixa de 160 Mpc. Não é um mapa observado.',
    aprofundar: [
      { href: '/aulas/crescimento-de-uma-sobredensidade/', texto: 'Crescimento de uma sobredensidade' },
      { href: '/aulas/tamanho-de-uma-perturbacao/', texto: 'Tamanho de uma perturbação' },
      { href: '/laboratorios/estruturas/', texto: 'Laboratório de estruturas' },
    ],
  },
  {
    id: 'expansao',
    rotulo: 'Expansão',
    titulo: 'O espaço entre as galáxias aumenta',
    texto: [
      'As distâncias entre galáxias afastadas crescem na proporção do fator de escala a(t). As galáxias em si não aumentam, porque a gravidade de cada uma a mantém coesa. Por definição, a vale 1 hoje.',
      'A luz que viaja durante a expansão chega esticada pelo mesmo fator. Emitida quando a valia 0,5, ela chega com o dobro do comprimento de onda, desvio para o vermelho z = 1.',
    ],
    controle: { rotulo: 'Fator de escala', unidade: '', min: 0.3, max: 1, passo: 0.01, inicial: 1 },
    leituras: (a) => [
      { rotulo: 'Desvio para o vermelho da luz emitida', valor: 'z = ' + formatar(redshiftDeEscala(a)) },
      { rotulo: 'Hα emitida em 656 nm chega em', valor: formatar(656.3 / a), unidade: 'nm' },
      { rotulo: 'Separação entre vizinhas', valor: formatar(22 * a), unidade: 'Mpc' },
    ],
    nota: 'Grade de galáxias ilustrativa, 22 Mpc entre vizinhas hoje.',
    aprofundar: [
      { href: '/aulas/ler-a-expansao-em-uma-linha/', texto: 'Ler a expansão em uma linha' },
      { href: '/aulas/inclinacao-do-diagrama-de-hubble/', texto: 'Inclinação do diagrama de Hubble' },
      { href: '/laboratorios/expansao/', texto: 'Laboratório de expansão' },
    ],
  },
  {
    id: 'luz-fossil',
    rotulo: 'Luz fóssil',
    titulo: 'A luz mais antiga chega de todas as direções',
    texto: [
      'Cerca de 380 mil anos depois do início da expansão, o Universo esfriou o bastante para os elétrons se ligarem aos núcleos, e a luz passou a viajar livre. A radiação estava então perto de 3 000 K. Esticada desde z ≈ 1100, ela chega hoje a 2,7255 K, nas micro-ondas.',
      'As manchas variam a temperatura em poucas partes em cem mil. O tamanho típico delas, cerca de um grau no céu, guarda a geometria e a composição do Universo.',
    ],
    controle: {
      rotulo: 'Redshift',
      unidade: '',
      min: 0,
      max: 1100,
      passo: 1,
      inicial: 0,
      formato: (z) => 'z = ' + formatar(Math.round(z)),
    },
    leituras: (z) => [
      { rotulo: 'Temperatura da radiação', valor: formatar(temperaturaCmb(z)), unidade: 'K' },
      comprimento(picoWienNm(temperaturaCmb(z))),
      { rotulo: 'Brilho visível a olho nu', valor: temperaturaCmb(z) > 800 ? 'sim, acima de ~800 K' : 'não, só em infravermelho ou micro-ondas' },
    ],
    nota: 'Mapa sintético com espectro de potência semelhante ao medido pelo Planck; não é o mapa observado.',
    aprofundar: [
      { href: '/aulas/temperatura-da-luz-fossil/', texto: 'Temperatura da luz fóssil' },
      { href: '/aulas/escalas-angulares-no-ceu/', texto: 'Escalas angulares no céu' },
      { href: '/laboratorios/cmb/', texto: 'Laboratório da radiação cósmica de fundo' },
    ],
  },
];

export { corCorpoNegro };
