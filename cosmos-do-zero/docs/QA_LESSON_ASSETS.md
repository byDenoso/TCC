# Microscenas, resumos, endereço e estrelas

Verificação local em 18 de novembro de 2026, com Node 24.19 e Chromium do Playwright. As páginas foram servidas em loopback a partir do build estático do Astro.

| Superfície | Entrada para o inventário | Comportamento verificado |
| --- | --- | --- |
| Microscenas | IDs em `src/data/micro-frames.json`, botão `[data-mx-reference-toggle]`, imagem `[data-mx-reference]` | Os 35 SVGs mudaram com Avançar. As dez referências abriram e fecharam. Cada quadro listado foi decodificado. |
| Resumos | `[data-story-world]`, `[data-story-graphic]`, `[data-story-film]` | Seis resumos mantiveram a posição entre cena e filme. Cinco usam quadros por etapa. O resumo da origem desenha a onda de 400 a 800 nm. Os seis filmes têm 20 s, largura de 1280 px e legendas em português. |
| Endereço cósmico | `[data-scale-stage]`, grupos `[data-scale-visual]` | Cinco escalas com painel e imagem correspondentes. A captura em segunda execução coincidiu com cada referência. A menor diferença média entre duas escalas foi 7,80/255, acima do limiar de regressão de 2/255. |
| Estrelas | `[data-island="stars"] [data-star-svg]` | As escolhas de 0,3, 1 e 15 massas solares chegaram aos desfechos correspondentes. A imagem da nuvem aparece nas etapas de formação. O SVG mostra massa, cor, tamanho, trajetória e grau de certeza. |

Os quatro WebP derivados do Reel ocupam 465.200 bytes. O crédito, as dimensões e os hashes SHA-256 dos originais e resultados estão em `public/renders/reel-cycles/manifest.json`. A verificação releu os quatro PNG originais e os quatro WebP. Os clipes, as faixas VTT e os quadros por fase vêm de `public/media/stories/`.

## Reexecução

Com o build servido localmente, defina `BASE_URL` para o endereço do servidor e execute os comandos na raiz do projeto.

```powershell
node tests/lesson-assets.mjs
node tests/story-cinema.mjs
node tests/renders.mjs
node tests/scale-visual.mjs
```

O primeiro teste intercepta os pedidos de contexto GL em canvas e OffscreenCanvas e bloqueia HTTP externo. O percurso terminou com zero tentativas em ambos os contadores. O teste de cinema aprovou 343 verificações, incluindo reprodução real, busca temporal, movimento reduzido e troca de formato com metadados atrasados. O teste de renders decodificou 29 imagens e terminou sem erros HTTP de imagem. As cinco referências visuais estão em `tests/baselines/scale-assets/`. As asserções de endereço em `tests/e2e.mjs` também cobrem teclado e transporte do pulso de luz.

## Aceite no build integrado

Em `127.0.0.1:4378`, passaram os testes de microscenas, resumos, renders e regressão visual. O primeiro E2E detectou uma falha de acentuação na nota de procedência do mapa CMB. Após a correção, a suíte completa passou nas 1.224 verificações. O registro final está em `test-results/e2e-4378-final-20261118-221148-676.log`.

O percurso dos 35 diagramas também passou em um segundo build servido sob `/TCC/cosmos-do-zero/`. Na integração final, com os testes de motores aposentados removidos, o Vitest aprovou 224 testes em 27 arquivos. O Astro concluiu a checagem com zero erros, zero avisos e três sugestões.
