# Cosmos do Zero — escola interativa

Objetivo: tornar as seis aulas e os 36 passos existentes uma escola visual, com demonstrações automáticas e explicações próximas do fenômeno.

Decisões de execução: preservar Astro, TypeScript, os modelos 3D e suas alternativas SVG, URLs, fontes, equações, quizzes e chaves de progresso. Usar a branch cosmos-do-zero (000bb11) como base, mais completa que a publicação Vercel. Executar em branch isolada.

## Experiência

- Home: abertura cósmica, chamada direta para aprender, catálogo das seis aulas antes dos laboratórios e trilha de três aulas principais preservada.
- Aula: abertura curta, um conceito por passo, demonstração antes da explicação longa, índice e anterior/próximo. Instrumentos extras ao final, em exploração opcional.
- Cada passo recebe instruções específicas: o que observar, o que isso significa e uma ação para experimentar.
- Demonstração visível inicia sozinha, percorre opções/etapas e repete após uma pausa de leitura. Controles manuais interrompem a demonstração; botão explícito permite retomá-la.
- Pausa manual prevalece sobre sair/voltar à tela. Fora da tela/aba não há avanço. Movimento reduzido mantém controles discretos sem reprodução automática.
- A jornada CMB percorre suas três etapas automaticamente. A navegação automática não escreve parâmetros de URL nem anuncia cada quadro ao leitor de tela.
- Paleta padrão: espaço azul profundo, ciano para ações, violeta para destaque e branco frio para leitura; tema claro disponível e escolha salva preservada. Cores de dados físicos e texturas não são remapeadas.

## Abordagem

Evoluir a aplicação existente mantém as 36 experiências e a proveniência. Reconstrução completa duplicaria conteúdo; mudança apenas de cores não atenderia à didática nem ao comportamento automático.

## Verificação

Testar o relógio das demonstrações (etapas, escolhas, repetição, limites e passo temporal), cobertura dos guias nos 36 passos, testes existentes, diagnóstico Astro e build. Inspecionar home e aulas pelo navegador, incluindo pausa e retomada. Não alterar infraestrutura NEXO, permissões ou dados científicos.
