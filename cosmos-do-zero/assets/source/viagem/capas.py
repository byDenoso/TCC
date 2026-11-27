"""Capas dos níveis do programa a partir dos pôsteres da viagem (renderizados no Blender).

Na pasta cosmos-do-zero:  python assets/source/viagem/capas.py

Cada capa é um recorte 3:2 do pôster de 2400 × 1500 px, centrado no objeto, salvo em
escola/public/imagens/<nome>.webp (1200 × 800) e nas versões de 820 e 440 px usadas nos cartões.
As capas de Astronomia (M51, Hubble) e Cosmologia (Planck) continuam sendo imagens observadas.
"""
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[3]
POSTERES = RAIZ / 'escola' / 'public' / 'viagem'
IMAGENS = RAIZ / 'escola' / 'public' / 'imagens'

# capa: (pôster, centro horizontal do recorte em fração da largura)
CAPAS = {
    'escala': ('luz', 0.37),         # Fundamentos: medir distâncias com a luz
    'orbita': ('sistema-solar', 0.5),  # Física Clássica: órbitas
    'plasma': ('buraco-negro', 0.5),   # Física Moderna: gravidade extrema
    'rede': ('teia-cosmica', 0.5),     # Cosmologia Avançada: estrutura em grande escala
}

for capa, (poster, cx) in CAPAS.items():
    im = Image.open(POSTERES / f'{poster}.webp').convert('RGB')
    w, h = im.size
    cw = round(h * 1.5)
    x0 = min(max(0, round(cx * w - cw / 2)), w - cw)
    recorte = im.crop((x0, 0, x0 + cw, h))
    recorte.resize((1200, 800), Image.LANCZOS).save(IMAGENS / f'{capa}.webp', quality=88, method=6)
    for largura in (820, 440):
        alt = round(largura / 1.5)
        recorte.resize((largura, alt), Image.LANCZOS).save(IMAGENS / 'mini' / f'{capa}-{largura}.webp', quality=86, method=6)
    print('capa', capa, '<-', poster)
