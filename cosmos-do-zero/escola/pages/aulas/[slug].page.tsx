import { Meta } from '../../src/components/Frame';
import { Exercise, StudyTools, PublishedNote } from '../../src/components/Study';
import { Plot } from '../../src/components/Plot';
import { curriculum, renderBody } from '../../src/lib/content';
import { levels, type Lesson } from '../../src/lib/school';
import { labs } from '../../src/lib/model';
import { LessonScene } from '../../src/components/LessonScene';
export function getStaticPaths() {
  return { paths: curriculum().map(({ meta }) => ({ params: { slug: meta.slug } })), fallback: false };
}
export async function getStaticProps({ params }: { params: { slug: string } }) {
  const all = curriculum(),
    i = all.findIndex((v) => v.meta.slug === params.slug),
    v = all[i];
  const ref = (j: number) => (all[j] ? { slug: all[j].meta.slug, title: all[j].meta.title } : null);
  return {
    props: { lesson: v.meta, html: await renderBody(v.body), prev: ref(i - 1), next: ref(i + 1) },
  };
}
type Ref = { slug: string; title: string } | null;
export default function Article({
  lesson: l,
  html,
  prev,
  next,
}: {
  lesson: Lesson;
  html: string;
  prev: Ref;
  next: Ref;
}) {
  const lab = labs.find((b) => b.id === l.lab)!;
  return (
    <>
      <Meta title={l.title} desc={l.objective} />
      <div className="wrap article-layout">
        <article className="lesson">
          <header>
            <p className="kicker">
              <a href="/trilhas/">Trilhas</a> /{' '}
              <a href={'/niveis/' + l.level + '/'}>{levels[l.level - 1].name}</a>
            </p>
            <span className="subject">
              {l.subject} · Aula {l.order}
            </span>
            <h1>{l.title}</h1>
            <p className="deck">{l.objective}</p>
          </header>
          <LessonScene labId={l.lab} />
          <StudyTools slug={l.slug} />
          <section id="conceito" className="prose" dangerouslySetInnerHTML={{ __html: html }} />
          <section id="grafico">
            <p className="kicker">Explore a relação</p>
            <h2>Leia o gráfico</h2>
            <Plot
              points={l.graph.points}
              {...{ xLabel: l.graph.xLabel, yLabel: l.graph.yLabel, caption: l.graph.caption }}
            />
          </section>
          <section className="related">
            <div>
              <p className="kicker">Experimento relacionado</p>
              <h3>{lab.title}</h3>
              <p>{lab.description}</p>
            </div>
            <a className="btn dark" href={'/laboratorios/' + l.lab + '/'}>
              Abrir laboratório
            </a>
          </section>
          <Exercise lesson={l} />
          <section id="resumo">
            <h2>Para guardar</h2>
            <p>{l.summary}</p>
            <h3>Referência</h3>
            <a href={l.reference.url}>{l.reference.name} ↗</a>
            {l.level === 6 && (
              <p>
                <a href="https://nexoresearch.org/pt/results/t-05ae703af393">
                  Estudo de caso do NEXO · sensibilidade de um ajuste à seleção de redshift ↗
                </a>
              </p>
            )}
          </section>
          <PublishedNote slug={l.slug} />
          <nav className="lesson-next" aria-label="Sequência didática">
            <div>
              <small>Pré-requisito recomendado</small>
              {prev ? (
                <a href={'/aulas/' + prev.slug + '/'}>{prev.title}</a>
              ) : (
                <p>Operações aritméticas básicas. Esta é a primeira aula.</p>
              )}
            </div>
            <div>
              <small>{next ? 'Próxima aula' : 'Encerramento'}</small>
              <a href={next ? '/aulas/' + next.slug + '/' : '/avaliacao/6/'}>
                {next ? next.title : 'Avaliação de Cosmologia Avançada'}
              </a>
            </div>
          </nav>
        </article>
        <aside className="lesson-aside">
          <p className="kicker">Nesta aula</p>
          {[
            ['visual', 'Cena 3D'],
            ['conceito', 'Conceito e cálculo'],
            ['grafico', 'Gráfico interativo'],
            ['exercicio', 'Exercício'],
            ['resumo', 'Resumo e fontes'],
          ].map(([id, t]) => (
            <a href={'#' + id} key={id}>
              {t}
            </a>
          ))}
          <a href={'/niveis/' + l.level + '/'}>Ver a trilha completa</a>
        </aside>
      </div>
    </>
  );
}
