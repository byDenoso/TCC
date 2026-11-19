import { Lead, Meta } from '../src/components/Frame';
import { curriculum } from '../src/lib/content';
import { labs } from '../src/lib/model';
import { NEXO } from '../src/lib/school';
export function getStaticProps() {
  return {
    props: {
      sources: [
        ...new Map(
          [...curriculum().map((c) => c.meta.reference), ...labs.map((l) => l.reference)].map((r) => [
            r.url,
            r,
          ])
        ).values(),
      ],
    },
  };
}
export default function Sources({ sources }: { sources: { name: string; url: string }[] }) {
  return (
    <>
      <Meta title="Fontes e créditos" />
      <Lead
        tag="Acervo da escola"
        title="Fontes e créditos"
        text="Cada aula e bancada indica a referência usada para a relação física. Gráficos gerados pela escola identificam os modelos e suas aproximações."
      />
      <div className="wrap reading block prose">
        <h2>Imagens e simulações</h2>
        <p>
          A fotografia de M51 é de NASA, ESA, S. Beckwith (STScI) e The Hubble Heritage Team
          (STScI/AURA). A capa de trilha usa um recorte responsivo.{' '}
          <a href="https://esahubble.org/images/heic0506a/">Imagem original</a> ·{' '}
          <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.
        </p>
        <p>
          O modelo ilustrativo de Saturno usa o mapa JPL/Caltech e NASA. As representações da Terra, do
          Sistema Solar, da estrela e da teia cósmica são ilustrações do acervo Cosmos.{' '}
          <a href="/cosmos-hero/creditos.json">Crédito e composição de Saturno</a>.
        </p>
        <p>
          A capa de Cosmologia mostra as anisotropias da radiação cósmica de fundo observadas pelo
          satélite Planck. Crédito ESA e Planck Collaboration. As cores representam variações de
          temperatura. O laboratório de CMB calcula o espectro do corpo negro.{' '}
          <a href="https://www.esa.int/media/planck-s-view-of-the-cosmic-microwave-background-en-213137">
            Mapa original do Planck
          </a>
          .
        </p>
        <h2>Pesquisa pública</h2>
        <p>
          O acervo do NEXO registra hipóteses, testes e resultados com escopo próprio. Os exercícios do
          Cosmos usam dados fornecidos no enunciado ou curvas calculadas.{' '}
          <a href={NEXO}>NEXO Research</a>.
        </p>
        <h2>Bibliografia das aulas e laboratórios</h2>
        <ul>
          {sources.map((s) => (
            <li key={s.url}>
              <a href={s.url}>{s.name}</a>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}
