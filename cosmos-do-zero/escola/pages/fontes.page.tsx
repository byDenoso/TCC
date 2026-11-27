import { atlasMedia } from '../src/components/explorer/atlas-media';
import { stations } from '../src/components/explorer/explorer-data';
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
          Os modelos 3D e os pôsteres da viagem da página inicial e os retratos dos planetas do
          Explorador são gerados no Blender por um script do próprio Cosmos, a partir de mapas da NASA:
          Blue Marble Next Generation (Terra), LROC (Lua), Hubble OPAL (Júpiter), MESSENGER (Mercúrio) e
          JPL/Caltech e USGS (demais planetas). Em Saturno, Urano e Netuno, as cores de cada latitude
          vêm desses mapas e as estrias finas são geradas. A galáxia, a teia cósmica (aproximação de
          Zel’dovich), o disco do buraco negro e o mapa da radiação de fundo (campo sintético) são
          modelos gerados, não observações. O buraco negro é desenhado por traçado de raios na
          geometria de Schwarzschild.{' '}
          <a href="/viagem/manifest.json">Lista dos arquivos gerados</a>.
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
        <h2>Imagens do Explorador</h2>
        <ul>
          {stations.map((station) => {
            const media = atlasMedia[station.id as keyof typeof atlasMedia];
            return <li key={station.id}><strong>{station.short}</strong> · {media.kind}. <a href={media.source}>{media.credit}</a></li>;
          })}
        </ul>
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
