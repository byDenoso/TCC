# Vistas solares e cena de autoria

O estúdio usa 36 vistas por corpo, de 0° a 350°, com intervalo de 10°. A câmera ortográfica, a direção de luz e a inclinação de observação são fixas. Os discos são esféricos. O comparador aplica a razão dos raios equatoriais do catálogo ao diâmetro das imagens e usa a série de Saturno sem anéis. As velocidades de reprodução são ilustrativas.

## Arquivos

- `assets/source/solar-turntable/solar-turntable.blend` contém a câmera, a luz, as malhas, os materiais e 13 imagens incorporadas. O Blender 5.3.0 reabriu a cena em CPU. Os quadros de animação 1 a 9 selecionam os nove atlas de produção. Cada coluna mostra um corpo ou variante. As quatro linhas avançam 10° cada. A última linha da Lua vai de 30° no primeiro atlas a 350° no último.
- `assets/source/solar-materials/manifest.json` documenta os mapas locais e seus originais. O mapa de altura complementar está em `assets/source/solar-turntable/ldem_4_uint.tif`. O download do mosaico LROC de cor coincidiu byte a byte com o original local.
- `public/models/solar-turntable/manifest.json` lista os mapas usados por série, condições de uso, créditos, URLs e hashes. O material original dos anéis tem autoria declarada no projeto e nenhuma licença de redistribuição independente declarada no manifesto original.
- `public/models/solar-turntable/atlases/` contém as nove pranchas WebP de 4160 × 1280. As pastas por corpo contêm os recortes de 320 × 320 usados pelo navegador. As três variantes adicionais da Terra permitem alternar nuvens e atmosfera.
- `docs/screenshots/solar-turntable.png` reúne quatro ângulos dos nove corpos principais.

## Reprodução local

Execute a partir da pasta do projeto com Blender no PATH. O empacotamento usa Python e Pillow.

```powershell
$env:SOLAR_ATLAS_DIR = Join-Path $env:TEMP 'cosmos-solar-atlas'
blender -b -t 4 --python-exit-code 1 -P scripts/render_solar_turntable.py
python scripts/pack_solar_turntable.py $env:SOLAR_ATLAS_DIR
python scripts/pack_solar_turntable.py --verify-only
```

Para gerar novamente o arquivo editável, defina `SOLAR_SAVE_SCENE=1` no ambiente antes de executar o mesmo comando Blender. O script grava a cena de autoria. A renderização dos nove atlas desta entrega levou 8 min 15 s com quatro threads e quatro amostras por pixel.

## Aceite no build estático

Em 18 de novembro de 2026, o servidor local na porta 4378 entregou os 468 recortes e os nove atlas com SHA-256 idêntico ao manifesto. Os recortes totalizaram 2.877.582 bytes. O maior tem 11.800 bytes. Cada recorte foi decodificado, verificado quanto a dimensões, transparência, bordas, conteúdo distinto dentro da série e correspondência com a célula do atlas.

```powershell
node tests/solar-turntable.mjs http://127.0.0.1:4378
$env:BASE_URL = 'http://127.0.0.1:4378'
node tests/saturn.mjs
```

O Chrome abriu catálogo, comparador e estúdio com bloqueio de origens externas e instrumentação das chamadas de contexto gráfico. Foram observadas zero requisições externas e zero chamadas WebGL. O teste exercitou seleção, teclado, arraste, zoom, proporção dos raios, troca de lados, camadas e rotação da Lua. Uma falha induzida em 20° recuperou o quadro lunar de 0°. Uma falha no quadro inicial de Marte recuperou o retrato local.

O teste independente dos anéis exibiu as 91 inclinações, verificou 93 hashes e confirmou a recuperação de imagens, o pôster com JavaScript desligado e zero tentativas de WebGL no capítulo. Os testes unitários de catálogo e Kepler passaram em 34 casos. A checagem Astro retornou zero erros, zero avisos e três sugestões.

