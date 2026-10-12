# Validação da versão com renders — 11/10/2026

Resultado local: versão consolidada compilada e navegável em http://127.0.0.1:4321/. Sem implantação pública concluída.

## Execuções confirmadas

| Verificação | Resultado |
|---|---|
| `npm run check` | 52 arquivos; zero erros, avisos ou sugestões |
| `npm test` | 29 testes unitários passaram |
| `npm run test:http` | GET, HEAD, MIME, 404, métodos, URL inválida e contenção de caminhos passaram |
| `npm run build` | Build estático final passou; oito páginas HTML, robots e sitemap |
| `npm run test:e2e`, com Chrome instalado em `CHROMIUM` | 231 verificações OK, zero falhas; execução final sobre o build consolidado |
| `npm run test:renders` | 24 estados de imagem carregados e decodificados; uma imagem por escala; srcsets das dez eras consistentes; zero erro HTTP de imagem |
| `npm run test:browsers` — WebKit | 23 verificações passaram |
| `npm run test:browsers` — Firefox | Bloqueado na inicialização do navegador pelo Windows; a execução conjunta retorna falha e não foi declarada aprovada |
| `npm audit --omit=optional` | Zero vulnerabilidades conhecidas na execução registrada |
| Revisão de conteúdo e legendas | Sem bloqueador científico identificado; cronologia e distinção entre observação e render preservadas |

E2E verifica as oito páginas em 360, 390, 768, 1024 e 1440 px, navegação, leitor, progresso persistido e falha de armazenamento, desmarcação, eras, planetas, comparador, evolução estelar, quiz, glossário, acessibilidade, conteúdo sem JavaScript e cenas com movimento reduzido. A abertura também recebeu inspeção visual em 1070 px.

O Firefox falhou antes de carregar a aplicação (`spawn UNKNOWN`). O diagnóstico local de Windows indicou SideBySide/`mozglue`. Nenhuma alteração de segurança ou de sistema foi feita para contornar esse bloqueio. O Chromium empacotado do Playwright não estava instalado; o E2E final usou o Chrome já instalado por meio da variável `CHROMIUM`.

## Inspeção visual

Foram conferidas a abertura no computador e celular, os previews e as três cenas após as imagens carregarem. A revisão detectou e corrigiu uma regra CSS que mostrava imagens de escalas inativas; o E2E passou a exigir uma única imagem visível. A máscara 2D do eclipse suaviza a borda sem recriar gráficos 3D.

Capturas finais em `screenshots/`:

- `home-renders-viewport-1440.png`, `home-renders-viewport-1070.png`, `home-renders-viewport-390.png`
- `home-renders-1440.png`, `home-renders-390.png`
- `previews-renders-1440.png`
- `scene-renders-scale-1440.png`, `scene-renders-expansion-1440.png`, `scene-renders-evidence-1440.png`

Os renders principais estão em WEBP 1200×800 e 600×400. O marcador de galáxia tem PNG transparente de 192×128, com alpha confirmado. Imagens fora da abertura são lazy; a abertura tem prioridade alta. Total aproximado de arquivos do build: HTML 227,8 kB; JS 47,8 kB; CSS 54,5 kB; imagens 2,34 MB. Esses totais não representam o download inicial nem desempenho medido em rede móvel.

## Publicação e pendências

A Vercel recusou a tentativa de prévia pelo limite diário da conta, `api-deployments-free-per-day` (mais de 100 deploys; resposta indicou tentar em 24 horas). Não houve URL de implantação concluída. Produção continua pendente de uma prévia pública revisada e aprovação de Dener.

Não foram executados: validação em telefone físico, sessões com cinco iniciantes, benchmark de desempenho móvel nem fluxo Firefox. Não foi reivindicado resultado de aprendizado medido.
