import { Meta } from '../src/components/Frame';
import Viagem, { useEstacaoSalva } from '../src/components/viagem/Viagem';
import { atlasMedia, type AtlasId } from '../src/components/explorer/atlas-media';
import { stations } from '../src/components/explorer/explorer-data';
import { LevelCard } from '../src/components/Catalog';
import { MetodoPesquisa } from '../src/components/pesquisa/MetodoPesquisa';
function Continuar() {
  const salva = useEstacaoSalva();
  if (!salva) return null;
  return (
    <p className="editorial-continue">
      Você parou em <a href={'#' + salva.id}>{salva.rotulo}</a>.
    </p>
  );
}
export default function Home() {
  return (
    <>
      <Meta title="Cosmos · Escola de física, astronomia e cosmologia" />
      <section className="wrap editorial-opening">
        <div>
          <p className="kicker">Escola de ciências</p>
          <h1>Cosmos</h1>
          <p className="deck">Uma viagem em nove estações, da distância até a Lua à luz mais antiga do Universo. Em cada parada há uma relação física para testar e o caminho para as aulas e os laboratórios do programa.</p>
          <div className="editorial-actions">
            <a className="btn editorial-primary" href="#luz">Começar a viagem</a>
            <a className="text-link" href="#programa">Ver o programa em seis níveis</a>
          </div>
          <Continuar />
          <p>Dener Pereira · Cosmos</p>
        </div>
        <figure>
          <img src="https://cdn.esahubble.org/archives/images/screen/opo0501a.jpg" alt="Galáxia espiral barrada NGC 1300 observada pelo Hubble, com barra central e braços espirais." width={6637} height={3787} fetchPriority="high" />
          <figcaption><strong>NGC 1300</strong><p>Imagem observacional · Hubble · NASA, ESA e The Hubble Heritage Team (STScI/AURA). <a href="https://esahubble.org/images/opo0501a/">Imagem e legenda originais</a>.</p></figcaption>
        </figure>
      </section>
      <Viagem />
      <section className="wrap block" id="programa">
        <div className="section-title">
          <div>
            <p className="kicker">Percursos de estudo</p>
            <h2>Programa de estudos</h2>
          </div>
          <a className="text-link" href="/trilhas/">
            Ver todas as disciplinas
          </a>
        </div>
        <div className="level-grid">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <LevelCard i={i} key={i} />
          ))}
        </div>
      </section>
      <section className="home-atlas">
        <div className="wrap block">
          <div className="section-title">
            <div>
              <p className="kicker">Atlas do Universo</p>
              <h2>Atlas do Universo</h2>
              <p>Escolha uma imagem para explorar o que muda de uma escala para a seguinte.</p>
            </div>
            <a className="text-link" href="/explorador/">Abrir o Explorador</a>
          </div>
          <div className="home-atlas-grid">
            {stations.map((station) => {
              const id = station.id as AtlasId;
              const media = atlasMedia[id];
              return (
                <a href={'/explorador/#' + id} key={id} className={'home-atlas-card home-atlas-' + id}>
                  <img
                    src={id === 'solar' ? '/cosmos-hero/saturno-24-small.webp' : '/atlas/' + media.file}
                    srcSet={id === 'solar' ? '/cosmos-hero/saturno-24-small.webp 740w, /cosmos-hero/saturno-24.webp 1440w' : undefined}
                    sizes={id === 'solar' ? '(max-width: 470px) calc(100vw - 36px), (max-width: 800px) 46vw, 33vw' : undefined}
                    alt=""
                    loading="lazy"
                    decoding="async"
                  />
                  <div>
                    <h3>{station.short}</h3>
                    <p>{media.invitation}</p>
                    <small>{media.kind} · {media.credit}</small>
                  </div>
                </a>
              );
            })}
          </div>
        </div>
      </section>
      <MetodoPesquisa />
    </>
  );
}
