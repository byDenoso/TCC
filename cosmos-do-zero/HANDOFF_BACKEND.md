# HANDOFF — Frontend → Backend (ChatGPT/NEXO)

## Resumo

**Nenhuma função atual exige servidor.** O frontend está completo e funciona só com dados locais. Não há contas, banco, CMS nem API; nada foi inventado para justificar um backend. O que segue descreve (1) o que já funciona, (2) o único ponto de integração real que preparei como *opção*, e (3) decisões em aberto.

## Stack e versões

Node ≥ 20.19 (testado 22.22) · Astro 7.3.8 (static, `trailingSlash: 'always'`, `build.format: 'directory'`) · TypeScript 5.9 estrito · Vitest 3.2 · Playwright 1.64 (Chromium) · sharp 0.34 · @fontsource-variable (inter-tight, inter, fraunces 5.3).

## Comandos

```bash
npm install
npm run dev | build | preview | serve   # serve = servidor estático sem dependências em dist/
npm run check                           # astro check → 0 erros
npm test                                # vitest, 23 testes (src/lib)
npm run build && npm run preview &      # e então:
npm run test:e2e                        # 181 verificações Playwright (BASE_URL opcional)
```

## Rotas

| Rota | Fonte |
|---|---|
| `/` | `src/pages/index.astro` — jornadas, linha do tempo, planetas, laboratório (comparador + estrelas), quiz, glossário, fontes |
| `/capitulos/{id}/` | `src/pages/capitulos/[id].astro` — `id` ∈ `origem-do-universo`, `vida-das-estrelas`, `sistema-solar`, `terra-e-atmosfera`, `galaxias-e-nebulosas`, `misterios-do-cosmos` |
| `/404.html` | `src/pages/404.astro` |

Parâmetros de URL (estado compartilhável, via `history.replaceState`): `?marco=`, `?planeta=`, `?a=&b=`, `?massa=`, `?assunto=`, `?q=&jornada=`, `?nivel=entender|profundo`. IDs inválidos caem no padrão.

## Dados e tipos

Tudo em `src/data/*.json`, tipado por `src/types.ts` e exposto por `src/data/index.ts` (build) e `src/data/client.ts` (subconjunto leve no navegador: planetas, eras, perguntas, termos).

- `planets.json` — `Planet` (id, radius km equatorial, mass kg, gravity m/s², temperature °C, distance UA, orbit dias, rotation h — negativo = retrógrada…)
- `eras.json` (9 marcos), `questions.json` (12), `terms.json` (22), `chapters.json` (6 × 6 seções com níveis body/more/deep, equações, fontes), `site.json` (linhas da home, créditos de imagem, índice de 27 referências).
- IDs canônicos: `CHAPTER_IDS`, `PLANET_IDS`. Unidades e convenções do legado preservadas.

## O que já funciona integralmente no frontend

Navegação entre 6 jornadas e leitor (índice com scroll-spy, 3 níveis, barra de leitura) · linha do tempo (teclado: setas/Home/End) · 8 planetas + régua de tamanhos · comparador (troca, mesmo planeta) · evolução estelar (0,2–30 M☉, esfera e cor contínuas) · quiz (feedback, resultado, revisão, "refazer só as que errei", filtro por assunto) · glossário (busca sem acento, chips por jornada, estado vazio) · progresso local (persistente, entre abas via evento `storage`, fallback em memória com storage bloqueado) · fontes, créditos, referências · funciona sem JS para leitura.

## Backend — necessidade real: nenhuma. Opção preparada

Única fronteira de persistência: `ProgressStore` em `src/lib/progress.ts` (`read(): ChapterId[]`, `write(ids): boolean`). Se um dia houver sincronização entre dispositivos, implemente outra `ProgressStore`; nenhum componente chama rede diretamente.

Contrato proposto **somente se** o produto passar a exigir contas (hoje não exige):

- `GET /api/progress` → `200 { completed: ChapterId[], updatedAt: string(ISO) }` · `204` sem dados · `401` sem sessão.
- `PUT /api/progress` body `{ completed: ChapterId[] }` → `200` mesmo formato · `400` ID inválido · `401`.
- Auth: cookie de sessão (decisão aberta). Conflito: união dos conjuntos (progresso só cresce, exceto "reiniciar").
- UI: **local primeiro**; sincronizar em segundo plano; carregando = sem indicador bloqueante; erro/offline = continua local sem mensagem intrusiva (opcional, aviso discreto); vazio = progresso local prevalece. Hoje a UI já funciona assim para o caso "sem armazenamento".

Outros candidatos que *não* implementei por não haver demanda: telemetria de acertos do quiz (`POST /api/quiz-results {questionId, correct}`), formulário de contato/feedback. Ambos exigem decisão de privacidade.

## Decisões em aberto

1. Haverá contas? (determina tudo acima.)
2. Hospedagem estática (subcaminho exige `base` no `astro.config.mjs`; links já passam por `u()`).
3. Substituir ilustrações procedurais dos planetas por imagens oficiais (requer créditos).
4. Rótulo "Semieixo da órbita" vs "Distância média ao Sol" (ver `SCIENCE_NOTES.md`).

## Testes executados e limitações

Executados nesta entrega: `astro check` (0 erros/avisos), `vitest` (23/23), build (8 páginas), E2E Playwright Chromium (181 OK): 5 larguras (360/390/768/1024/1440) × 8 páginas sem rolagem horizontal nem erros de console; menu móvel; leitor (níveis, índice, voltar, progresso, sem localStorage); linha do tempo; 8 planetas (imagem carrega); comparador; massas estelares; quiz completo (12 perguntas, resultado, refazer, filtro); glossário (acentos, vazio, recuperação); imagens/alt/links internos/externos; movimento reduzido; foco visível; leitura sem JS. Bug real encontrado e corrigido durante o E2E: botões do quiz sem eventos no HTML estático.

**Não verificado:** Firefox/Safari/dispositivos reais (só Chromium); leitor de tela; validação axe-core (não executada); disponibilidade dos links externos de fontes (só presença/atributos); desempenho medido (Lighthouse). Valores numéricos de raio/massa/gravidade/temperatura/rotação não foram reconferidos linha a linha contra a NASA.
