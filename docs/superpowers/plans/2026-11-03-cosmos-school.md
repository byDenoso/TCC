# Cosmos School Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** entregar uma escola de cosmologia visual com seis aulas, 36 guias e demonstrações automáticas.
**Architecture:** preservar Astro e os runtimes existentes; extrair um relógio puro para demonstrações e acrescentar conteúdo didático por seção. Reorganizar as páginas e centralizar a nova paleta.
**Tech Stack:** Astro, TypeScript, Three.js, SVG, Vitest.
**Spec:** docs/superpowers/specs/2026-11-03-cosmos-school-design.md

## Global Constraints

- Preservar URLs, progresso, quizzes, conteúdo científico e alternativas sem WebGL.
- Pausa manual prevalece; não animar fora da tela, com aba oculta ou movimento reduzido.
- Não modificar dados científicos nem infraestrutura NEXO.

## Review Focus

- Troca de passo enquanto anima: a cena anterior deve parar.
- Escolha manual, saída e retorno: a pausa deve permanecer.
- Demonstração automática CMB: não alterar URL compartilhável a cada etapa.
- Tela estreita: controles, legendas e navegação devem permanecer legíveis.
- Tema claro salvo: preservar preferência e cores físicas.

### Task 1: Relógio e conteúdo didático

**Files:** `cosmos-do-zero/src/lib/demonstration.ts`, `cosmos-do-zero/src/data/lesson-guides.ts`, `cosmos-do-zero/tests/unit/demonstration.test.ts`, `cosmos-do-zero/tests/unit/lesson-guides.test.ts`.
**Interfaces:** `advanceDemonstration(state, dt, spec)` retorna valor/fase/espera; `LESSON_GUIDES[sectionId]` fornece observe/connect/try.

- [ ] Testes primeiro: escolhas/etapas avançam e repetem; range fica no intervalo e espera antes de repetir; mesmo tempo em 60/120 Hz; todo passo tem guia.
- [ ] Implementar os dois módulos e executar os testes unitários.

### Task 2: Escola e aulas visuais

**Files:** Hero, Header, ChapterList, Micro, página inicial, página de capítulos, Base, cosmic-theme.css, school.css.
**Interfaces:** consome `LESSON_GUIDES`; mantém seletores de progresso e controles existentes.

- [ ] Catálogo das seis aulas, home com prioridade para aprender, abertura e identidade cósmica.
- [ ] Cena antes de texto longo, guias individuais e instrumentos extras opcionais.
- [ ] Tema escuro padrão e tema claro explícito; controles responsivos.
- [ ] Validar com `npm run check` e `npm run build`.

### Task 3: Integração e entrega

**Files:** micro/engine.ts, visible-motion.ts, cmb-journey.ts, experience.ts.
**Interfaces:** consome relógio da Task 1; `visibleMotion.automatic()` retoma demonstração explicitamente.

- [ ] Integrar reprodução contínua com controle manual e sem alterar progresso automaticamente.
- [ ] Percorrer as três etapas CMB e preservar navegação manual/URL.
- [ ] Rodar testes, diagnóstico, build e verificação visual. Revisão independente do diff.
- [ ] Persistir código em branch/PR e publicar a experiência no destino autorizado, conferindo o resultado.
