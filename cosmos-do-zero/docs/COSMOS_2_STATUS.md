# Cosmos do Zero 2.0

Base de trabalho `byDenoso/TCC`, branch `cosmos-do-zero`, commit `2d95f49`. Destino desta revisão `https://cosmos-do-zero.vercel.app`. Astro estático, TypeScript, SVG e o motor 3D existente. As seis aulas, fragmentos, quizzes e progresso continuam no mesmo percurso.

| Área | Implementação | Como conferir |
|---|---|---|
| Sistema editorial | Abertura com Webb, paleta de exposição, tratamento de aulas, dicionário, fontes, laboratório e 404. Metadados WebSite e LearningResource | `/`, as seis aulas, `/fontes/`, `/glossario/`, `/laboratorio/` |
| Luz e espectroscopia | Prólogo por rolagem, emissão e absorção calculadas e redshift manipulável. Campo profundo NIRCam e dois espectros observados NIRISS creditados | `/#prologo`, `/#luz-cena-3` |
| Escalas | Cinco cenas em progressão e régua logarítmica. O explorador 3D existente mantém a alternativa SVG e as distinções entre escala física e render conceitual | `/#escala-cosmica`, aula de galáxias em `#exploracao` |
| Tempo cósmico | Doze marcos, com Idade das Trevas e reionização. Identificadores legados de `?marco=` preservados | `/#viagem`, `/laboratorio/#tempo` |
| Buracos negros | Sequência de órbitas, acreção, horizonte e evidência em rádio de Sagittarius A*. Diagrama conceitual identificado separadamente da imagem EHT | Aula de galáxias em `#buracos-negros` |
| Órbitas | Dois corpos pontuais, massas, posição, excentricidade, velocidade relativa, período, energia e áreas de igual duração | `/laboratorio/#orbitas`, aula do Sistema Solar |
| Expansão | FLRW com curvatura e CPL em comparação com ΛCDM de referência. H(z), a(t), distância de luminosidade e tempo de viagem | `/laboratorio/#expansao-modelos`, aula de origem |
| Trânsitos | Sobreposição de discos em órbita circular, com raios, inclinação, curva de luz e cenários | `/laboratorio/#transito`, aula de mistérios |
| Estrelas | Hertzsprung–Russell em eixos logarítmicos com leitura em unidades solares. Modelos de exemplo e fonte observacional Gaia identificados | `/laboratorio/#diagrama-hr`, aula de estrelas |
| Lentes | Lente fina pontual com massa e alinhamento variáveis, imagem calculada e geometria 3D opcional | `/laboratorio/#lente-gravitacional`, aula de mistérios |

## Reproduzir a validação

```sh
cd cosmos-do-zero
npm ci
npm run check
npm test
npm run test:http
SITE_URL=https://cosmos-do-zero.vercel.app SITE_BASE=/ SITE_PUBLIC=true npm run build
SITE_URL=https://cosmos-do-zero.vercel.app SITE_BASE=/ SITE_PUBLIC=true npm run test:pages
npm run serve
# Em outro terminal com Chromium do Playwright instalado
npm run test:e2e
npm run test:budget
```

A suíte numérica testa o limite ΛCDM, integrais de distância e tempo, equação de Kepler e áreas iguais, geometrias de trânsito, lei de Stefan–Boltzmann e lente pontual. Cada bancada mostra aproximações, unidades e referências. Os retratos de Idade das Trevas e reionização derivam dos estados ilustrativos em `src/lib/journey.ts`.

A meta de Core Web Vitals em p75 depende de telemetria de visitantes. A inspeção visual e os testes automatizados locais não constituem certificação WCAG 2.2 AA. Permanecem fora desta versão uma biblioteca independente com todos os diagramas do caderno, distribuições interativas de redshift de levantamentos e um motor gravitacional de muitos corpos.
