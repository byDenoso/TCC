# Renderer: migração parcial de fase 1

Three.js foi atualizado para r187. O runtime tenta WebGPU quando o navegador oferece um adaptador e **todos os materiais de uma cena** são compatíveis. Caso a inicialização não funcione, usa `WebGLRenderer` com WebGL2; se o 3D não estiver disponível, mantém SVG ou poster. A criação assíncrona é serializada e cancelada quando o palco sai de tela. Perda de dispositivo WebGPU solicita uma remontagem em WebGL2; a perda real de dispositivo WebGPU ainda não foi induzida em teste.

A inicialização do renderer ainda não tem timeout: se a promessa de inicialização do navegador permanecer pendente indefinidamente, a fila de palcos também pode ficar bloqueada. Um timeout seguro requer garantir o descarte de qualquer dispositivo criado depois do prazo, sem abrir simultaneamente outro contexto. O teste nativo desta revisão usou flags explícitas do Chrome para habilitar WebGPU e ignorar o bloqueio de GPU; não prova que WebGPU esteja disponível nas configurações padrão de outros navegadores.

Erros de validação assíncronos do WebGPU podem chegar via `renderer.onError` e não são cobertos pelo tratamento síncrono de desenho; esse caminho de recuperação permanece pendente de prova. Falha no carregamento do módulo de efeitos, inicialização negada e perda de dispositivo injetada têm testes distintos.

Materiais GLSL (`ShaderMaterial`/`RawShaderMaterial`), modificações por `onBeforeCompile` e a primitiva `LineLoop` são incompatíveis com `WebGPURenderer`. Cenas que os contêm permanecem em WebGL2. Por exemplo, fase quente usa WebGPU quando o dispositivo o permite, enquanto a cena do Sol, com material GLSL, continua em WebGL2. A seleção examina também objetos ocultos da cena. Referência: [guia oficial de migração](https://threejs.org/manual/pages/webgpurenderer).

O renderer usa saída sRGB, tratamento de cor linear interno do Three e ACES; a exposição atual é um ajuste artístico por cena, não uma calibração física. No perfil Cinemática das cenas WebGPU compatíveis, um pipeline TSL opcional compõe bloom de luminância e SMAA antes da conversão final de cor; em WebGL2, Alta definição aumenta somente o limite de resolução. O buffer de profundidade logarítmico é usado em cenas compatíveis. Cenas GLSL legadas preservam a profundidade anterior para evitar oclusão incorreta entre shaders que não compartilhem os mesmos trechos. **Não há floating origin validada nem cobertura demonstrada de 1 m a 10 Gpc.**

A opção Automática começa em Padrão e passa para Econômica se o percentil 90 de pelo menos 90 intervalos de quadros de uma animação visível superar 30 ms. O relógio reinicia quando a animação pausa ou a aba fica oculta; travamentos entram na amostra. A medição reflete a cadência da aplicação, não tempo isolado de GPU. Ela só é ativada nos palcos cujo motor informa reprodução; os demais permanecem em Padrão até ajuste manual. O visitante pode escolher Econômica, Padrão ou Cinemática/Alta definição; o último modo não ativa um pipeline cinematográfico completo. A opção original de qualidade por palco continua preservada na remontagem.

## Ainda não entregue nesta fase

- Migração dos shaders GLSL e de `onBeforeCompile` para TSL, em todas as experiências.
- Pipeline HDR com exposição física, motion blur, TAA e profundidade de campo cinematográfica; bloom/SMAA só existem no perfil WebGPU Cinemática.
- Floating origin, teste de precisão em distâncias físicas extremas e perfis calibrados em todos os palcos.
- Meta sustentada de 60 fps em GPU integrada e 30 fps em celular de entrada; emulação de viewport não equivale a hardware móvel.
- Teste de perda real de dispositivo WebGPU e regressão visual por captura em todas as escalas.

O modelo das cenas continua didático. O renderer não transforma ilustrações em dados observados. Para testar a seleção e o fallback: `npm run test:webgpu` com `BASE_URL` apontando para um build local servido e `CHROMIUM` para o navegador disponível. A suíte injeta ausência e rejeição de GPU apenas para testar falhas; a execução nativa é identificada separadamente.
