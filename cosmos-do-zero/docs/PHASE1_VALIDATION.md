# Fase 1: validação do renderer

Este registro reúne provas com a revisão identificada. O código de aplicação final está em `e8c0291cab7d5da17042b91301e3088116ef2b66`; a revisão de entrega seguinte acrescenta este registro e o ajuste do teste de navegadores. Resultados de uma revisão anterior estão assinalados, sem serem atribuídos ao novo pacote. A conclusão da bateria completa no HEAD deve ser consultada na PR, separadamente dos testes locais. Não houve merge nem publicação em produção.

## Pacote e condições

O build final gerou 11 páginas. O arquivo servido na prévia local correspondeu ao compilado `runtime.cDAv6-qG.js`, SHA-256 `324931018e22f3b6434db5e9202a6d6dbb72291c9ee701d5cf1aefd0ec81118b`. O helper fonte de normalização usado no build tem SHA-256 `2deca2d321d6db1aaef81806445f7042a965142e79f9cffdc57c5165b9d22c08`. Os testes gráficos e de seleção de backend foram repetidos nesse pacote. As fixtures de engenharia carregam os mesmos módulos fonte por Vite; são identificadas separadamente do pacote estático.

Os testes nativos usaram Chrome no Windows e uma GPU AMD RDNA 4 dedicada, com flags explícitas para WebGPU. Os testes de referência visual usaram WebGL2 por SwiftShader, qualidade Padrão, movimento reduzido, viewport 390 × 844 e DPR 1. Viewport emulado não equivale a dispositivo móvel físico. As cenas são ilustrações didáticas, sem novos resultados astronômicos.

## Resultados e revisões

| Verificação | Resultado |
|---|---|
| `npm run check` | Revisão final: 227 arquivos, zero erros, avisos ou sugestões |
| `npm test` | Revisão final: 199 testes em 23 arquivos, todos aprovados |
| Build | Revisão final: 11 páginas compiladas |
| `test:http` | Aprovado na CI de `883c4783`, anterior à correção de projeção; a PR registra a nova execução completa |
| `test:e2e` | 1.110 verificações, nenhuma falha na CI de `883c4783`; a PR registra a nova execução completa |
| `test:hero` | 9 verificações aprovadas, incluindo ativação explícita e alternativa visual |
| `test:renders` | 20 imagens raster decodificadas e cinco vistas aprovadas no Windows e na CI Linux de `883c4783` |
| `test:graphics` | 54 verificações de renderização, 26 de visibilidade e 34 de dinâmica aprovadas |
| `test:browsers` | Teste corrigido: WebKit 28/28 nas bases raiz e Pages, com compilações identificadas no diagnóstico. Firefox não iniciou neste Windows (`spawn UNKNOWN`); confirmação do HEAD atual é feita na CI |
| `test:webgpu` | WebGPU observado na fase quente e nas órbitas; Sol em WebGL2; ausência, rejeição, perda injetada e falha de importação com alternativas verificadas |
| `test:gpu-quarantine` | Oito cenários aprovados na GPU local, incluindo validação injetada antes e depois da montagem e descarte pendente/rejeitado |
| `test:world-frame` | Fonte final: azul real, revelar/restaurar planos, material original mutável, origem flutuante, órbita e zoom aprovados em SwiftShader e AMD; quadro de transição e estabilidade após arraste verificados |
| `test:quality-calibration` | Dez cenários aprovados; três perfis, cancelamentos e encerramento da medição. Intervalos injetados testam decisões; um cenário usa RAF original |
| `test:cinematic-effects` | Focal anterior no pipeline fonte inalterado: bloom, foco, profundidade de campo, SMAA e desfoque de câmera comparados em perspectiva e ortográfica; valor linear HDR máximo 4 |

## Orçamento da primeira visita

Em 1440 × 900 e 390 × 844, a home carregou **172.877 bytes gzip** de HTML, CSS e JavaScript da mesma origem até 1,5 s após `load`, abaixo do limite de 300.000 bytes. O teste comprime os corpos de resposta reais com gzip nível 6. Trata-se de uma soma conservadora dos recursos desse intervalo, sem atribuir cada arquivo ao caminho crítico; não é transferência medida na rede e não inclui imagens nem fontes. O 3D da nebulosa é ativado pelo visitante.

## Referências visuais

As cinco referências em `tests/baselines/scale/` foram geradas explicitamente e inspecionadas. A captura repetida no Windows teve erro médio zero; o menor erro entre escalas distintas foi 5,96 em 255, acima do limite de comparação de 2. Quadros pretos também são rejeitados. Na CI Linux `41971866838`, os erros das cinco vistas ficaram entre 0,0004 e 0,263, também aprovados. Atualização de referências é proibida quando `CI` está definido; falhas guardam a captura e uma imagem da diferença. A PR registra a repetição na revisão final.

Essa cobertura corresponde às cinco vistas atuais — Terra, Sistema Solar, Via Láctea, Grupo Local e teia cósmica. A viagem contínua da Fase 3 não está incluída.

## Isolamento do teste de pausa

A primeira execução Linux (`41970576888`) falhou ao comparar os pixels de Tempo em desktop. Na reprodução com SwiftShader e CPU limitada em 4×/8×, o botão permaneceu pausado e o canvas manteve 661 × 413, mas a calibração automática trocou a textura de 1536 para 512. As transformações dos 13 objetos e as oito matrizes registradas permaneceram iguais. A captura mudou durante a troca de qualidade e depois estabilizou.

O teste de pausa passou a selecionar Padrão e aguardar o perfil manual e a textura correspondente antes de comparar. A igualdade exata de pixels continua exigida; não foi acrescentada tolerância nem alterado o runtime. O focal com CPU limitada em 4× passou em pausa, retomada e alternativa após perda de contexto. A seleção Automática permanece na suíte específica de dez cenários, sem ser desativada na aplicação. Em Automática, a calibração inicial ainda pode trocar resolução ou textura após o visitante pausar o movimento; a prova de igualdade exata em Padrão não demonstra pixels imutáveis nesse modo.

## Captura da cena e controle da retomada

A execução `41977345415` aprovou a prova de projeção reforçada no Linux, mas voltou a divergir na pausa de Tempo em 390 px. Essa execução não guardava A/B e estado; sua causa específica não foi diretamente observada. Um controle local prolongou somente a transição visual do botão: 4.337 pixels mudaram no retângulo sobreposto, mantendo quadros, objetos e matrizes. Isso comprova um mecanismo possível de interferência da interface, sem atribuí-lo como causa certa da falha remota.

O screenshot do elemento canvas também capturava botões e rótulos desenhados acima dele. Agora a captura da cena oculta essas sobreposições somente durante a operação e desativa animações CSS transitórias; o site não recebe essa alteração. Controles continuam visíveis e interativos fora das capturas, com estado, rótulo e visibilidade verificados separadamente. A animação 3D por JavaScript permanece ativa quando solicitada.

A pausa exige pixels decodificados exatamente iguais. A retomada compara dois quadros em execução com o mesmo estado do botão, exige dimensões/canais iguais e pixels diferentes. Uma contraprova que alterou apenas a interface para “Pausar”, mantendo a cena parada, foi rejeitada com zero pixels 3D alterados. Não foi acrescentada tolerância. Divergências guardam A/B, diferença amplificada e JSON com quatro leituras de estado, incluindo posição, dimensões, texturas, animações, matrizes e a política de captura. O workflow preserva PNG/JSON nos diretórios específicos de diagnóstico.

## Projeção extrema e integridade da prova

O predicado inicial para o plano azul aceitava o fundo `[7, 12, 24]` no SwiftShader. Esse resultado não comprovava visibilidade ou oclusão distante. A verificação foi substituída por azul intenso distinto do fundo, revelar o plano distante ao ocultar o próximo e restaurar a oclusão ao reexibi-lo. A geometria e a distância de 10²⁷ m foram preservadas.

O caminho WebGL2 de `worldFrame` agora normaliza uniformemente as coordenadas homogêneas após preservar o valor de profundidade logarítmica. Essa operação mantém NDC e a geometria; o caminho WebGPU não recebe a alteração. SwiftShader e AMD passaram na cena extrema, com continuidade após rebase e mudança de cor pela instância original do material. A contraprova com fator 1 voltou a perder o plano e falhou como esperado. Isso não demonstra suporte a coordenadas arbitrárias fora do intervalo validado.

O contrato físico aceita perspectiva. `worldFrame` ortográfico usa a alternativa 2D nos dois backends; a fixture ortográfica normalizada sem `worldFrame` continuou funcionando em ambos. No caminho WebGL2 normalizado, shaders customizados, callbacks sem contrato e sombras usam fallback explícito. Os materiais pertencem ao cenário; as referências e os descritores dos callbacks são preservados e restaurados no descarte, sem suporte prometido a compartilhamento externo concorrente.

## Navegação nas duas bases

Na CI `41971866838`, E2E e capturas passaram, mas os dois engines pararam na entrada: o preview do Pages responde 404 em `/TCC/cosmos-do-zero` e 200 em `/TCC/cosmos-do-zero/`. O teste passou a usar a URL canônica com barra e verificar o HTTP antes do conteúdo. A volta à home pode responder 304 por revalidação com ETag, observada no WebKit; os testes de conteúdo e progresso continuam exigidos.

O WebKit podia considerar a cena visível mesmo com o disclosure recolhido. Agora o teste aguarda o seletor gerado pelo leitor, abre o controle nativo e só então aguarda a cena. Os 26 testes originais e dois de HTTP passaram nas duas bases, sem forçar cliques. As compilações usadas nesse diagnóstico eram anteriores ao pacote final; a CI da PR verifica o código reunido.

Capturas da interface de `6caf1e65`, anterior à correção interna de projeção: [Home desktop com ativação](screenshots/renderer-phase1/home-ativada-1440.png) · [Home em celular emulado](screenshots/renderer-phase1/home-ativada-390.png) · [Palco WebGPU desktop](screenshots/renderer-phase1/fase-quente-desktop-final.png) · [Cinemática em celular emulado](screenshots/renderer-phase1/fase-quente-cinematica-390-final.png).

## Limites preservados

- O runtime compartilha um contexto entre seus palcos. Após ativar a nebulosa e abrir o Observatório, a instrumentação registrou três contextos WebGL ativos: abertura, CMB e palco. Não há comprovação de um contexto único em toda a página.
- A fixture verifica deslocamentos locais de 1 m junto a uma âncora sintética de 10²⁷ m. Não demonstra resolução angular universal nem a viagem física entre escalas. A exposição possui controles fotográficos, com ganho artístico separado; as luminâncias dos materiais não foram calibradas fisicamente.
- Os materiais GLSL legados continuam em WebGL2. Os efeitos completos dependem do perfil Cinemática e de um backend WebGPU compatível.
- No CI com adaptador ausente ou identificado como fallback, sete cenários de quarentena, quatro de calibração e o ramo Cinemática da origem flutuante podem ficar sem execução. Os efeitos isolados não são chamados pelo workflow. As provas nativas locais não são substituídas por essas execuções de software.
- Perda física de dispositivo, falha espontânea de driver, rejeições internas fora de `onError`, 60 fps sustentados em GPU integrada e 30 fps em celular de entrada permanecem não verificados.

O comportamento e os comandos de reprodução estão descritos em [RENDERER_FASE_1.md](RENDERER_FASE_1.md).
