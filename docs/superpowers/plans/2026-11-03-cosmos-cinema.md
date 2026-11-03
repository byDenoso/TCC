# Cosmos Cinema Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** publicar a escola em azul profundo com seis cenas narrativas SVG/vídeo, leitura natural e modo cinema utilizável.
**Architecture:** uma biblioteca pura fornece metadados, estados e SVG das seis cenas. Astro faz SSR; um controlador usa o contrato de visibilidade existente. Filmes são renderizados da mesma biblioteca com Sharp/FFmpeg. O restante do site conserva seus motores, dados e IDs.
**Tech Stack:** Astro, TypeScript, SVG, Three.js, GSAP, Vitest, Sharp, FFmpeg.
**Spec:** `docs/superpowers/specs/2026-11-03-cosmos-cinema.md`

## Global Constraints
- Preservar URLs, armazenamento, quizzes, ciência e as alternativas sem JavaScript/WebGL.
- Azul profundo na interface; controles manuais e movimento reduzido prevalecem.
- Fonte única para geometria, rótulos e vídeos; mídia carregada sob demanda.
- Somente o projeto Cosmos; nenhuma migração React/Tailwind sem necessidade.

## Review Focus
- Saída e retorno à cena após pausa manual ou troca SVG/vídeo.
- Celular baixo: comandos e saída do cinema acessíveis, sem transbordamento.
- Mais de um SVG da mesma aula: IDs de clipping únicos.
- Dados ilustrativos identificados, sem inferência de observações reais.
- Escape, foco e posição preservados em todas as famílias de experiências.

### Task 1: modelos e narrativa audiovisual
**Files:** criar `src/lib/story-scenes.ts`, `tests/unit/story-scenes.test.ts`, `scripts/render-story-films.mjs`.
**Interface:** `STORIES`, `sampleStory(id, progress)`, `renderStory(id, progress, uid)`, `storyProgress(seconds)`. IDs correspondem às seis aulas.
- [x] Escrever e executar teste RED: expansão proporcional, raios de galáxias constantes; períodos keplerianos; altitudes válidas; seis narrativas; render finito e IDs únicos.
- [x] Implementar biblioteca e verificar GREEN + suíte unitária completa.
- [x] Gerar seis MP4, capas e legendas; verificar duração, frames e geometria de quadros representativos.

### Task 2: escola e transportes
**Files:** criar `components/StoryLesson.astro`, `scripts/story.ts`, `styles/cinema.css`; editar `main.ts`, início, catálogo e capítulos.
**Interface:** `[data-story]`, `[data-story-stage]`, `[data-story-play]`, `[data-story-time]`, `[data-story-phase]`, `[data-story-film]`; usa `visibleMotion`.
- [x] Escrever regressões de transporte e cinema no teste de navegador antes da integração.
- [x] Integrar seis cenas e filmes, miniaturas SVG e demonstrações antes do catálogo.
- [x] Verificar Astro, build, links e QA visual; progresso/quizzes preservados.

### Task 3: linguagem, paleta e cinema
**Files:** `cosmic-theme.css`, `school.css`, `cinema.css`, `experience.ts`, `Micro.astro`, `MotionLab.astro`, Hero e textos de entrada.
- [x] Trocar roxo visual por azul; compactar instruções repetidas; distinguir Avançar cena e Próximo assunto.
- [x] Ajustar cinema com cena e comandos visíveis, preservar foco e Escape.
- [x] Atualizar testes apenas quando a navegação ou a linguagem do produto mudar; manter asserts de função, acessibilidade e GPU.

### Task 4: revisão, prompt e publicação
**Files:** `docs/COSMOS_PROMPT_REWORK.md`, registro de entrega e testes relevantes.
- [x] Revisão independente do diff, corrigir questões importantes e executar verificações necessárias.
- [x] Persistir fonte e mídia, abrir/integrar PR na branch Cosmos e publicar nos dois destinos existentes.
- [x] Verificar a URL real, capturar resultado e registrar os checks.

## Ledger
- Base remota: `ecf53114189e45d055bb1ddfe988e078b39fda4a`, árvore `16580f533984f1bccb2327e5417f14335b20c84e`.
- Workspace: `/workspace/scratch/bbb1fb832b56/cosmos-motion-school`, isolado por worktree; dependências existentes reutilizadas por symlink ignorado.
- Pré-voo: a biblioteca da Task 1 é a única fonte consumida por componentes e exportação da Task 2; o cinema da Task 3 reconhece os mesmos seletores de transporte. Sem conflito de interfaces.
- Decisão: implementação nativa nesta sessão e uma revisão independente final; execução e publicação já autorizadas pelo usuário.

- Integração: a página inicial usa o MotionLab antes do catálogo; as histórias de 20 s abrem cada capítulo, sem repetir um segundo player na entrada.
- Evidência local: testes RED em modelos/limites de etapas antes das correções; 172 testes unitários GREEN; Astro sem diagnósticos; build público de 11 páginas, 261 fragmentos e 564 URLs/assets; teste HTTP aprovado.
- Mídia: seis filmes H.264, 1280×720, 24 fps, 480 quadros/20 s, sem áudio, com VTT; quadros inspecionados visualmente.
- Revisão independente: três achados de pausa, celular deitado e histórico corrigidos em `2a96e88`; reavaliação aprovou as correções. Suíte de navegador aprovada no CI e no domínio público.
- Publicação: novos PRs para a branch Cosmos passam pelo mesmo workflow de verificação; publicação continua condicionada à branch e marcador autorizados.

- Conferência final encontrou a camada GLSL do céu ainda com violeta. Teste GPU de pixels RED no CI `41713718270` (75,1% azul/ciano), correção revisada em `c938984`, etapa independente GREEN no CI `41714419269` para 390/1440 px; integrada pelo PR199. Nenhuma geometria ou interação mudou.

- Verificação pública encontrou dois sintomas de um clique perdido em primeiras estruturas. Sonda isolada CI `41720518581`: oito variações de assets passaram; IO atrasado200ms reproduziu o guard de visibilidade (palco na tela, primeira escrita true ausente, segundo clique inicia). Corrigido pelo PR201 via controlador de visibilidade, com prioridade direta para Avançar reduzido.
- PR201 (`41722044944`): Astro205 sem diagnósticos,172 unitários,8 céuGPU,170 cinema/transporte,54 shaders,26 visibilidade,34 dinâmica,1109 E2E e20 imagens aprovados. Revisão independente aprovou o controle e a preferência reduzida.

- Entrega final: fonte `92272aa265451172e787353dbd2f062cc5e77732`; workflow público `41722894450` com build, deploy Pages e verificação pública SUCCESS. No domínio principal: 8 checks de céu azul,170 cinema/transporte,1109 E2E sem falhas,54 shaders,26 visibilidade,34 dinâmica e20 imagens aprovados. Vercel READY no deployment `dpl_51h85XwxmF9WsHBucTQ697C3L1oB`. Capturas reais da entrada e da aula persistidas em `docs/screenshots/cosmos-cinema-principal-*.png`; os seis vídeos foram reproduzidos em ambos os endereços.
