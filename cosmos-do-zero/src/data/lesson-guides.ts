export interface LessonGuide { observe: string; connect: string; try: string }

/** Mediação visual de cada passo. As legendas dinâmicas continuam vindo da própria cena. */
export const LESSON_GUIDES: Record<string, LessonGuide> = {
  'galaxias-e-nebulosas-via-lactea': {
    observe: 'A cada afastamento, o lugar que parecia enorme vira um ponto dentro do próximo.',
    connect: 'A Terra pertence ao Sistema Solar, que pertence à Via Láctea. Galáxias também se agrupam.',
    try: 'Volte à Terra e avance até a teia. Em qual salto a Via Láctea vira um ponto?'
  },
  'galaxias-e-nebulosas-tipos': {
    observe: 'As camadas se somam: estrelas, gás, poeira e um halo que representa massa invisível.',
    connect: 'Uma galáxia é um sistema mantido pela gravidade. Sua parte luminosa conta apenas parte da história.',
    try: 'Compare a espiral com a elíptica e procure os braços em cada uma.'
  },
  'galaxias-e-nebulosas-teia-cosmica': {
    observe: 'Pequenas concentrações crescem e desenham fios, cruzamentos e regiões mais vazias.',
    connect: 'A gravidade amplifica diferenças de densidade e organiza a matéria em uma rede cósmica.',
    try: 'Mova a barra até a metade. Procure onde os fios começam a se encontrar.'
  },
  'galaxias-e-nebulosas-nebulosas': {
    observe: 'A nuvem muda de aparência conforme emite, espalha ou bloqueia a luz das estrelas.',
    connect: 'A posição da fonte de luz e a interação com gás e poeira explicam aparências diferentes.',
    try: 'Selecione a nuvem escura e identifique de onde viria a luz que ela esconde.'
  },
  'galaxias-e-nebulosas-gas-e-estrelas': {
    observe: 'O pulso precisa percorrer a distância entre a fonte e quem observa.',
    connect: 'Olhar para longe também é olhar para o passado: a imagem chega depois de a luz viajar.',
    try: 'Compare Lua e Sol. Leia o tempo real ao lado da viagem acelerada da figura.'
  },
  'galaxias-e-nebulosas-centros-galacticos': {
    observe: 'O círculo do que pode ser visto acompanha cada observador escolhido.',
    connect: 'O horizonte observável depende de onde estamos e de quanto tempo a luz teve para viajar.',
    try: 'Troque de galáxia e procure regiões que entram ou saem do horizonte.'
  },
  'origem-do-universo-o-universo': {
    observe: 'As distâncias entre galáxias aumentam enquanto cada galáxia mantém seu tamanho.',
    connect: 'A expansão muda as grandes separações. Sistemas ligados pela gravidade não crescem junto.',
    try: 'Compare o tamanho de uma galáxia com a distância até sua vizinha.'
  },
  'origem-do-universo-expansao': {
    observe: 'A onda recebida fica mais comprida e as linhas do espectro acompanham a mudança.',
    connect: 'A expansão alonga o comprimento de onda durante a viagem: esse deslocamento é o redshift cosmológico.',
    try: 'Duplique a escala do espaço e compare as ondas emitida e recebida.'
  },
  'origem-do-universo-fase-quente': {
    observe: 'Primeiro aparecem núcleos leves; elétrons presos em átomos surgem muito depois.',
    connect: 'O resfriamento permite formar estruturas diferentes em épocas diferentes.',
    try: 'Compare três minutos com 380 mil anos. O que só existe na última etapa?'
  },
  'origem-do-universo-primeira-luz': {
    observe: 'A luz ziguezagueia no plasma, passa a viajar livre e depois tem sua onda esticada.',
    connect: 'A formação de átomos tornou o Universo transparente. Essa luz chega hoje como radiação de micro-ondas.',
    try: 'Pause na formação dos átomos e compare a trajetória da luz com a etapa quente.'
  },
  'origem-do-universo-primeiras-estruturas': {
    observe: 'Regiões um pouco mais densas concentram matéria e dão origem às primeiras estruturas.',
    connect: 'As galáxias nasceram do crescimento de pequenas diferenças de densidade ao longo do tempo.',
    try: 'Observe a mesma concentração antes e depois de a gravidade agir.'
  },
  'origem-do-universo-nossa-epoca': {
    observe: 'A linha do tempo distingue as épocas que investigamos das extrapolações para o começo.',
    connect: 'Reconstruímos a evolução a partir de pistas; algumas perguntas sobre o início permanecem abertas.',
    try: 'Compare o que a cena mostra como conhecido com a região marcada como pergunta.'
  },
  'misterios-do-cosmos-horizonte': {
    observe: 'A mesma investigação separa uma medida, sua interpretação e uma pergunta ainda aberta.',
    connect: 'Uma explicação científica conecta observações a um modelo que pode ser confrontado com novas medidas.',
    try: 'Troque as opções e identifique qual delas descreve uma medida direta.'
  },
  'misterios-do-cosmos-exoplanetas': {
    observe: 'As linhas escuras mudam de posição juntas, preservando o padrão que identifica sua origem.',
    connect: 'Comparar espectros permite medir deslocamentos da luz e investigar a expansão.',
    try: 'Procure uma linha específica nos dois espectros e acompanhe seu deslocamento.'
  },
  'misterios-do-cosmos-vida': {
    observe: 'As diferenças no mapa da luz antiga são pequenas; a escala de cores as torna visíveis.',
    connect: 'O padrão da CMB preserva informação sobre o Universo jovem e ajuda a testar modelos cosmológicos.',
    try: 'Compare as opções do mapa e veja como muda o padrão das manchas.'
  },
  'misterios-do-cosmos-materia-escura': {
    observe: 'Compare a velocidade prevista pela matéria visível com a curva que exige massa adicional.',
    connect: 'Movimentos e lentes gravitacionais revelam gravidade além da explicada pela matéria luminosa.',
    try: 'Acompanhe a borda da galáxia e compare as duas curvas na mesma distância.'
  },
  'misterios-do-cosmos-energia-escura': {
    observe: 'Os pontos sintéticos ficam acima da linha do modelo que freia.',
    connect: 'O modelo acelerado usado para gerar este exemplo prevê supernovas mais fracas para o mesmo redshift.',
    try: 'Alterne Modelo freando e Modelo acelerando e confira qual curva acompanha os pontos sintéticos.'
  },
  'misterios-do-cosmos-limites': {
    observe: 'Ao acrescentar pontos, acompanhe a largura da faixa que cerca a reta.',
    connect: 'Mais medidas independentes podem reduzir a incerteza aleatória, mas um erro comum de calibração permanece.',
    try: 'Compare a faixa com 3 e com 40 medidas.'
  },
  'vida-das-estrelas-colapso': {
    observe: 'A nuvem se concentra, seu centro aquece e uma protoestrela se forma.',
    connect: 'A gravidade transforma energia durante a contração; a fusão sustentada marca a fase estelar.',
    try: 'Pare antes da estrela formada. Procure o que já mudou no centro da nuvem.'
  },
  'vida-das-estrelas-fusao': {
    observe: 'Núcleos leves se combinam e parte da massa inicial se converte em energia.',
    connect: 'A fusão nuclear fornece energia ao interior das estrelas e sustenta seu brilho.',
    try: 'Acompanhe os núcleos e identifique o produto que permanece depois da reação.'
  },
  'vida-das-estrelas-sol': {
    observe: 'Siga o caminho da energia do núcleo à superfície.',
    connect: 'A fusão libera energia no núcleo. Na zona radiativa ela se difunde; na convectiva, o gás quente sobe.',
    try: 'Compare os traços da zona radiativa com o movimento do gás na convectiva.'
  },
  'vida-das-estrelas-pequenas-e-medias': {
    observe: 'As camadas externas se espalham e um remanescente compacto fica no centro.',
    connect: 'Estrelas como o Sol terminam como anãs brancas depois de perder suas camadas externas.',
    try: 'Encontre a anã branca e compare seu tamanho com a nuvem ao redor.'
  },
  'vida-das-estrelas-massivas': {
    observe: 'Depois do colapso do núcleo, o diagrama se divide em dois caminhos.',
    connect: 'Uma estrela massiva pode deixar uma estrela de nêutrons ou um buraco negro.',
    try: 'Selecione Destinos possíveis e identifique os dois remanescentes.'
  },
  'vida-das-estrelas-elementos': {
    observe: 'Elementos diferentes aparecem associados a processos e ambientes diferentes.',
    connect: 'A matéria do nosso corpo reúne produtos da evolução estelar e de outros eventos cósmicos.',
    try: 'Escolha um elemento e siga a origem indicada pela experiência.'
  },
  'sistema-solar-disco': {
    observe: 'O material em rotação se organiza num disco e concentra corpos ao redor do centro.',
    connect: 'O Sol e os planetas se formaram a partir de uma nuvem comum, preservando uma organização orbital.',
    try: 'Compare a nuvem inicial com o disco e procure o plano das órbitas.'
  },
  'sistema-solar-sol-e-planetas': {
    observe: 'Os quatro planetas internos compartilham superfícies rochosas, com aparências diferentes.',
    connect: 'Distância ao Sol, tamanho e história geológica ajudam a explicar a diversidade dos mundos rochosos.',
    try: 'Compare Terra e Vênus. Depois investigue outro planeta no modelo ampliado.'
  },
  'sistema-solar-gigantes': {
    observe: 'A seta atravessa as nuvens de Júpiter e alcança camadas cada vez mais densas.',
    connect: 'A pressão aumenta com a profundidade. O nível de 1 bar serve de referência para comparar condições.',
    try: 'Pare na linha de 1 bar e depois procure o hidrogênio metálico.'
  },
  'sistema-solar-pequenos-corpos': {
    observe: 'A cauda cresce ao se aproximar do Sol e aponta para longe dele.',
    connect: 'A luz e o vento solar afastam o material liberado pelo cometa.',
    try: 'Compare a direção da cauda na ida e na volta, perto do Sol.'
  },
  'sistema-solar-orbitas': {
    observe: 'A gravidade curva o movimento; a velocidade lateral impede a queda direta no Sol.',
    connect: 'Uma órbita é uma queda contínua em que o corpo segue passando ao lado do centro.',
    try: 'Mude a velocidade e compare o percurso com a órbita inicial.'
  },
  'sistema-solar-medindo-mundos': {
    observe: 'A ordem e a diferença entre as barras mudam com a grandeza escolhida.',
    connect: 'A gravidade na superfície depende da massa e do raio do planeta.',
    try: 'Compare Terra e Saturno em Massa e em Gravidade.'
  },
  'terra-e-atmosfera-formacao-da-terra': {
    observe: 'Materiais densos se concentram no interior enquanto os mais leves ficam nas camadas externas.',
    connect: 'O aquecimento e a diferenciação organizaram o interior da Terra em camadas.',
    try: 'Compare o começo e o fim e acompanhe a região que forma o núcleo.'
  },
  'terra-e-atmosfera-atmosfera-primitiva': {
    observe: 'A mistura de gases muda ao longo da história, especialmente com a produção de oxigênio.',
    connect: 'A atmosfera resulta da interação entre interior, superfície, oceanos e vida.',
    try: 'Compare o ar primitivo com o atual e procure quando o oxigênio ganha importância.'
  },
  'terra-e-atmosfera-ar-atual': {
    observe: 'Nitrogênio ocupa a maior parte da mistura; oxigênio vem em segundo lugar.',
    connect: 'A proporção de um gás e seu efeito físico são informações diferentes: gases raros também podem importar.',
    try: 'Identifique o gás mais abundante antes de conferir as porcentagens.'
  },
  'terra-e-atmosfera-camadas': {
    observe: 'A temperatura muda de tendência conforme subimos e atravessamos camadas do ar.',
    connect: 'As camadas atmosféricas são definidas por comportamento térmico; suas fronteiras variam.',
    try: 'Suba pela barra e compare a direção da curva de temperatura em cada camada.'
  },
  'terra-e-atmosfera-campo-magnetico': {
    observe: 'O campo ao redor da Terra modifica o percurso das partículas carregadas.',
    connect: 'O movimento do material condutor no interior sustenta o campo magnético terrestre.',
    try: 'Compare o percurso das partículas com e sem o campo representado.'
  },
  'terra-e-atmosfera-habitabilidade': {
    observe: 'Terra, Vênus e Marte respondem de maneira diferente à luz solar e à atmosfera.',
    connect: 'A habitabilidade envolve vários fatores combinados: temperatura, água, atmosfera e história planetária.',
    try: 'Compare os três planetas e procure quais fatores mudam ao mesmo tempo.'
  }
};
