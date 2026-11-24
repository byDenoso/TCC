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
      <Meta title="Explore o Universo. Entenda suas leis." />
      <section className="hero">
        <HeroSky />
        <div className="wrap hero-content">
          <div className="hero-text">
            <p className="kicker">
              <i />
              Escola de ciências do Universo
            </p>
            <h1>
              Explore o Universo.
              <br />
              <em>Entenda suas leis.</em>
            </h1>
            <p className="hero-deck">
              Aprenda física, astronomia e cosmologia. Faça uma previsão, mude os parâmetros e veja o que
              o Universo permite.
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
            <h2>Escolha sua trilha.</h2>
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
              <h2>Da órbita à teia cósmica.</h2>
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
                  <img src={'/atlas/mini-' + id + '.webp'} alt="" width="620" height="380" loading="lazy" decoding="async" />
                  <div>
                    <h3>{station.short}</h3>
                    <p>{media.invitation}</p>
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
            <h2>Aulas em destaque.</h2>
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
            <h2>Da pergunta ao teste.</h2>
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
