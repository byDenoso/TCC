import { Meta } from '../src/components/Frame';
import { atlasMedia, type AtlasId } from '../src/components/explorer/atlas-media';
import { stations } from '../src/components/explorer/explorer-data';
import { LevelCard } from '../src/components/Catalog';
import { CourseImage } from '../src/components/CourseImage';
import HeroSky from '../src/components/hero/HeroSky';
import MotionBand from '../src/components/MotionBand';
import { LabView } from '../src/components/Laboratory';
import { cards } from '../src/lib/content';
import { NEXO, type Card } from '../src/lib/school';
export function getStaticProps() {
  const all = cards();
  return {
    props: {
      start: all[0].slug,
      featured: [
        'o-periodo-revela-a-orbita',
        'o-tamanho-do-horizonte',
        'distancia-que-acompanha-o-fluxo',
      ].map((x) => all.find((a) => a.slug === x)!),
    },
  };
}
export default function Home({ start, featured }: { start: string; featured: Card[] }) {
  return (
    <>
      <Meta title="Cosmos · Escola de física, astronomia e cosmologia" />
      <section className="wrap editorial-opening">
        <div>
          <p className="kicker">Escola de ciências</p>
          <h1>Cosmos</h1>
          <p className="deck">Programa de física, astronomia e cosmologia em seis níveis. Estude as relações matemáticas, compare observações e teste modelos nos laboratórios.</p>
          <div className="editorial-actions">
            <a className="btn editorial-primary" href={'/aulas/' + start + '/'}>Começar pela primeira aula</a>
            <a className="text-link" href="/trilhas/">Consultar o programa</a>
          </div>
          <p>Dener Pereira · Cosmos</p>
        </div>
        <figure>
          <img src="/atlas/m31.webp" alt="Mosaico do disco de Andrômeda observado pelo Hubble." fetchPriority="high" />
          <figcaption><strong>Galáxia de Andrômeda</strong><p>{atlasMedia.m31.kind} · {atlasMedia.m31.credit}. <a href={atlasMedia.m31.source}>Imagem e legenda originais</a>.</p></figcaption>
        </figure>
      </section>
      <section className="hero">
        <HeroSky />
        <div className="wrap hero-content">
          <div className="hero-text">
            <p className="kicker">
              <i />
              Modelo ilustrativo
            </p>
            <h2>Saturno e seus anéis</h2>
            <p className="hero-deck">
              Varie a inclinação dos anéis para comparar a geometria projetada do planeta.
            </p>
            <div className="hero-actions">
              <a className="btn light" href={'/aulas/' + start + '/'}>
                <svg viewBox="0 0 20 20" aria-hidden="true">
                  <path d="m6 3 10 7-10 7z" fill="currentColor" />
                </svg>
                Começar a aprender
              </a>
              <a className="btn ghost" href="/laboratorios/expansao/">
                Testar a expansão
              </a>
            </div>
          </div>
        </div>
        <div className="hero-caption">
          SATURNO <span> / </span> Modelo ilustrativo
        </div>
      </section>
      <section className="wrap block">
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
      <section className="home-lab">
        <div className="wrap block">
          <div className="section-title">
            <div>
              <p className="kicker">Experimente agora</p>
              <h2>Quanto dura um ano?</h2>
              <p>Afaste o planeta de sua estrela e acompanhe o período orbital.</p>
            </div>
            <a className="text-link" href="/laboratorios/orbitas/">
              Abrir bancada completa
            </a>
          </div>
          <LabView id="orbitas" mini />
        </div>
      </section>
      <section className="wrap block">
        <div className="section-title">
          <div>
            <p className="kicker">Leituras selecionadas</p>
            <h2>Aulas selecionadas</h2>
          </div>
        </div>
        <div className="feature-grid">
          {featured.map((l, i) => (
            <a className="feature" href={'/aulas/' + l.slug + '/'} key={l.slug}>
              <CourseImage file={['orbita.webp', 'estrela.webp', 'm51.webp'][i]}
                sizes="(max-width: 680px) calc(100vw - 36px), (max-width: 1300px) 30vw, 390px" />
              <small>
                Nível {l.level} · {l.subject}
              </small>
              <h3>{l.title}</h3>
            </a>
          ))}
        </div>
      </section>
      <section className="research-band">
        <div className="wrap research-grid">
          <div>
            <p className="kicker">A escola e a pesquisa</p>
            <h2>Método de investigação</h2>
            <p>
              Em cada aula, você constrói uma relação matemática, testa um exemplo e compara a previsão
              com o resultado. As aulas avançadas levam esse método ao acervo público do NEXO Research.
            </p>
            <a className="text-link" href={NEXO}>
              Conhecer o NEXO Research ↗
            </a>
          </div>
          <MotionBand />
        </div>
      </section>
    </>
  );
}
