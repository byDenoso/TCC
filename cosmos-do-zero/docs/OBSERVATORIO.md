# Observatório interativo e temas — 12/10/2026

## O que mudou

- **Observatório** logo após a abertura da home (`src/components/Observatorio.astro`), com quatro experimentos para quem nunca estudou cosmologia. Cada um tem palpite antes de mexer, leitura em linguagem do dia a dia e uma caixa opcional "Para quem quer os termos técnicos".
  1. **Máquina do tempo**: arraste para olhar mais longe. Mostra quando a luz saiu, quanto viajou, tamanho e temperatura do Universo então, onde a fonte está hoje, como a cor chega e a composição da época. Paradas: hoje, galáxias distantes, época de mais estrelas, primeiras galáxias, luz mais antiga.
  2. **O espaço crescendo**: grade de galáxias; toque numa para "morar" nela e deixe o espaço crescer. O gráfico mostra a proporcionalidade (lei de Hubble–Lemaître). Substitui a antiga cena de expansão do capítulo 2.
  3. **Meça como Hubble**: 16 galáxias fictícias com erro de distância (7 %) e movimento próprio (250 km/s); o visitante mede, vê a reta e o ritmo de expansão em km/s por milhão de anos-luz.
  4. **Do que o Universo é feito**: matéria, energia escura e ritmo de expansão → idade, acelerando/freando, futuro (cresce para sempre ou colapsa) e forma do espaço; comparação com o nosso Universo e a tensão de Hubble (67 × 73).
- Os experimentos também aparecem dentro das três jornadas: 1 → Máquina do tempo; 2 → Espaço crescendo + Receita; 3 → Meça como Hubble + Receita.
- **Temas**: claro (branco + turquesa vivo) e escuro (preto + dourado estelar). Segue o sistema; o botão no topo alterna e salva em `localStorage` (`cosmos-theme`), com funcionamento sem armazenamento. Tokens em `src/styles/global.css` (`--bg`, `--surface`, `--ink`, `--accent`, `--accent-ink`, `--on-accent`, cores de dados `--c-*`). As cores fixas antigas foram convertidas para esses tokens.
- Estado na URL: `?lab=tempo|expansao|hubble|receita`, `?z=`, `?om=&ol=&h0=`.

## Cálculo

`src/lib/cosmology.ts` integra as equações de Friedmann (matéria, radiação com Ωr h² = 4,18 × 10⁻⁵, energia escura constante e curvatura) sem dependências. Referência: ΛCDM plano do Planck 2018 (H₀ = 67,4; Ωm = 0,315). Testes em `tests/unit/cosmology.test.ts` conferem: idade 13,8 Gyr; tempo de viagem da luz em z = 1 ≈ 7,9 Gyr; distância comóvel até o CMB ≈ 13,9 Gpc; recombinação ≈ 372 mil anos; igualdade matéria–radiação z ≈ 3400; aceleração a partir de z ≈ 0,63; Einstein–de Sitter (2/3)/H₀; Big Crunch fechado π Ωm / (H₀ (Ωm − 1)^1,5).

Fontes: Planck Collaboration 2018 VI (arXiv:1807.06209); Riess et al. 2022, SH0ES (arXiv:2112.04510); Hubble 1929 (PNAS 15, 168).

## Testes executados (12/10/2026)

- `npm test`: 51/51 (23 antigos + 28 de cosmologia).
- `npm run check`: 0 erros, 0 avisos, 0 dicas.
- `node tests/e2e.mjs` (Chromium): 256 verificações, 0 falhas — inclui 5 larguras × 8 páginas, os 4 experimentos, abas por teclado, link direto, movimento reduzido, sem JavaScript, tema claro/escuro, persistência e armazenamento bloqueado.
- `tests/http.mjs`, `tests/renders.mjs`, `tests/pages-base.mjs` (build com base `/TCC/cosmos-do-zero`): passaram.
- **Não verificado:** `tests/browser-smoke.mjs` (Firefox e WebKit não estão instalados neste ambiente; o teste foi atualizado para o novo experimento); leitor de tela; aparelho físico.
