# Cosmos do Zero

Portal educativo de cosmologia em pt-BR para quem começa do zero. Três jornadas principais — nosso lugar no Universo, sua evolução e as evidências — com três capítulos complementares de astronomia. Inclui exploração de escalas, expansão e luz, linha do tempo, planetas, evolução estelar, quiz, glossário e progresso local.

**Estático e local:** todo o conteúdo vive em `src/data/*.json`; não há servidor, banco de dados nem chamadas de rede em tempo de execução (só links externos para fontes). Ver `HANDOFF_BACKEND.md`.

## Stack

Astro 7 (saída estática) · TypeScript estrito · Vitest · Playwright · fontes locais (Inter Tight, Inter, Fraunces — subconjunto latin). Node ≥ 22.12; implementação executada com Node 24.19.0. Publicação preparada para GitHub Pages, com Node 24 no GitHub Actions.

## Comandos

```bash
npm ci
npm run dev          # desenvolvimento em http://localhost:4321
npm run build        # gera dist/ (11 páginas) + relatório de tamanho
npm run preview      # serve dist/ via Astro      (alternativa: npm run serve)
npm run check        # astro check (tipos)
npm test             # 115 testes unitários (lógica em src/lib)
npm run test:http    # servidor estático: caminhos, métodos, MIME e erros
npm run test:e2e     # Playwright contra http://localhost:4321 (suba o preview antes)
npm run test:browsers # fluxo principal em Firefox e WebKit
npm run test:renders # carregamento e troca das imagens renderizadas em Chrome
SHOTS=1 npm run test:e2e   # idem, salvando capturas em docs/screenshots
```

Para publicar em subcaminho, defina `base` em `astro.config.mjs`; todos os links internos passam por `u()` (`src/lib/url.ts`).

Os E2E precisam de um navegador Playwright instalado. Para usar um Chrome existente, defina `CHROMIUM` com o caminho do executável; alternativamente, instale o Chromium do Playwright com `npx playwright install chromium`. `test:renders` usa o Chromium instalado pelo Playwright ou o executável definido em `CHROMIUM`. `test:browsers` requer as versões Firefox/WebKit do Playwright; o resultado registra separadamente cada navegador.

## Estrutura

```
src/
  data/        conteúdo (JSON) + index.ts (gateway tipado) + client.ts (subconjunto leve p/ o navegador)
  types.ts     tipos e IDs canônicos (CHAPTER_IDS, PLANET_IDS)
  lib/         lógica pura e testada: format, planets, stars, quiz, glossary, progress, url-state, url, images
  components/  seções da home (ChapterList, Timeline, PlanetCatalog, Lab, Quiz*, Glossary, Sources) + Header/Footer/Hero
  pages/       index, capitulos/[id], 404
  scripts/     ilhas de interatividade (uma por seção) ligadas por atributos data-*; main.ts carrega somente as ilhas presentes em cada página
  styles/      global.css (tokens, hero, rodapé) · home.css · reader.css · fonts.css
  assets/      planetas (render procedural) e fotos oficiais reencodadas
public/renders/ imagens conceituais prontas: WEBP responsivo e PNG transparente
scripts/       render_planets.py (gera as ilustrações), extract_legacy.py (extração única do HTML legado), postbuild, serve-dist
tests/         unit/lib.test.ts · e2e.mjs
```

## Princípios

- **Melhoria progressiva:** o HTML já traz o estado inicial (comparação Terra × Júpiter, percurso estelar de 1 M☉, 1ª pergunta do quiz, lista do glossário). O JS liga os controles.
- **Estado em URL:** `?marco=`, `?planeta=`, `?a=&b=`, `?massa=`, `?assunto=`, `?q=&jornada=`, `?nivel=entender|profundo`.
- **Progresso:** `localStorage` (`cosmos-v3-progress`, preservada do legado) com fallback em memória se o armazenamento estiver bloqueado.
- **Rotulagem de imagens:** fotografia · observação em cores compostas · ilustração conceitual/artística, sempre com legenda e crédito.
- **Movimento reduzido:** `prefers-reduced-motion` desliga animações contínuas.

Notas científicas e verificação dos dados: `SCIENCE_NOTES.md`. Decisões, preparação de publicação e limitações: `docs/IMPLEMENTACAO.md`. Resultados da versão consolidada: `docs/VALIDACAO.md`. Prompts e origem dos renders: `docs/render-assets.json`.

## Imagens renderizadas

Eclipse, escalas cósmicas, evidências, linha do tempo e estrela usam imagens raster geradas previamente. A teia cósmica e a Máquina do tempo também usam cenas Three.js/WebGL quando disponíveis. Esses módulos carregam sob demanda e pausam fora da tela; desenhos SVG preservam a explicação quando WebGL não está disponível ou há preferência por movimento reduzido. A formação dos átomos e a viagem da CMB usam Canvas 2D.

Os dez renders foram gerados com a ferramenta integrada `image_gen`, em resoluções responsivas de 1200×800 e 600×400. A galáxia da malha usa PNG de 192×128 com transparência. As legendas distinguem arte conceitual de observações oficiais. A imagem de luz antiga não é um mapa medido da CMB; o halo azul de matéria escura é uma convenção visual.

## Publicação em domínio próprio e fallback

Domínio final: https://cosmos.denerpereira.com.br/ (`SITE_BASE=/`).
Fallback: https://bydenoso.github.io/TCC/cosmos-do-zero/ (`SITE_BASE=/TCC/cosmos-do-zero`).
Apenas a branch `cosmos-do-zero` de `byDenoso/TCC` recebe o projeto.
Push executa testes sem publicar. O workflow manual separa build e publicação.
Leia `docs/PUBLICACAO_PAGES.md` para acesso, migração e rollback; o domínio
não foi configurado por esta preparação. Resultados desta execução ficam no
relatório anexo ao pacote, não nas validações históricas da versão original.
