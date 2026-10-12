# Notas científicas

Nenhum valor numérico, texto científico, ID ou unidade foi alterado em relação ao conteúdo legado (`src/data/*.json` foi extraído do HTML original por `scripts/extract_legacy.py`).

## Verificado

- Colunas de distância ao Sol e período orbital dos planetas conferidas em 12/10/2026 contra a tabela principal da NASA/NSSDCA *Planetary Fact Sheet* (https://nssdc.gsfc.nasa.gov/planetary/factsheet/): Júpiter 778,5 ×10⁶ km / 4331 d; Marte 228,0 / 687,0; Saturno 1432,0 / 10 747; Urano 2867,0 / 30 589; Netuno 4515,0 / 59 800. Convertidos a UA (÷149,6) coincidem com o arquivo (9,57; 19,17; 30,18).
- Demais colunas (raio, massa, gravidade, temperatura, rotação) **não** foram reconferidas linha a linha nesta entrega; os valores seguem o legado e as três páginas NASA listadas sob o catálogo.

## Observações para revisão editorial (nada foi alterado)

1. **"Semieixo da órbita"** — a tabela principal da NASA rotula a coluna como *Distance from Sun* (média). A interface usa "semieixo", que é a leitura das notas da NASA (https://nssdc.gsfc.nasa.gov/planetary/factsheet/planetfact_notes.html). Se quiser o rótulo literal: "Distância média ao Sol".
2. **Temperaturas** — superfície (média) para rochosos, 1 bar para gigantes. A interface já explicita isso na linha "Onde é medida"; manter.
3. **Ilustrações dos planetas** são geradas proceduralmente (`scripts/render_planets.py`), rotuladas "Ilustração artística · sem escala". Não representam feições reais; substituir por fotos/composições oficiais exigiria nova curadoria de créditos.
4. **Percursos estelares** — corte em 8 M☉ é pedagógico (já dito na própria nota da interface). A esfera ilustrativa usa raio de sequência principal aproximado (R ∝ M^0,9 abaixo de 1 M☉, M^0,6 acima) apenas para dar ideia de tamanho; não é dado do conteúdo.
