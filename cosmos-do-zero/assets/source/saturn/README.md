# Saturno · anéis vistos de perfil

O piloto fica em `/capitulos/sistema-solar/#saturno-aneis`. O diagrama SVG e os controles de câmera ficam disponíveis enquanto o GLB carrega. PlayCanvas usa a mesma escala de câmera ortográfica e a mesma direção fixa de luz da cena Blender. A 0°, os anéis de largura finita e espessura desprezível são vistos pela borda. A linha nessa posição no diagrama tem espessura gráfica para assegurar a leitura.

## Editar e exportar

`public/models/saturn/scene.json` fixa o enquadramento horizontal, os ângulos de referência, a direção do Sol e os nomes dos objetos exportados. No GLB, o polo norte é +Y e a vista de perfil observa a partir de +Z. A câmera fica a uma distância fixa do centro e a vista aberta fica a 30° do plano dos anéis. O objeto de atmosfera compartilha o achatamento do planeta.

O `.blend` tem as texturas empacotadas. O perfil dos anéis contém a cor em RGB e a opacidade radial no alfa. A câmera, a iluminação e os materiais de referência ficam editáveis. O GLB leva os três objetos, as UVs e as texturas. PlayCanvas atribui os materiais de iluminação, sombra e espalhamento no limbo durante a montagem.

Na pasta `cosmos-do-zero`, execute com Blender 5.3:

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.3/blender.exe' --background --threads 6 --python-exit-code 1 --python assets/source/saturn/build_saturn.py -- --render
```

O comando gera `saturn.blend` e os quadros `blender-open.png` e `blender-edge.png` neste diretório, e grava `public/models/saturn/saturn.glb`. O argumento `--render` gera as duas referências a 960 × 540. Para repetir a exportação a partir do Python, edite o script e use os materiais de origem em `assets/source/solar-materials/`.

## Verificar no navegador

Sirva o build local e rode `node tests/saturn.mjs`, com `BASE_URL` apontando para a prévia quando a porta for diferente de 4321. O teste inclui teclado, toque em emulação, movimento reduzido, interrupção do GLB e perda real de contexto. Ele salva os quadros PlayCanvas de mesmo enquadramento, uma captura do diagrama em 390 px e as medições em `test-results/saturn/`. As medições de FPS contam chamadas efetivas de renderização durante mudanças repetidas de ângulo. Registre o aparelho físico separadamente da emulação.

## Créditos e limites

- O mapa de JPL/Caltech é uma textura ilustrativa distribuída pela NASA. Reutilizamos a versão do projeto em `assets/source/solar-materials/saturno.jpg`, que tem saturação reduzida. [NASA · Saturn](https://science.nasa.gov/3d-resources/saturn/)
- Geometria, faixa de opacidade, cores e espessura da atmosfera são escolhas didáticas e artísticas. O perfil dos anéis vem de `assets/source/prepare_solar_materials.py`. A posição solar é fixa e os dois motores reproduzem as sombras com técnicas próprias. [NASA · Cassini, Translucent Arcs](https://science.nasa.gov/resource/translucent-arcs/) · [NASA · Hubble Views Saturn Ring-Plane Crossing](https://science.nasa.gov/missions/hubble/hubble-views-saturn-ring-plane-crossing/)
