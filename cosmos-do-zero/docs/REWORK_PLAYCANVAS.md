# Cosmos do Zero · rework PlayCanvas

> Registro histórico do renderizador aposentado em novembro de 2026. Os comandos de teste vigentes estão no [README](../README.md).

O PlayCanvas renderiza os palcos da web. Saturno e a nebulosa têm cenas nativas. Os demais palcos reaproveitam as geometrias, cálculos e estados já autorados. O adaptador converte malhas, materiais, câmeras, luzes e primitivas para PlayCanvas enquanto a interface Astro controla a lição. Three.js continua como representação de autoria e conserva as rotinas de carga de assets e de câmera usadas nessas cenas.

O inventário em `scripts/rework-inventory.mjs` cruza as subseções das aulas com o catálogo e a lista de microcenas 3D visíveis. Registra separado o trabalho de Laboratório, Observatório, resumos, Saturno, Céu e Escalas. Dez variantes do catálogo seguem sem botão público, conforme a base. Os módulos e assets gráficos são solicitados pelo palco quando necessário. Uma fila comum coordena a criação e a liberação dos contextos WebGL2.

## Prévia local

Execute `npm ci`, `npm run build` e `node scripts/serve-dist.mjs 4332`. O endereço da aula-piloto é `http://127.0.0.1:4332/capitulos/sistema-solar/#saturno-aneis`. Para a sessão de teste em aparelho físico, use `COSMOS_PREVIEW_HOST` com o IP da rede local e sirva a saída de build. Copie `tests/saturn-phone.html` para a saída local para abrir a ferramenta de medição no aparelho.

## Autoria e exportação

- [Saturno](../assets/source/saturn/README.md) contém o Blender editável, os parâmetros e a exportação para GLB.
- [Nebulosa](../assets/source/sky-nebula/README.md) descreve a geração da referência Blender e seu enquadramento.

## Verificação

`npm run check`, `npm test` e `npm run build` verificam o projeto. Os testes de navegador usam a prévia ou a URL informada em `BASE_URL`. `npm run test:saturn` exercita os controles, as capturas, o carregamento, a perda de contexto e o diagrama. `npm run test:scales` percorre as dez paradas de Escalas. O navegador e o renderer aparecem nos resultados.
