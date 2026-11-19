# Aposentadoria dos renderizadores em tempo real

Verificação local em 18 de novembro de 2026 no worktree cosmos-assets-1118.

O npm retirou three, @types/three e playcanvas do manifesto, do lock e da instalação local, junto com sete dependências exclusivas deles. A resolução pelo Node falhou para os três, como esperado. A varredura de imports em src, scripts e tests não encontrou consumidores dos pacotes.

Os módulos visuais ativos continuam em lensing.ts, world-view.ts e solar-studio.ts. world-frame.ts conserva as operações numéricas de posição e diferença em metros, inclusive frações de metro em coordenadas de 10²⁷ m. camera-exposure.ts conserva o cálculo de exposição. A suíte de escalas mantém as verificações de interpolação, tempo de vídeo e régua logarítmica.

Esta limpeza retirou 84 arquivos versionados, entre implementações de renderização, ferramentas antigas de captura, testes de GPU e seus auxiliares. As fontes editáveis e os dados brutos ficaram fora da edição. Os geradores antigos de retrato da Terra e filmes das aulas dependiam dos módulos aposentados. A versão completa que os executava está no Git em 44dd939abea03e4f86689ccfb3ebaff9e7f7be80. Exemplo de consulta a partir da raiz do repositório:

```sh
git show 44dd939abea03e4f86689ccfb3ebaff9e7f7be80:cosmos-do-zero/scripts/render-story-films.mjs
```

## Verificação

| Execução | Resultado observado |
| --- | --- |
| npm test | 224 testes passaram em 27 arquivos |
| npm run check | 223 arquivos, 0 erros, 0 avisos e 3 sugestões nos testes de integração e cinema |
| tests/visual-fallback.mjs contra Astro local | O controle de profundidade alterou o SVG, com zero pedidos de contexto WebGL/WebGPU no canvas |
| tests/autoplay-visible.mjs contra Astro local | 25 verificações passaram, incluindo avanço e reinício da Terra em movimento reduzido |

Uma execução contra o dist compartilhado encontrou os quadros 00 e 01 da Terra ausentes da distribuição. A segunda execução usou o servidor de desenvolvimento do mesmo worktree e verificou a decodificação dos dois arquivos em public.

## Verificação dos comandos de integração

O inventário offline agora lê os capítulos, seus controles e imagens de referência e confere as âncoras, os instrumentos e os arquivos de imagem no site compilado. Execute `node tests/inventory.mjs` na cópia do projeto para gerar `test-results/inventory/inventario.json` e `inventario.md`. As 36 seções de seis capítulos foram encontradas nas portas 4339 e 4378. Dez têm imagens de referência.

O gerador de vídeo de escalas dependia da captura do canvas WebGL aposentado. O vídeo editado continua em public. A implementação original pode ser consultada com `git show 44dd939abea03e4f86689ccfb3ebaff9e7f7be80:cosmos-do-zero/scripts/render-scale-journey.mjs`.

No workflow foram ajustados os caminhos de evidência das duas capturas de cinema e das imagens de Saturno. Os padrões do diagnóstico de GPU aposentado foram removidos. Os testes que bloqueiam GL ou verificam ausência de canvas continuam exercitando o comportamento esperado.

| Execução local | Resultado |
| --- | --- |
| http, pages | Servidor verificado. 18 páginas, 364 fragmentos e 1.178 URLs e recursos no build com base / |
| browsers, hero, budget, saturn, scales | Passaram. 56 verificações em Firefox e WebKit, 101.231 bytes gzip na primeira visita e zero chamadas GL observadas no teste de Saturno |
| autoplay, motion, dynamic | 25, 429 e 34 verificações passaram, respectivamente |
| experience | A primeira execução revelou um título com erro de codificação em /ceu/. Depois da correção do texto, os três subtestes passaram no build estático, inclusive o título com JavaScript desligado. Registro em `test-results/runtime-audit/experience-reteste.log` |
| npm test e npm run check | 224 testes aprovados. Checagem com 0 erros, 0 avisos e 3 sugestões |

A suíte de movimento passou a observar a mudança real do SVG com a figura visível. O teste de palpite abre o controle de divulgação antes de responder. E2E, renders, scale-visual, cinema e assets permaneceram com seus responsáveis. Os testes de navegador desta verificação usaram a distribuição local em 4378, com comparações em desenvolvimento em 4339. Os logs locais estão em `test-results/runtime-audit/`.
