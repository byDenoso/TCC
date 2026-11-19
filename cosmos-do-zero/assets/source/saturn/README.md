# Saturno · anéis vistos de perfil

Em `/capitulos/sistema-solar/#saturno-aneis`, cada grau inteiro entre 0° (perfil) e 90° (polo norte) corresponde a uma imagem local. A abertura inicial de 30° usa o pôster. Ao mover o controle, o navegador solicita apenas o grau escolhido. O diagrama SVG acompanha a seleção durante a carga e quando a imagem falha. Com JavaScript desativado, o pôster continua disponível.

## Origem e reprodução

- Cena de autoria do Cosmos do Zero em `assets/source/saturn/saturn.blend`, com mapas empacotados. O construtor original é `build_saturn.py`. O lote lê diretamente o arquivo Blender.
- Mapa do globo de JPL/Caltech, distribuído pela NASA e adaptado em `assets/source/solar-materials/saturno.jpg`. O perfil radial de cor e opacidade foi criado em `assets/source/prepare_solar_materials.py`. Geometria, atmosfera e luz têm fins ilustrativos. [NASA · Saturn](https://science.nasa.gov/3d-resources/saturn/)
- A luz permanece fixa. A câmera ortográfica percorre o meridiano a distância constante, com a mesma escala nos 91 quadros. A largura de 6,8 unidades mantém o anel externo inteiro na vista polar.
- Cada WebP mede 704 × 512 pixels. O Cycles usa CPU, três threads, oito amostras por pixel e redução de ruído OpenImageDenoise em CPU. A qualidade WebP é 88. O pôster é uma cópia exata do quadro de 30°.
- `public/models/saturn/frames.json` identifica a versão do Blender, o SHA-256 da cena original, o grau, caminho relativo e SHA-256 de cada quadro e do pôster.

Na raiz do site, execute o lote em uma única instância do Blender:

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.3/blender.exe' -b assets/source/saturn/saturn.blend -t 3 --python-exit-code 1 -P assets/source/saturn/render_frames.py
```

## Validação

Com a prévia local do site em execução, rode `node tests/saturn.mjs`. A variável `BASE_URL` aceita o endereço da prévia com a subpasta do site. O teste verifica os hashes, percorre os 91 graus no Chromium com WebGL desativado, interrompe a rede para testar o diagrama e verifica a recuperação. O relatório e as capturas ficam em `test-results/saturn/`. `tests/saturn-phone.html` permite repetir a medição em um celular conectado ao servidor local.
