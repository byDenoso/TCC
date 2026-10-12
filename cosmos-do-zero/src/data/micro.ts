/**
 * Microexperiências: uma por subseção. Padrão: pergunta → palpite → mexer → observar → explicar → verificar.
 * Este arquivo só tem o texto (renderizado no servidor). O desenho de cada cena fica em src/scripts/micro/.
 */
export type MicroControl =
  | { kind: 'range'; label: string; min: number; max: number; step: number; value: number }
  | { kind: 'stages'; label: string; options: string[] }
  | { kind: 'choice'; label: string; options: string[] };
export interface MicroQuiz { q: string; options: string[]; right: number; why: string }
export interface MicroSpec {
  /** Pergunta humana que abre a cena */
  ask: string;
  guess: MicroQuiz;
  control: MicroControl;
  /** Descrição estática equivalente (sem JavaScript ou antes da cena carregar) */
  alt: string;
  /** O que o desenho omite ou exagera */
  limit: string;
  /** Pergunta de transferência */
  check: MicroQuiz;
}

const stages = (label: string, ...options: string[]): MicroControl => ({ kind: 'stages', label, options });
const choice = (label: string, ...options: string[]): MicroControl => ({ kind: 'choice', label, options });
const range = (label: string, min: number, max: number, step: number, value = min): MicroControl => ({ kind: 'range', label, min, max, step, value });

export const MICRO: Record<string, MicroSpec> = {
  // ── A. Onde estamos no Universo? ──
  'galaxias-e-nebulosas-via-lactea': {
    ask: 'Qual é o seu endereço completo no Universo?',
    guess: { q: 'O Sol fica…', options: ['no centro da Via Láctea', 'num braço da galáxia, longe do centro', 'fora de qualquer galáxia'], right: 1, why: 'O Sol está num dos braços da Via Láctea, a uns 26 mil anos-luz do centro.' },
    control: stages('Afastar a câmera', 'Terra', 'Sistema Solar', 'Via Láctea', 'Grupo Local', 'Teia cósmica'),
    alt: 'Cinco degraus de zoom: Terra, Sistema Solar, Via Láctea, Grupo Local e teia cósmica. Em cada degrau, o anterior vira um ponto minúsculo.',
    limit: 'Os degraus não estão em escala; o salto de tamanho varia entre eles.',
    check: { q: 'O que é maior?', options: ['A Via Láctea', 'O Grupo Local', 'O Sistema Solar'], right: 1, why: 'O Grupo Local reúne a Via Láctea, Andrômeda e dezenas de galáxias menores.' }
  },
  'galaxias-e-nebulosas-tipos': {
    ask: 'Do que é feita uma galáxia?',
    guess: { q: 'Uma galáxia é…', options: ['uma estrela gigante com planetas', 'bilhões de estrelas, gás e poeira presos pela gravidade', 'uma nuvem de gás colorida'], right: 1, why: 'Uma galáxia junta estrelas, gás, poeira e uma massa invisível que só percebemos pela gravidade.' },
    control: stages('Montar a galáxia', 'Estrelas', '+ gás e poeira', '+ massa invisível', 'Outra forma: elíptica'),
    alt: 'Uma galáxia montada em camadas: primeiro estrelas, depois gás e poeira, depois um halo de matéria escura inferido. Por fim, uma galáxia elíptica, sem braços.',
    limit: 'O halo de matéria escura é invisível de verdade; a névoa desenhada só marca onde a gravidade indica massa. Galáxias não mudam de forma numa ordem fixa.',
    check: { q: 'O Sistema Solar está dentro da Via Láctea ou o contrário?', options: ['O Sistema Solar está dentro da Via Láctea', 'A Via Láctea está dentro do Sistema Solar', 'São a mesma coisa'], right: 0, why: 'O Sistema Solar é um dos bilhões de sistemas dentro da Via Láctea.' }
  },
  'galaxias-e-nebulosas-teia-cosmica': {
    ask: 'Como as galáxias se espalham pelo espaço?',
    guess: { q: 'Num mapa de milhões de galáxias, elas aparecem…', options: ['espalhadas por igual', 'em fios e nós, com grandes vazios', 'todas juntas numa bola'], right: 1, why: 'A gravidade puxou pequenas diferenças iniciais e formou fios, nós e vazios.' },
    control: range('Deixar a gravidade agir', 0, 1, 0.01, 0),
    alt: 'Pontos quase uniformes se juntam aos poucos em filamentos e nós, deixando regiões vazias entre eles.',
    limit: 'Simulação esquemática, não fotografia. O padrão real é em três dimensões e levou bilhões de anos.',
    check: { q: 'Um "vazio" cósmico é…', options: ['uma região com poucas galáxias', 'um buraco sem espaço', 'a borda do Universo'], right: 0, why: 'Vazios têm poucas galáxias, mas são espaço normal.' }
  },
  'galaxias-e-nebulosas-nebulosas': {
    ask: 'Por que algumas nuvens brilham e outras escurecem o céu?',
    guess: { q: 'Uma nuvem de gás e poeira pode…', options: ['só brilhar', 'só escurecer', 'brilhar ou escurecer, conforme a luz e a posição'], right: 2, why: 'Depende de onde está a estrela e de onde está você.' },
    control: choice('Tipo de nebulosa', 'Emissão', 'Reflexão', 'Escura'),
    alt: 'Três situações: uma estrela quente faz o gás brilhar com luz própria; a poeira rebate a luz de uma estrela; uma nuvem na frente esconde as estrelas de trás.',
    limit: 'Cores e tamanhos simplificados. Nebulosas reais misturam os três efeitos.',
    check: { q: 'Uma nuvem escura na frente de muitas estrelas aparece como…', options: ['uma mancha escura no céu estrelado', 'uma estrela muito brilhante', 'um arco-íris'], right: 0, why: 'A poeira bloqueia a luz de trás.' }
  },
  'galaxias-e-nebulosas-gas-e-estrelas': {
    ask: 'Quando você olha uma estrela, vê ela agora?',
    guess: { q: 'Quando você olha o Sol, vê ele…', options: ['exatamente agora', 'como era há uns 8 minutos', 'como era há 8 anos'], right: 1, why: 'A luz do Sol leva cerca de 8 minutos e 20 segundos para chegar.' },
    control: choice('De onde vem a luz', 'Lua', 'Sol', 'Estrela vizinha'),
    alt: 'Um pulso de luz sai da fonte e chega até você. Lua: 1,3 segundo. Sol: 8 minutos e 20 segundos. Estrela mais próxima: 4,2 anos.',
    limit: 'O pulso anda em poucos segundos na tela; os tempos reais estão no texto. Distâncias fora de escala.',
    check: { q: 'A luz de uma estrela a 100 anos-luz que chega hoje saiu há…', options: ['100 anos', '100 dias', '1 ano'], right: 0, why: 'Ano-luz é distância: 100 anos-luz = 100 anos de viagem da luz.' }
  },
  'galaxias-e-nebulosas-centros-galacticos': {
    ask: 'O Universo observável tem uma parede no fim?',
    guess: { q: 'O limite do que conseguimos ver é…', options: ['uma parede onde o Universo acaba', 'até onde a luz teve tempo de chegar até nós', 'a borda da Via Láctea'], right: 1, why: 'É um horizonte: depende de onde está quem observa.' },
    control: choice('Onde está o observador', 'Nós', 'Galáxia à direita', 'Galáxia acima'),
    alt: 'O círculo do horizonte acompanha o observador. Quando o observador muda de galáxia, o círculo muda junto; as galáxias continuam além dele.',
    limit: 'O círculo é muito menor que o real, e o desenho é plano. Não sabemos se o Universo inteiro tem fim.',
    check: { q: 'Um observador numa galáxia muito distante teria…', options: ['o mesmo horizonte que nós', 'o próprio horizonte, centrado nele', 'nenhum horizonte'], right: 1, why: 'Cada observador tem seu horizonte, como cada barco no mar vê até a própria linha do horizonte.' }
  },

  // ── B. Como o Universo evoluiu? ──
  'origem-do-universo-o-universo': {
    ask: 'Se tudo se afasta, existe um centro?',
    guess: { q: 'Quando o espaço cresce, o Sistema Solar…', options: ['cresce junto', 'fica do mesmo tamanho, preso pela gravidade', 'encolhe'], right: 1, why: 'Sistemas presos pela gravidade não acompanham a expansão.' },
    control: range('Quanto o espaço cresceu', 1, 2, 0.01, 1),
    alt: 'Uma malha de galáxias cresce: todas se afastam umas das outras. Um sistema preso pela gravidade, no canto, continua do mesmo tamanho.',
    limit: 'Malha plana e regular para facilitar. O Universo real é tridimensional e as galáxias também têm movimentos próprios.',
    check: { q: 'De qualquer galáxia, um observador veria…', options: ['as outras se afastando, como nós vemos', 'tudo vindo na direção dele', 'que ele está no centro, e só ele'], right: 0, why: 'Não há centro: cada ponto vê o mesmo padrão.' }
  },
  'origem-do-universo-expansao': {
    ask: 'Como a luz conta que o espaço cresceu?',
    guess: { q: 'Se o espaço cresce enquanto a luz viaja, a onda chega…', options: ['mais curta (mais azul)', 'mais longa (mais vermelha)', 'igual'], right: 1, why: 'A onda é esticada junto com o espaço: isso é o redshift.' },
    control: range('Quanto o espaço cresceu na viagem', 1, 3, 0.01, 1),
    alt: 'Uma onda emitida e a mesma onda recebida, mais esticada. As linhas escuras do espectro andam para o lado vermelho.',
    limit: 'Ondas desenhadas gigantes. Movimentos próprios das galáxias também mudam um pouco a cor.',
    check: { q: 'A luz de uma galáxia mais distante tende a chegar…', options: ['mais esticada', 'menos esticada', 'sem mudança'], right: 0, why: 'Viajou por mais tempo enquanto o espaço crescia.' }
  },
  'origem-do-universo-fase-quente': {
    ask: 'O que existia nos primeiros minutos?',
    guess: { q: 'Nos primeiros minutos surgiram…', options: ['átomos completos', 'só núcleos leves, como hidrogênio e hélio', 'as primeiras estrelas'], right: 1, why: 'Estava quente demais para os elétrons ficarem presos: só núcleos se formaram.' },
    control: stages('Avançar no tempo', '1 segundo', '3 minutos', '20 minutos', '380 mil anos'),
    alt: 'Prótons e nêutrons soltos se juntam em núcleos de hélio nos primeiros minutos. Só centenas de milhares de anos depois os elétrons se prendem e surgem átomos.',
    limit: 'Pouquíssimas partículas desenhadas. Na mistura real, cerca de 3 em cada 4 partes da massa ficaram como hidrogênio.',
    check: { q: 'Qual a diferença entre núcleo e átomo?', options: ['Átomo é o núcleo com elétrons presos em volta', 'São a mesma coisa', 'Núcleo é maior que o átomo'], right: 0, why: 'Os núcleos vieram em minutos; os átomos, centenas de milhares de anos depois.' }
  },
  'origem-do-universo-primeira-luz': {
    ask: 'Por que a luz mais antiga demorou para viajar?',
    guess: { q: 'Antes de o Universo ficar transparente, havia luz?', options: ['Não, a luz nasceu ali', 'Sim, mas ela batia em tudo e não ia longe'], right: 1, why: 'Elétrons soltos desviavam a luz o tempo todo, como neblina.' },
    control: stages('Avançar no tempo', 'Névoa quente', 'Átomos se formam', 'Luz viaja livre', 'Chega hoje esticada'),
    alt: 'Na névoa, a luz ziguezagueia entre elétrons soltos. Quando os átomos se formam, ela segue reto e, com a expansão, chega hoje como micro-ondas.',
    limit: 'Poucos fótons e elétrons desenhados; a formação dos átomos foi gradual, ao longo de dezenas de milhares de anos.',
    check: { q: 'Por que essa luz antiga chega como micro-ondas?', options: ['Seu comprimento de onda cresceu com a expansão do espaço', 'Ela perdeu energia batendo em poeira', 'Sempre foi micro-ondas'], right: 0, why: 'O comprimento de onda cresceu cerca de 1 100 vezes junto com as distâncias: do infravermelho próximo, a radiação passou às micro-ondas.' }
  },
  'origem-do-universo-primeiras-estruturas': {
    ask: 'Como um Universo quase liso virou galáxias?',
    guess: { q: 'O que veio primeiro?', options: ['O Universo ficar transparente', 'As primeiras estrelas', 'As galáxias de hoje'], right: 0, why: 'Primeiro a luz se soltou (380 mil anos); estrelas vieram dezenas a centenas de milhões de anos depois.' },
    control: range('Tempo depois do Big Bang', 0, 1, 0.01, 0),
    alt: 'Regiões um pouco mais densas crescem, juntam gás, acendem as primeiras estrelas e abrem bolhas de gás ionizado ao redor.',
    limit: 'As datas das primeiras estrelas ainda são incertas; a faixa no eixo mostra essa incerteza.',
    check: { q: 'A ordem certa é…', options: ['transparência → primeiras estrelas → galáxias maiores', 'galáxias → transparência → estrelas', 'estrelas → Big Bang → transparência'], right: 0, why: 'A gravidade precisou de tempo para juntar matéria.' }
  },
  'origem-do-universo-nossa-epoca': {
    ask: 'Até onde a história do começo é medida, e onde vira hipótese?',
    guess: { q: 'A inflação cósmica é…', options: ['observada diretamente', 'uma hipótese bem estudada, ainda não confirmada', 'um fato do dia a dia'], right: 1, why: 'Ela explica várias coisas, mas ainda não há prova direta.' },
    control: stages('O que mostrar', 'Evidências', 'Cálculo do modelo', 'Hipótese: inflação', 'Antes disso'),
    alt: 'Uma linha do tempo: trechos firmes onde há medidas, trecho calculado pelo modelo, trecho hachurado de hipótese e um ponto de interrogação no começo.',
    limit: 'Escala de tempo comprimida; a parte inicial durou frações minúsculas de segundo.',
    check: { q: '"Os núcleos leves se formaram nos primeiros minutos" é…', options: ['apoiado por medidas da quantidade de hélio e deutério', 'hipótese sem evidência', 'opinião'], right: 0, why: 'As quantidades medidas batem com o cálculo.' }
  },

  // ── C. Como sabemos disso? ──
  'misterios-do-cosmos-horizonte': {
    ask: 'Como uma luz fraca vira uma conclusão científica?',
    guess: { q: '"A expansão está acelerando" é…', options: ['uma medida direta', 'uma conclusão tirada de muitas medidas com um modelo', 'uma opinião'], right: 1, why: 'Medimos brilho e cor; o modelo transforma isso em conclusão.' },
    control: stages('Seguir a pista', 'Luz chega', 'Espectro', 'Comparar com modelos', 'Conclusão e pergunta'),
    alt: 'Quatro etapas: o telescópio recebe luz, ela vira um espectro, o espectro é comparado com modelos e sai uma conclusão, junto com perguntas abertas.',
    limit: 'Cada etapa real envolve calibrações e equipes inteiras.',
    check: { q: '"Do que é feita a energia escura?" é…', options: ['uma medida', 'uma inferência', 'uma pergunta aberta'], right: 2, why: 'Sabemos do efeito, não da natureza.' }
  },
  'misterios-do-cosmos-exoplanetas': {
    ask: 'Uma galáxia só basta para provar a expansão?',
    guess: { q: 'Toda galáxia mostra luz avermelhada?', options: ['Sim, todas', 'Não: vizinhas podem até se aproximar'], right: 1, why: 'Andrômeda vem na nossa direção: a gravidade local vence a expansão.' },
    control: choice('Galáxia observada', 'Andrômeda (vizinha)', 'Média distância', 'Muito distante'),
    alt: 'Linhas do espectro de laboratório e da galáxia. Andrômeda chega um pouco azulada; galáxias distantes chegam bem avermelhadas.',
    limit: 'Espectros inventados para o exemplo; os deslocamentos estão exagerados para aparecer.',
    check: { q: 'Por que se usam muitas galáxias distantes?', options: ['Movimentos próprios atrapalham nas próximas', 'Galáxias próximas não emitem luz', 'Por tradição'], right: 0, why: 'Longe, a expansão domina; perto, os movimentos locais confundem.' }
  },
  'misterios-do-cosmos-vida': {
    ask: 'O que as manchas do mapa da luz antiga significam?',
    guess: { q: 'As cores fortes do mapa mostram…', options: ['diferenças minúsculas de temperatura, exageradas', 'cores reais que veríamos', 'nuvens da Via Láctea'], right: 0, why: 'As diferenças são de centésimos de milésimo de grau; as cores são atribuídas.' },
    control: stages('Tratar o mapa', 'Céu bruto', 'Tirar a Via Láctea', 'Realçar contraste', 'Sem realce'),
    alt: 'Um céu simulado com a faixa da Via Láctea na frente. Ao retirar a faixa e realçar o contraste, aparecem manchas; sem realce, o céu parece liso.',
    limit: 'Mapa simulado só para o exercício, não o mapa real do satélite Planck.',
    check: { q: 'Por que é preciso retirar a Via Láctea do mapa?', options: ['Ela brilha na frente e esconde parte do sinal antigo', 'Ela não existe naquela luz', 'Para ficar bonito'], right: 0, why: 'Nossa galáxia emite micro-ondas também.' }
  },
  'misterios-do-cosmos-materia-escura': {
    ask: 'Como sabemos que há massa que não brilha?',
    guess: { q: 'Estrelas longe do centro de uma galáxia giram…', options: ['bem mais devagar, como prevê a matéria que brilha', 'quase tão rápido quanto as de dentro'], right: 1, why: 'Esse é o sinal: precisa de mais massa do que vemos.' },
    control: stages('Comparar', 'Previsão: só o que brilha', 'O que se mede', 'Com massa invisível'),
    alt: 'Gráfico de velocidade contra distância ao centro: a previsão cai, a medida fica quase plana. Um halo de massa invisível explica a diferença.',
    limit: 'Curvas suavizadas. A matéria escura é inferida pela gravidade; a partícula ainda não foi identificada.',
    check: { q: 'Já sabemos de que partícula é feita a matéria escura?', options: ['Sim', 'Não, só conhecemos o efeito gravitacional'], right: 1, why: 'É uma das grandes perguntas abertas.' }
  },
  'misterios-do-cosmos-energia-escura': {
    ask: 'Como se descobriu que a expansão acelera?',
    guess: { q: 'Supernovas distantes pareceram…', options: ['mais fracas do que um Universo freando previa', 'mais brilhantes do que o previsto', 'iguais ao previsto'], right: 0, why: 'Mais fracas = mais longe = a expansão acelerou.' },
    control: stages('Montar o gráfico', 'Medidas', 'Modelo freando', 'Modelo acelerando'),
    alt: 'Pontos com barras de erro comparados a dois modelos. Sozinho, um ponto não decide; juntos, ficam mais perto do modelo com aceleração.',
    limit: 'Dados inventados no formato dos reais, para mostrar a ideia.',
    check: { q: 'Por que uma só supernova não basta?', options: ['Cada medida tem erro; muitas juntas mostram a tendência', 'Supernovas mentem', 'Basta, sim'], right: 0, why: 'A conclusão vem do conjunto.' }
  },
  'misterios-do-cosmos-limites': {
    ask: 'O que faz uma conclusão mudar?',
    guess: { q: 'Com mais medidas independentes, com erros semelhantes, a incerteza aleatória tende a…', options: ['diminuir', 'aumentar', 'não mudar'], right: 0, why: 'A média fica mais precisa. Erros de calibração não somem só com mais medidas.' },
    control: range('Número de medidas', 3, 40, 1, 3),
    alt: 'Pontos de medida e a reta que melhor passa por eles. Com mais pontos, a faixa de incerteza em volta da reta fica mais estreita.',
    limit: 'Dados sorteados. Erros sistemáticos (de calibração) não somem só com mais dados.',
    check: { q: 'Novos dados ajustarem um valor significa que…', options: ['a ciência se refinou', 'tudo estava errado', 'qualquer opinião vale igual'], right: 0, why: 'Refinar faz parte do método; não iguala todas as opiniões.' }
  },

  // ── D. A vida das estrelas ──
  'vida-das-estrelas-colapso': {
    ask: 'Como uma nuvem fria vira uma estrela?',
    guess: { q: 'A nuvem vira estrela porque…', options: ['a gravidade junta e aperta o gás', 'o gás pega fogo', 'um raio acende a nuvem'], right: 0, why: 'Ao ser apertado pela gravidade, o gás esquenta.' },
    control: stages('Avançar', 'Nuvem fria', 'Contraindo', 'Protoestrela e disco', 'Fusão começa'),
    alt: 'A nuvem encolhe e esquenta, forma um disco em volta de uma protoestrela e, quando o centro fica quente o bastante, a fusão começa.',
    limit: 'Leva centenas de milhares a milhões de anos; o desenho comprime tudo.',
    check: { q: 'Uma protoestrela brilha principalmente por…', options: ['fusão nuclear', 'calor da contração'], right: 1, why: 'A fusão estável só começa depois.' }
  },
  'vida-das-estrelas-fusao': {
    ask: 'De onde vem a energia do Sol?',
    guess: { q: 'O Sol brilha porque…', options: ['queima como fogueira', 'funde núcleos de hidrogênio em hélio', 'reflete luz de outras estrelas'], right: 1, why: 'Não há fogo: é fusão nuclear, sem oxigênio.' },
    control: stages('Avançar', '4 núcleos de hidrogênio', 'Viram 1 de hélio', 'Sobra energia', 'Equilíbrio'),
    alt: 'Quatro núcleos de hidrogênio se fundem em um de hélio, um pouco mais leve. A diferença vira energia, que empurra para fora e equilibra a gravidade.',
    limit: 'A reação real acontece em várias etapas; aqui ela aparece resumida.',
    check: { q: 'Se a fusão parasse, a gravidade…', options: ['comprimiria o núcleo', 'desapareceria', 'empurraria para fora'], right: 0, why: 'Sem a pressão da energia, a gravidade vence.' }
  },
  'vida-das-estrelas-sol': {
    ask: 'Como a energia do centro chega à superfície?',
    guess: { q: 'Onde o Sol é mais quente?', options: ['Na superfície', 'No núcleo'], right: 1, why: 'Núcleo: cerca de 15 milhões °C. Superfície: cerca de 5.500 °C.' },
    control: stages('Seguir a energia', 'Núcleo', 'Zona radiativa', 'Zona convectiva', 'Superfície'),
    alt: 'Corte do Sol: no núcleo nasce a energia; ela é rebatida muitas vezes na zona radiativa, sobe em bolhas na convectiva e sai pela superfície.',
    limit: 'Camadas e cores ilustrativas; a luz leva milhares de anos para sair do núcleo.',
    check: { q: 'A cor "amarela" do Sol nas figuras…', options: ['é atribuída; a luz do Sol é quase branca', 'mostra a temperatura do núcleo'], right: 0, why: 'Visto do espaço, o Sol é branco.' }
  },
  'vida-das-estrelas-pequenas-e-medias': {
    ask: 'Como termina uma estrela como o Sol? E uma bem menor?',
    guess: { q: 'Anã vermelha e anã branca são…', options: ['a mesma coisa', 'coisas diferentes: uma é estrela viva, a outra é o resto de uma estrela'], right: 1, why: 'A anã vermelha ainda funde hidrogênio; a anã branca é um núcleo que esfria.' },
    control: stages('Avançar no tempo', 'Hoje', '+5 bilhões de anos', '+7 bilhões de anos', '+8 bilhões de anos', 'Trilhões de anos'),
    alt: 'Lado a lado: o Sol vira gigante vermelha, solta suas camadas e deixa uma anã branca. A anã vermelha continua quase igual por trilhões de anos.',
    limit: 'Tamanhos fora de escala. O fim das anãs vermelhas é previsto por modelos; ainda não aconteceu.',
    check: { q: 'Já vimos uma anã vermelha morrer de velhice?', options: ['Sim, várias', 'Não: o Universo é jovem demais para isso'], right: 1, why: 'Elas vivem muito mais que a idade atual do Universo.' }
  },
  'vida-das-estrelas-massivas': {
    ask: 'Toda estrela gigante acaba em buraco negro?',
    guess: { q: 'Uma estrela massiva sempre…', options: ['vira buraco negro', 'vira estrela de nêutrons', 'pode ter mais de um destino'], right: 2, why: 'Massa, rotação, composição e companheiras mudam o fim.' },
    control: stages('Avançar', 'Sequência principal', 'Supergigante', 'Núcleo colapsa', 'Destinos possíveis'),
    alt: 'Uma estrela massiva incha, o núcleo de ferro colapsa e o caminho se divide: explosão com estrela de nêutrons, ou buraco negro, às vezes sem explosão brilhante.',
    limit: 'Os ramos são qualitativos; não há um corte exato de massa que decida o destino.',
    check: { q: 'Uma supernova brilhante é obrigatória no fim de uma estrela massiva?', options: ['Sim', 'Não: algumas podem colapsar quase sem explosão'], right: 1, why: 'Por isso o diagrama diz "pode".' }
  },
  'vida-das-estrelas-elementos': {
    ask: 'De onde veio o ferro do seu sangue?',
    guess: { q: 'Os elementos do seu corpo vieram…', options: ['de uma única supernova', 'de várias fontes: Big Bang, estrelas, explosões e colisões'], right: 1, why: 'Cada elemento tem suas fontes principais.' },
    control: choice('Elemento', 'Hidrogênio', 'Carbono', 'Oxigênio', 'Ferro', 'Ouro'),
    alt: 'Cada elemento escolhido acende suas fontes: hidrogênio vem do Big Bang; carbono e oxigênio, de estrelas; ferro, de explosões; ouro, de colisões e explosões raras.',
    limit: 'Fontes resumidas às principais; vários elementos têm mais de uma origem.',
    check: { q: 'O hidrogênio da água do seu corpo veio…', options: ['do Big Bang', 'de uma supernova', 'do núcleo da Terra'], right: 0, why: 'É o elemento mais antigo.' }
  },

  // ── E. O Sistema Solar ──
  'sistema-solar-disco': {
    ask: 'Por que os planetas rochosos ficam perto do Sol?',
    guess: { q: 'Perto do Sol jovem, o que conseguia ficar sólido?', options: ['Gelo e rocha', 'Só rocha e metal', 'Nada'], right: 1, why: 'Perto do Sol era quente demais para o gelo.' },
    control: stages('Avançar', 'Nuvem girando', 'Disco achatado', 'Grãos se juntam', 'Planetas'),
    alt: 'A nuvem gira e achata num disco. Perto do Sol só rocha e metal ficam sólidos; além da linha do gelo, o gelo ajuda planetas a crescerem grandes.',
    limit: 'Os planetas também migraram depois de formados; o desenho mostra só o começo.',
    check: { q: 'Por que os gigantes se formaram longe?', options: ['Lá havia gelo para crescer rápido e juntar gás', 'Lá era mais quente', 'Por acaso'], right: 0, why: 'Mais material sólido = núcleos maiores, que puxam gás.' }
  },
  'sistema-solar-sol-e-planetas': {
    ask: 'O planeta mais perto do Sol é o mais quente?',
    guess: { q: 'Qual é mais quente na superfície?', options: ['Mercúrio, o mais próximo', 'Vênus, mesmo mais distante'], right: 1, why: 'A atmosfera densa de Vênus prende o calor.' },
    control: choice('Planeta', 'Mercúrio', 'Vênus', 'Terra', 'Marte'),
    alt: 'Barras comparam luz do Sol recebida, atmosfera e temperatura média. Vênus recebe menos luz que Mercúrio, mas é mais quente.',
    limit: 'Barras qualitativas; temperaturas médias variam muito entre dia e noite.',
    check: { q: 'O que mais explica a diferença Vênus × Mercúrio?', options: ['A atmosfera', 'O tamanho', 'A cor'], right: 0, why: 'Atmosfera grossa = efeito estufa forte.' }
  },
  'sistema-solar-gigantes': {
    ask: 'Dá para pousar em Júpiter?',
    guess: { q: 'Descendo em Júpiter, você encontra…', options: ['um chão de rocha logo abaixo das nuvens', 'gás cada vez mais denso, sem chão definido'], right: 1, why: 'O gás vai ficando mais denso e quente; não há superfície para pousar.' },
    control: range('Descer na atmosfera', 0, 1, 0.01, 0),
    alt: 'Uma descida em Júpiter: nuvens, o nível de referência de 1 bar, hidrogênio cada vez mais comprimido e, muito fundo, um núcleo.',
    limit: 'Profundidades esquemáticas; o interior de Júpiter ainda é estudado.',
    check: { q: 'A temperatura de Júpiter no catálogo é medida…', options: ['no chão', 'no nível de 1 bar da atmosfera'], right: 1, why: 'É um nível de pressão escolhido como referência.' }
  },
  'sistema-solar-pequenos-corpos': {
    ask: 'Para onde aponta a cauda de um cometa?',
    guess: { q: 'A cauda do cometa aponta…', options: ['sempre para trás do movimento', 'para longe do Sol'], right: 1, why: 'O vento e a luz do Sol empurram o gás e a poeira.' },
    control: range('Posição na órbita', 0, 1, 0.005, 0.1),
    alt: 'Um cometa percorre uma órbita alongada. Perto do Sol, surgem duas caudas: uma de gás, reta e apontando para longe do Sol, e uma de poeira, curva.',
    limit: 'Tamanho do cometa e das caudas exagerados.',
    check: { q: 'Indo embora do Sol, a cauda do cometa fica…', options: ['na frente dele', 'atrás dele'], right: 0, why: 'Ela continua apontando para longe do Sol.' }
  },
  'sistema-solar-orbitas': {
    ask: 'Por que um planeta não cai no Sol?',
    guess: { q: 'Um planeta não cai no Sol porque…', options: ['um empurrão contínuo o leva para frente', 'ele se move de lado rápido o bastante: cai e erra o Sol o tempo todo', 'não existe gravidade no espaço'], right: 1, why: 'Órbita é queda contínua com velocidade lateral.' },
    control: range('Velocidade lateral do lançamento', 0, 1.6, 0.01, 0.5),
    alt: 'Um corpo lançado de lado: devagar, cai no Sol; com a velocidade certa, dá voltas; rápido demais, escapa. A seta da gravidade sempre aponta para o Sol.',
    limit: 'Sem atrito e só com o Sol puxando. Escala e velocidades ilustrativas.',
    check: { q: 'Se a Terra parasse de se mover de lado, ela…', options: ['cairia em direção ao Sol', 'ficaria parada no lugar', 'sairia voando'], right: 0, why: 'Sem velocidade lateral, só sobra a queda.' }
  },
  'sistema-solar-medindo-mundos': {
    ask: 'Planeta maior tem gravidade maior?',
    guess: { q: 'Saturno tem 95 vezes a massa da Terra. A gravidade lá é…', options: ['95 vezes maior', 'parecida com a da Terra'], right: 1, why: 'A massa está espalhada num raio enorme: o que conta é massa e distância ao centro.' },
    control: choice('Comparar por', 'Raio', 'Massa', 'Densidade', 'Gravidade'),
    alt: 'Barras para Terra, Júpiter e Saturno. Júpiter é 11 vezes maior em raio; Saturno é menos denso que a água; a gravidade de Saturno é parecida com a da Terra.',
    limit: 'Gigantes medidos no nível de 1 bar; barras em escala linear, uma propriedade por vez.',
    check: { q: 'Tamanho e gravidade…', options: ['são a mesma coisa', 'são diferentes: dependem de massa e raio juntos'], right: 1, why: 'Por isso o comparador usa a mesma definição para todos.' }
  },

  // ── F. Terra e atmosfera ──
  'terra-e-atmosfera-formacao-da-terra': {
    ask: 'Por que a Terra tem um núcleo de ferro?',
    guess: { q: 'Com a Terra jovem quente e mole, o ferro…', options: ['subiu para a superfície', 'afundou para o centro', 'ficou espalhado'], right: 1, why: 'Ferro é denso: afunda, como pedra na água.' },
    control: stages('Avançar', 'Mistura quente', 'Ferro afunda', 'Camadas', 'Hoje'),
    alt: 'Gotas de ferro afundam na Terra jovem e formam o núcleo; materiais mais leves sobem e formam manto e crosta.',
    limit: 'O manto de hoje é quase todo sólido, embora flua bem devagar.',
    check: { q: 'O manto da Terra hoje é…', options: ['um oceano de lava', 'quase todo sólido, fluindo muito devagar'], right: 1, why: 'A lava dos vulcões vem de regiões parciais derretidas.' }
  },
  'terra-e-atmosfera-atmosfera-primitiva': {
    ask: 'O oxigênio sempre esteve no ar?',
    guess: { q: 'Quando micróbios começaram a soltar oxigênio, o ar…', options: ['ficou logo como hoje', 'demorou muito: rochas e oceanos absorveram primeiro'], right: 1, why: 'O ferro dissolvido nos oceanos consumiu o oxigênio por muito tempo.' },
    control: range('Tempo (bilhões de anos atrás)', 0, 1, 0.01, 0),
    alt: 'Linha do tempo: o oxigênio produzido primeiro enche "reservatórios" no oceano e nas rochas; só depois começa a acumular no ar.',
    limit: 'Curva qualitativa: as quantidades e datas exatas ainda são estudadas.',
    check: { q: 'O ar primitivo era…', options: ['igual ao de hoje', 'muito diferente, quase sem oxigênio livre'], right: 1, why: 'Respirar ali seria impossível para nós.' }
  },
  'terra-e-atmosfera-ar-atual': {
    ask: 'Pouca quantidade quer dizer pouca importância?',
    guess: { q: 'O gás carbônico é cerca de 4 em cada 10 mil partes do ar. Para o calor da Terra ele é…', options: ['irrelevante', 'importante: segura parte do calor'], right: 1, why: 'Ele absorve a radiação de calor que nitrogênio e oxigênio deixam passar.' },
    control: choice('Ver', 'Composição', 'Calor saindo'),
    alt: 'Cem partes de ar seco: 78 de nitrogênio, 21 de oxigênio e 1 de argônio; o gás carbônico é uma fração minúscula. Mas o calor que sai do chão é absorvido por ele e pelo vapor d’água.',
    limit: 'Vapor d’água varia muito e foi deixado fora das 100 partes de ar seco.',
    check: { q: 'Nitrogênio é o gás mais abundante. Ele segura muito calor?', options: ['Sim', 'Não, quase nada'], right: 1, why: 'Abundância e efeito estufa são coisas diferentes.' }
  },
  'terra-e-atmosfera-camadas': {
    ask: 'Subindo no céu, a temperatura só cai?',
    guess: { q: 'Subindo sem parar, a temperatura…', options: ['só cai', 'cai, sobe, cai e sobe de novo'], right: 1, why: 'Cada camada esquenta por um motivo diferente: o ozônio, por exemplo, absorve luz do Sol.' },
    control: range('Altitude (km)', 0, 120, 1, 8),
    alt: 'Perfil de temperatura com a altitude: cai na troposfera, sobe na estratosfera (ozônio), cai na mesosfera e sobe na termosfera. Nuvens embaixo, meteoros e auroras no alto.',
    limit: 'Perfil médio aproximado; as fronteiras variam com latitude e estação.',
    check: { q: 'Chuva e nuvens acontecem quase todas…', options: ['na troposfera', 'na estratosfera', 'na termosfera'], right: 0, why: 'É a camada de baixo, com quase todo o vapor d’água.' }
  },
  'terra-e-atmosfera-campo-magnetico': {
    ask: 'O campo magnético é a atmosfera?',
    guess: { q: 'O campo magnético da Terra…', options: ['é a mesma coisa que a atmosfera', 'é outra coisa: desvia partículas do Sol'], right: 1, why: 'Ele nasce do ferro líquido em movimento no núcleo externo.' },
    control: choice('Cenário', 'Com campo', 'Sem campo'),
    alt: 'Partículas do vento solar chegam à Terra. Com campo magnético, são desviadas e algumas descem nos polos (auroras). Sem campo, atingem a atmosfera direto.',
    limit: 'Linhas de campo simplificadas; perder atmosfera depende também de gravidade e temperatura.',
    check: { q: 'Ter campo magnético garante vida?', options: ['Sim', 'Não: ajuda, mas não basta'], right: 1, why: 'Muitos fatores juntos tornam um planeta habitável.' }
  },
  'terra-e-atmosfera-habitabilidade': {
    ask: 'Água líquida basta para ter vida?',
    guess: { q: 'Um planeta na "zona habitável" tem…', options: ['vida, com certeza', 'condições que podem permitir água líquida; vida não é garantida'], right: 1, why: 'Zona habitável fala de temperatura possível, não de vida.' },
    control: choice('Planeta', 'Vênus', 'Terra', 'Marte', 'Terra sem efeito estufa (hipotética)'),
    alt: 'Barras de pressão do ar e temperatura média de Vênus, Terra e Marte, e de uma Terra hipotética sem efeito estufa, que congelaria.',
    limit: 'O último cenário é hipotético e rotulado como tal.',
    check: { q: 'Encontrar água num planeta prova que há vida?', options: ['Sim', 'Não'], right: 1, why: 'Água é condição importante, não prova.' }
  }
};
