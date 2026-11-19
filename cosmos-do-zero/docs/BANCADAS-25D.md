# Bancadas do Laboratório e do Observatório

As nove cenas usam Canvas 2D para compor projeções com profundidade, discos e sobreposições. As coordenadas de desenho são compartilhadas com os modelos e com as réguas SVG. Os gráficos e as leituras numéricas continuam disponíveis durante o carregamento ou falha das imagens.

| Bancada | O que responde ao controle |
| --- | --- |
| Órbita | Posição kepleriana e iluminação orientada para o foco. O raio visual dos corpos é ilustrativo. |
| Trânsito | Fase orbital, projeção, silhueta e curva de fluxo. A imagem da estrela tem textura, e a fotometria mantém a hipótese de brilho uniforme. |
| H–R | Temperatura altera a cor e o raio altera o tamanho do disco em escala comprimida. O marcador e a luminosidade usam os valores físicos. |
| Expansão FLRW | O espaçamento acompanha a = 1/(1+z). A reprodução até hoje percorre o tempo de viagem da luz do modelo, com interpolação da tabela e a resolução do controle de redshift. |
| Lente | A equação de lente fina remapeia o brilho da fotografia de M51 ou de uma fonte gaussiana. A geometria lateral mostra os dois raios, a lente e o observador. |
| Tempo | A tabela FLRW dá a posição do fóton e o fator de escala. A onda desenhada usa espaçamento comprimido. No movimento reduzido o botão avança o percurso em passos. |
| Espaço crescendo | As 14 galáxias mantêm seu tamanho enquanto mudam as separações em relação ao observador escolhido. |
| Hubble | As galáxias projetadas são selecionáveis por teclado ou ponteiro. O tamanho aparente é ilustrativo. O espectro e o ajuste usam a amostra simulada. |
| Receita | A projeção mostra o espaçamento previsto pela curva do modelo daqui a 5 bilhões de anos. O gráfico mostra toda a evolução. |

## Origem das imagens

A fotosfera foi renderizada em Blender 5.3, Cycles CPU, com a textura de granulação esférica do projeto. A Terra usa o quadro Blender do catálogo solar. A galáxia espiral usa um recorte suavizado da fotografia de M51. A mesma textura pode representar galáxias distintas nos campos didáticos. Os discos barrado e elíptico derivam dos mapas ilustrativos do catálogo v4. A região emissora antiga usa uma amostra do campo sintético do projeto, com cores ilustrativas.

Crédito de M51: NASA, ESA, S. Beckwith (STScI) e Hubble Heritage Team (STScI/AURA), CC BY 4.0. [Imagem original](https://esahubble.org/images/heic0506a/) · [Licença](https://creativecommons.org/licenses/by/4.0/)

Para reproduzir os assets locais a partir da raiz do projeto:

```text
blender -b -t 3 --python-exit-code 1 -P assets/source/lab/render_photosphere.py
python assets/source/lab/prepare_sprites.py
```

## Cobertura observada

A suíte `node tests/lab-plates.mjs` usa a porta 4339 ou a variável BASE_URL. Exercita nove cenas no Chromium, incluindo medidas de referência, mudanças dos pixels após controles, interação offline após a carga, ausência de pedidos de contexto GL no canvas, movimento reduzido e falhas de imagem/Canvas 2D.

A execução em viewport móvel de 390 × 844 confirmou a pausa fora da tela de órbita, trânsito, expansão FLRW e fóton. A suíte de autoplay confirmou também o comportamento da expansão do Observatório. Nas páginas de capítulos, cinco bancadas foram abertas em Chromium, Firefox e WebKit, verificando a presença de pixels no canvas carregado. A cobertura móvel foi emulada.

As evidências locais estão em `test-results/lab-plates/`, incluindo `bancadas.png`, capturas individuais, os logs de testes e o build estático isolado em `site/`. Passaram os 224 testes unitários, a checagem do Astro, as 25 verificações de autoplay, as 34 de dinâmica e a suíte das bancadas contra a saída estática.
