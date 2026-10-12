# Cosmos do Zero — implementação de 11/10/2026

## Objetivo e decisões aprovadas

Ensinar ideias centrais de cosmologia a pessoas a partir de aproximadamente 14 anos, sem exigir conhecimento prévio. O portal permanece estático em Astro, com conteúdo em português e a identidade marinho, creme e cobre. Contas e sincronização entre dispositivos ficam para uma eventual etapa de backend.

Trilha principal:

1. **Onde estamos no Universo?** Terra, Sistema Solar, Via Láctea, outras galáxias, teia cósmica e tempo de viagem da luz.
2. **Como o Universo evoluiu?** Fase quente, evolução e expansão homogênea; troca de observador sem um centro privilegiado.
3. **Como sabemos disso?** Expansão, CMB, matéria escura e aceleração; observação, interpretação e limites separados.

Capítulos de estrelas, Sistema Solar e Terra foram preservados como complementares, com URLs anteriores. Há 15 perguntas: nove principais e seis complementares; 26 termos no glossário e dez marcos na linha do tempo.

## Alteração visual solicitada

Dez imagens raster foram produzidas com `image_gen` e incluídas em `public/renders`. Eclipse, capas sem fotografia, cartões, escalas, evidências, linha do tempo e estrela passam a usar esses arquivos. As imagens têm versões WEBP de 1200×800 e 600×400; a pequena galáxia da malha é PNG transparente. Os prompts completos e os arquivos originais estão registrados em `render-assets.json`.

Não há execução de gráficos 3D no navegador. As relações didáticas usam HTML e SVG 2D. A expansão mantém a geometria relativa ao observador escolhido, a onda e os controles. O movimento depende de uma ação do visitante, para quando a aba fica oculta ou a cena sai da tela e oferece estados estáticos para movimento reduzido.

Todas as imagens geradas são conceituais. A Via Láctea vista por fora é uma interpretação artística; o halo azul é uma convenção de distribuição inferida; a luz antiga não é um mapa CMB. Imagens da linha do tempo ilustram temas e não reconstroem a aparência de cada época. Fotos e composições observacionais oficiais permanecem com créditos próprios.

## Progresso e servidor

A chave anterior `cosmos-v3-progress` foi preservada. O progresso principal conta apenas as três jornadas centrais. Uma falha ao gravar mantém a mudança em memória e avisa que ela vale para a sessão; leituras antigas não apagam essa mudança. Desmarcação e reinício continuam disponíveis.

O servidor local valida caminhos, URLs inválidas, métodos e MIME; atende GET/HEAD e escuta somente 127.0.0.1. O requisito de Node foi corrigido para ≥22.12. Vitest e Sharp foram atualizados e a auditoria de dependências passou sem vulnerabilidades conhecidas na execução registrada.

## Publicação preparada, pendente

Destino aprovado: projeto Vercel `cosmos-do-zero`, Node 24, saída `dist`. Projeto criado e ligado ao checkout isolado. A tentativa de prévia foi recusada pelo limite diário de 100 deploys da conta, código `api-deployments-free-per-day`, com indicação de tentar novamente em 24 horas. Não houve implantação concluída nem publicação em produção.

Próxima sequência: serviço aceitar uma prévia → conferir URL e funcionamento publicados → Dener revisar a versão concreta → publicar em produção após aprovação. Não foi alterado o plano da conta, proteção de acesso, domínio ou DNS.

## Limites de validação

Os resultados executados estão em `VALIDACAO.md`. Firefox foi bloqueado ao iniciar pelo Windows, com erro SideBySide envolvendo `mozglue`; isso não demonstra falha da aplicação. Chrome e WebKit fornecem a evidência de navegação disponível. Não houve avaliação com cinco iniciantes nem teste em telefone físico. Os números de tamanho do build representam arquivos totais, não a transferência da primeira visita nem um benchmark de desempenho móvel.

## Origem e isolamento

A implementação foi consolidada num diretório de trabalho isolado a partir do pacote de projeto. Os pacotes originais foram preservados. Os caminhos pessoais do computador de desenvolvimento foram removidos desta cópia pública.

Workers conforme escolha de Dener: frontend GPT 6.1 Sol High; conteúdo e lógica GPT 6 Luna Max. Escopos de escrita separados e nenhuma ação externa por workers.
