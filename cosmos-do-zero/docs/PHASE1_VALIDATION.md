# Fase 1: validação do renderer

Este registro descreve os testes locais do código de aplicação no commit `6caf1e65a166f957690e62a8e187c4dab876004e`. A revisão seguinte acrescenta somente este registro e capturas; não altera o pacote de aplicação medido. A conclusão do CI Linux deve ser consultada na PR, separadamente destes resultados locais. Não houve merge nem publicação em produção.

## Pacote e condições

O build estático gerou 11 páginas. O arquivo servido na prévia local correspondeu ao arquivo compilado `runtime.CH2fyeAv.js`, com SHA-256 `4ba0511781ee244cd52a2e7101495fa6264c0824e737c22bd0633ff808af478d`. Os testes E2E e gráficos usaram esse mesmo pacote; a inclusão posterior de referências visuais e documentação não muda o runtime.

Os testes nativos usaram Chrome no Windows e uma GPU AMD RDNA 4 dedicada, com flags explícitas para WebGPU. Os testes de referência visual usaram WebGL2 por SwiftShader, qualidade Padrão, movimento reduzido, viewport 390 × 844 e DPR 1. Viewport emulado não equivale a dispositivo móvel físico. As cenas são ilustrações didáticas, sem novos resultados astronômicos.

## Resultados locais

| Verificação | Resultado |
|---|---|
| `npm run check` | 224 arquivos, zero erros, avisos ou sugestões |
| `npm test` | 196 testes em 22 arquivos, todos aprovados |
| Build e `test:http` | Aprovados; 11 páginas compiladas |
| `test:e2e` | 1.110 verificações, nenhuma falha |
| `test:hero` | 9 verificações aprovadas, incluindo ativação explícita e alternativa visual |
| `test:renders` | 20 imagens raster carregadas e decodificadas; comparação das cinco vistas atuais aprovada |
| `test:graphics` | 54 verificações de renderização, 26 de visibilidade e 34 de dinâmica aprovadas |
| `test:browsers` | WebKit: 26 verificações aprovadas. Firefox não iniciou neste Windows (`spawn UNKNOWN`); a execução conjunta local ficou incompleta |
| `test:webgpu` | WebGPU observado na fase quente e nas órbitas; Sol em WebGL2; ausência, rejeição, perda injetada e falha de importação com alternativas verificadas |
| `test:gpu-quarantine` | Oito cenários aprovados na GPU local, incluindo validação injetada antes e depois da montagem e descarte pendente/rejeitado |
| `test:world-frame` | Rasterização, profundidade, origem flutuante, órbita e zoom aprovados em WebGL2 e WebGPU; quadro de transição e estabilidade após arraste verificados |
| `test:quality-calibration` | Dez cenários aprovados; três perfis, cancelamentos e encerramento da medição. Intervalos injetados testam decisões; um cenário usa RAF original |
| `test:cinematic-effects` | Bloom, foco, profundidade de campo, SMAA e desfoque de câmera comparados em perspectiva e ortográfica; valor linear HDR máximo 4 antes do tone mapping |

## Orçamento da primeira visita

Em 1440 × 900 e 390 × 844, a home carregou **172.877 bytes gzip** de HTML, CSS e JavaScript da mesma origem até 1,5 s após `load`, abaixo do limite de 300.000 bytes. O teste comprime os corpos de resposta reais com gzip nível 6. Trata-se de uma soma conservadora dos recursos desse intervalo, sem atribuir cada arquivo ao caminho crítico; não é transferência medida na rede e não inclui imagens nem fontes. O 3D da nebulosa é ativado pelo visitante.

## Referências visuais

As cinco referências em `tests/baselines/scale/` foram geradas explicitamente e inspecionadas. A captura repetida teve erro médio zero; o menor erro entre escalas distintas foi 5,96 em 255, acima do limite de comparação de 2. Quadros pretos também são rejeitados. Atualização de referências é proibida quando `CI` está definido; falhas guardam a captura e uma imagem da diferença. A estabilidade no Linux depende do CI da PR.

Essa cobertura corresponde às cinco vistas atuais — Terra, Sistema Solar, Via Láctea, Grupo Local e teia cósmica. A viagem contínua da Fase 3 não está incluída.

[Home desktop com ativação](screenshots/renderer-phase1/home-ativada-1440.png) · [Home em celular emulado](screenshots/renderer-phase1/home-ativada-390.png) · [Palco WebGPU desktop](screenshots/renderer-phase1/fase-quente-desktop-final.png) · [Cinemática em celular emulado](screenshots/renderer-phase1/fase-quente-cinematica-390-final.png).

## Limites preservados

- O runtime compartilha um contexto entre seus palcos. Após ativar a nebulosa e abrir o Observatório, a instrumentação registrou três contextos WebGL ativos: abertura, CMB e palco. Não há comprovação de um contexto único em toda a página.
- A fixture verifica deslocamentos locais de 1 m junto a uma âncora sintética de 10²⁷ m. Não demonstra resolução angular universal nem a viagem física entre escalas. A exposição possui controles fotográficos, com ganho artístico separado; as luminâncias dos materiais não foram calibradas fisicamente.
- Os materiais GLSL legados continuam em WebGL2. Os efeitos completos dependem do perfil Cinemática e de um backend WebGPU compatível.
- No CI com adaptador ausente ou identificado como fallback, sete cenários de quarentena, quatro de calibração e o ramo Cinemática da origem flutuante podem ficar sem execução. Os efeitos isolados não são chamados pelo workflow. As provas nativas locais não são substituídas por essas execuções de software.
- Perda física de dispositivo, falha espontânea de driver, rejeições internas fora de `onError`, 60 fps sustentados em GPU integrada e 30 fps em celular de entrada permanecem não verificados.

O comportamento e os comandos de reprodução estão descritos em [RENDERER_FASE_1.md](RENDERER_FASE_1.md).
