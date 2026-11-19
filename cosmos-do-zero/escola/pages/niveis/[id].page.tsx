import { Lead, Meta } from '../../src/components/Frame';
import { LessonList } from '../../src/components/Catalog';
import { usePublished } from '../../src/lib/student';
import { cards } from '../../src/lib/content';
import { levels, type Card } from '../../src/lib/school';
export function getStaticPaths() {
  return { paths: levels.map((_, i) => ({ params: { id: String(i + 1) } })), fallback: false };
}
export function getStaticProps({ params }: { params: { id: string } }) {
  return { props: { id: +params.id, all: cards().filter((l) => l.level === +params.id) } };
}
export default function Level({ id, all }: { id: number; all: Card[] }) {
  const level = levels[id - 1];
  const editorial = usePublished().filter((e) => e.payload.level === id);
  return (
    <>
      <Meta title={level.name} />
      <Lead tag={'Trilhas / Nível ' + id} title={level.name} text={level.blurb}>
        <div className="row-actions">
          <a className="btn light" href={'/aulas/' + all[0].slug + '/'}>
            Começar este nível
          </a>
          <a className="btn ghost" href={'/avaliacao/' + id + '/?modo=diagnostico'}>
            Fazer diagnóstico
          </a>
        </div>
      </Lead>
      <div className="wrap reading block">
        <h2>Disciplinas e sequência</h2>
        {level.subjects.map((s) => (
          <section className="module" key={s}>
            <h3>{s}</h3>
            <LessonList items={all.filter((l) => l.subject === s)} />
          </section>
        ))}
        {editorial.length > 0 && (
          <section className="module">
            <h3>Publicações da escola</h3>
            <ul>
              {editorial.map((e) => (
                <li key={e.key}>
                  {e.payload.type} ·{' '}
                  <a href={'/leitura/?id=' + encodeURIComponent(e.key)}>{e.payload.title}</a> ·{' '}
                  {e.payload.subject}
                </li>
              ))}
            </ul>
          </section>
        )}
        <a className="btn dark" href={'/avaliacao/' + id + '/'}>
          Avaliação do nível
        </a>
      </div>
    </>
  );
}
