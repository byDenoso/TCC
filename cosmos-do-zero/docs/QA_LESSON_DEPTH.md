# Cenas didáticas com assets locais

Verificação em Chromium no Windows, em 18/11/2026. O build de aceite ficou em uma pasta temporária fora do worktree. O navegador carregou o site por loopback. Cada camada Canvas usa o contexto 2D.

| Superfície | Imagem e interação | Evidência |
| --- | --- | --- |
| Resumos das seis aulas | Os seis MP4 e as legendas VTT acompanham o relógio da cena. Cinco resumos mantêm os quadros 3D por fase. No resumo da origem, galáxias renderizadas ficam sob a onda e a régua. | 343 verificações de cinema, com reprodução, busca, mudança de formato, pausa fora da tela e movimento reduzido. |
| Jornada da home | Doze marcos compartilham o estado de rolagem com o texto. Núcleos, gás, estrelas, galáxias, Terra e Lua são compostos em planos de profundidade. O seletor leva ao marco desejado e o botão pausa o movimento. | Seleção da Terra, imobilidade em movimento reduzido, pausa manual, retomada e suspensão fora da tela. |
| Céu e CMB | O mapa e a sonda usam o mesmo campo simulado. A projeção esférica coloca o ponto escolhido no centro do hemisfério. O mapa observado do Planck aparece ao lado, com crédito próprio. | Mudança do hemisfério por teclado, leitura do ponto simulado e imagem observacional local. |
| Recombinação | Prótons, elétrons e núcleos de hélio vêm de renders Cycles. O desenho sobrepõe órbitas projetadas, espalhamento, grade e régua aos estados do modelo original. | Avanço pelas três etapas. Valores da radiação e operação manual também verificados com Canvas indisponível. |
| Luz | O trajeto entre uma galáxia e a Terra acompanha o redshift. A régua de emissão e absorção fica separada, com as mesmas linhas e unidades. | A tecla End levou a linha Hα a 1.050,1 nm. |
| Endereço cósmico | Cinco vistas preservam os retratos, mapas galácticos, anotações e escalas originais. No percurso da luz, a estrela, a Terra e o pulso compartilham as posições do instrumento. | Cinco referências visuais, seleção da teia e chegada do pulso a x = 450. O teste visual alinha uma linha extra de captura do Chromium e mantém o limiar de diferença de 2/255. |
| Estrelas | O render da fotosfera recebe a cor e o raio do modelo de massa e etapa. A nuvem precede a fase estelar, e o remanescente de alta massa mantém as duas possibilidades do diagrama. | 0,3, 1 e 15 massas solares no percurso integrado, com leitura do desfecho. O diagrama e os controles continuam disponíveis sem Canvas. |
| Linha do tempo | Cada marco recompõe a cena por profundidade a partir da época escolhida. O render respeita as proporções da imagem em palcos estreitos. O pôster HTML atende o carregamento e a ausência de Canvas. | Seleção de época, sincronização do painel e decodificação dos pôsteres. |
| Buracos negros | A régua de S2 percorre 16 anos em passos de 0,1 ano. A anomalia excêntrica controla a posição na elipse ilustrativa. Um segundo controle percorre a fase do gás no disco; um terceiro acompanha a luz no esquema do horizonte. A quarta placa preserva a imagem em rádio do EHT. | Três controles por teclado, reprodução de S2 e pausa fora da tela. O diagrama de acreção é ilustrativo; a imagem observada ocupa uma placa identificada. |

## Procedência e reexecução

Os cinco renders originais estão em `public/renders/lesson-depth/`. O campo de estrelas vem do Reel Blender do projeto. O manifesto da pasta registra fonte, dimensão, bytes e SHA-256. O script de modelagem está em `assets/source/lesson-depth/bake.py`. O Reel, os retratos planetários, os filmes e as observações Webb, Planck e EHT usam os arquivos locais do projeto.

A suíte `tests/lesson-depth.mjs` acessa os controles do site, testa pixels efetivamente pintados, bloqueia HTTP externo e registra tentativas de abrir contextos GL. Use `BASE_URL` para selecionar o servidor, `WIDTH` para a largura e `SHOTS` para a pasta das provas. Os arquivos `test-results/lesson-depth/acceptance.json` e `test-results/lesson-depth/mobile/acceptance.json` acompanham as capturas dos dois tamanhos. A checagem com Canvas indisponível cobre recombinação, linha do tempo e evolução estelar.
