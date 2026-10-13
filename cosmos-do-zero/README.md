# Cosmos do Zero

Escola estática de cosmologia em português: três jornadas principais e três aulas complementares, Laboratório, Dicionário, Fontes e404. Astro 7, TypeScript eThree.js. Conteúdo e cálculos executam no navegador; não há banco de dados ou serviço pago. Mapas, fontes e modelos são arquivos do próprio site.

## Executar

Node >= 22.12; implementação/QA em Node 24.19.0. Instale com `npm ci`, execute `npm run dev` ou gere `npm run build`. A saída estática é `dist/`; `npm run serve` oferece o servidor local. Para homologação privada use `SITE_PUBLIC=false`, `SITE_BASE=/` e a URL privada em `SITE_URL`.

Links, modelos e posters passam por `u()` para funcionar na raiz e em `/TCC/cosmos-do-zero/`. Os dois destinos foram validados somente em builds locais; essa revisão não publicou produção nem alterou o domínio.

## Experiências

As 36 subseções preservam IDs, âncoras, quizzes e retomada:20 palcos 3D com alternativaSVG,15 microexperiências 2D e1 CmbJourney 2D. Gráficos de composição, Hubble, espectros, rotação, supernovas, ajuste e atmosfera permanecem2D onde favorecem a comparação.

Um runtime compartilhado controla montagem, estado, pausa, câmera, resize, qualidade e descarte. Só um contexto WebGL fica ativo por documento. Assets são carregados perto do palco/na seleção. Ao sair da tela, o desenho para; controles abertos ou focados continuam utilizáveis. Perda de contexto, falha de asset ou falta de WebGL mantém a experiência funcional em 2D/poster. A câmera requer ação explícita; toque comum preserva a rolagem. Botões/teclado permitem girar, aproximar e restaurar visão.

Qualidade ajustada à largura/DPR: mapas galácticos 1536 no desktop e 768 no mobile; modo Econômico 512. Os mundos selecionados usam mapas até 2048/1024/512 e restauram a fonte original após trocas. A preferência por palco é preservada ao remontar. Essas resoluções não são uma promessa de FPS em qualquer dispositivo.

## Materiais e proveniência

Terra: composição MODIS/Blue Marble de julho2004. Lua: mosaico LROC 2025, com tratamento de cor declarado pela fonte, e relevo LOLA. Júpiter: Hubble/OPAL 2015. Marte: mosaico Viking/USGS. Mercúrio: MESSENGER em cores realçadas. Mapas de Saturno/Netuno da coleção NASA são ilustrativos; Vênus/Urano usam authoring original de nuvens. Geometria, iluminação, espessura de atmosfera, anéis e relevos visuais são aproximações explícitas.

As seis morfologias galácticas são assets originais com emissão/poeira/estrelas sintetizadas; não correspondem a mapas observacionais de galáxias específicas. A nebulosa combina densidade original e detalhe Hubble/Orion creditado; a profundidade e as cores são artísticas. Estrelas usam granulação original. BH ilustra horizonte/disco, sem calcular sombra ou ray tracing relativístico. Lente calcula imagem 2D pelo modelo de lente fina, com geometria 3D coerente e limites declarados.

Posters atuais derivam das cenas/mapas creditados: plasma/núcleos sem estrelas e mapaCMB sintético identificado. Imagens oficiais da escola mantêm seus créditos. Recursos antigos e versões reprovadas permanecem como histórico de autoria no código-fonte; o pós-build exclui mapas antigos ePNGeditáveis do artefato servido.

Fontes/creditos aparecem junto às experiências e em `/fontes/`. Manifests: `assets/source/manifest.json`, `assets/source/solar-materials/manifest.json`, `public/models/galaxies-v4/manifest.json`, `public/models/stellar/manifest.json`, `public/posters/manifest.json`. Não há licença CC0 genérica para recursos NASA/terceiros.

## Fonte editável e reprodução

`assets/source/mundos.blend` contém o authoring solar. `assets/source/build_worlds.py` reproduz o GLB e os portraits com Blender 4.5.9 LTS. Os scripts `prepare_solar_materials.py`, `build_galaxies_v4.py`, `build_stellar_materials.py` e `build_posters.py` documentam os processamentos; originais/PNG/.npy ficam junto às fontes. Consulte as dependências no cabeçalho de cada script. Nenhum poster estático substitui a câmera interativa.

## Verificação

`npm run check`, `npm test`, `npm run test:http`, `npm run test:e2e`, `npm run test:renders`, `npm run test:graphics`, `npm run test:browsers`. `test:pages` valida a saída local com variáveis dos dois destinos autorizados; não envia arquivos para eles.

Testes dedicados incluem60/120 Hz da expansão, navegação/progresso/storage bloqueado, BFCache real, perda de contexto/falha de asset, pausa exata, seleção rápida, remount de qualidade,20 trocas e medição de memória. Registros e capturas estão no pacote de homologação; resultados históricos de outras revisões não são resultados desta execução.

Ilustrações e pontos gerados são TOY_MODEL. Testes numéricos verificam implementação e aproximações; não confirmam modelos contra dados.390/360 são emulação de viewport, sem teste em celular físico. Bytes de texturas/buffers submetidos não são VRAM física. A máquina é compartilhada e sua atividade comum não foi controlada.

## Persistência e reversão

Preservados `cosmos-v3-progress`, `cosmos-v5-selos`, `cosmos-v6-praticado`, `cosmos-v6-onde`, `cosmos-quiz:${pathname}:${chapter}` e `cosmos-quiz-review`. Reiniciar experimento/restaurar câmera não apaga conquistas. A origem privada mantém progresso separado da produção; QA usa fixtures artificiais.

Base de reversão: commit67a467f242fae92a638ec01884ef8ee6c81c3dcf da branch cosmos-do-zero. Homologação ocorre em branch/ambiente separados; nenhuma reversão exige apagar dados do aluno. Para reverter a prévia, publique uma versão privada previamente registrada ou reconstrua essa base em outro checkout. A produção exige autorização futura específica do Dener.
