# Cosmos · Escola Digital

A escola atual está em [escola/](escola/README.md). O domínio [cosmos.denerpereira.com.br](https://cosmos.denerpereira.com.br) serve a versão estática e [cosmos-do-zero.vercel.app](https://cosmos-do-zero.vercel.app) também oferece a API acadêmica.

## Acervo da edição Astro


Planetário editorial em português com seis aulas, fotografias astronômicas e experiências guiadas. O Astro gera HTML estático. As vistas dos mundos chegam como imagens prontas do Blender Cycles. Os controles de órbita, expansão, lente gravitacional e tempo continuam calculando os resultados no navegador.

## Executar localmente

Com Node 22.12 ou superior, execute na pasta do site:

```sh
npm ci
npm run dev
```

Para testar a saída estática, execute `npm run build` e depois `npm run serve`. O servidor de prévia atende na porta 4321 por padrão. Use `BASE_URL` ao executar os testes em outra porta ou subpasta. `SITE_BASE` define a subpasta durante a compilação.

A História do Universo usa 12 imagens fotográficas ou ilustrações preparadas, com enquadramento suave e carregamento por etapa. O marco das primeiras galáxias apresenta o campo GOODS-S observado pela NIRCam do Webb no levantamento JADES. Cada cartão identifica o tipo de imagem e dá acesso ao crédito. O endereço `/#viagem-galaxies` abre o sétimo marco.

## Explorar

- **Início e aulas.** A página inicial leva à primeira pergunta ou à escolha de outro tema. As seis aulas preservam as âncoras, os quizzes e a retomada da leitura. As 35 microexperiências têm cenas em Canvas 2,5D que acompanham os controles. O botão **Ver diagrama** alterna para a representação analítica. As cinco experiências de luz e galáxias da página inicial apresentam a cena espacial e o botão **Ver medidas**.
- **Laboratório.** O catálogo e o comparador compartilham a mesma convenção de ângulo. Há arraste horizontal, controle de rotação e zoom. O comparador orienta as duas imagens em conjunto. Os resultados numéricos vêm dos modelos didáticos.
- **Saturno.** A câmera percorre as inclinações de 0° a 90° em passos de um grau. Na ausência de um quadro, um diagrama acompanha o valor escolhido.
- **Escalas.** Dez paradas, do próton ao universo observável. A régua usa o logaritmo do tamanho em metros. O trecho Terra–teia cósmica usa um vídeo controlado pela posição da régua. Os pôsteres também permitem percorrer as paradas, e a versão HTML apresenta a lista completa. Os valores e referências estão em `src/data/scale-stations.ts`.
- **Imagens e Céu.** A fotografia de M51 mantém o crédito Hubble e a proporção do original. A nebulosa que se pode mostrar em Céu é uma ilustração autoral. O mapa interativo da radiação cósmica de fundo identifica seu campo sintético.

## Materiais e autoria

| Material | Origem e reprodução |
|---|---|
| Mapas e retratos dos mundos | `assets/source/solar-materials/manifest.json`, `assets/source/mundos.blend` |
| Rotações e camadas | `assets/source/solar-turntable/solar-turntable.blend` contém a cena editável. `scripts/render_solar_turntable.py` gera os atlas no Cycles. `scripts/pack_solar_turntable.py` recorta os quadros e verifica hashes e dimensões |
| Anéis de Saturno | `assets/source/saturn/saturn.blend`, `assets/source/saturn/render_frames.py`, `public/models/saturn/frames.json` |
| Nebulosa de Céu | `assets/source/sky-nebula/nebulosa.blend`, `build_reference.py` e README no mesmo diretório |
| Teia, galáxia, nebulosa e órbitas ilustrativas | Cenas em `assets/source/reel-cycles/`. `public/renders/reel-cycles/manifest.json` identifica os quadros e a conversão para WebP |
| M51 e sua companheira | `assets/source/m51.json` identifica o original ESA/Hubble, o crédito completo e as quatro versões proporcionais |
| Formação do Sistema Solar | Texturas de Barnard 59, HL Tauri e ilustração ESO/L. Calçada em `assets/source/formation/manifest.json`. Os agregados minerais e de gelo têm cena Blender e renderizador em `assets/source/formation/` |
| Pôsteres e microexperiências | `public/posters/manifest.json` e `src/data/micro-frames.json` |

Créditos completos acompanham as experiências e a página `/fontes/`. Os mapas de missão, os modelos ilustrativos e as fotografias têm origens diferentes. Os materiais de terceiros preservam os créditos individuais. Os arquivos em `docs/rework/` e o relatório `docs/REWORK_PLAYCANVAS.md` documentam a versão histórica.

## Verificar

`npm run check`, `npm test` e `npm run build` verificam os tipos, os testes unitários e a saída estática. Com a variável `BASE_URL` apontando para a prévia, `npm run test:depth` exercita as cenas das aulas, da página inicial e das bancadas, inclusive alternativas a falhas de mídia. Com o site servido, `npm run test:assets` exercita a navegação com as APIs 3D bloqueadas. `test:scales`, `test:saturn`, `test:hero`, `test:renders`, `test:e2e`, `test:browsers` e `test:cinema` exercitam as experiências específicas. `test:budget` mede HTML/CSS/JS da primeira visita com gzip nível 6 e registra à parte as imagens e os vídeos carregados.

A retomada usa as chaves já existentes, incluindo `cosmos-v3-progress`, `cosmos-v5-selos`, `cosmos-v6-praticado`, `cosmos-v6-onde`, `cosmos-quiz:${pathname}:${chapter}` e `cosmos-quiz-review`. O armazenamento é separado por origem.
