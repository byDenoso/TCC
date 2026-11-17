# Nebulosa do Céu

A nebulosa e o campo de estrelas são ilustrações procedurais autorais. A câmera da referência tem campo vertical de 55° e a distribuição das estrelas usa a semente 20261101.

O Blender reconstrói a nebulosa com a mesma função de ruído, paleta e posição de câmera usadas no quadro inicial do PlayCanvas. A referência usa Cycles em CPU, textura de emissão empacotada e estrelas editáveis. A mistura de transparência e o brilho pontual variam entre os motores.

Para reproduzir o enquadramento de 936 × 593 px, rode no diretório de `cosmos-do-zero`:

```powershell
blender --background --python assets/source/sky-nebula/build_reference.py -- --output ./nebula-reference --width 936 --height 593
```

O mapa de temperatura em `/ceu/` usa uma simulação diferente. `node scripts/render-cmb-map.mjs` regenera a prévia HTML a partir do mesmo campo sintético consultado pelos números do indicador.
