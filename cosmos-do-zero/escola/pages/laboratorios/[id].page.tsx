import { Lead, Meta } from '../../src/components/Frame';
import { LabView } from '../../src/components/Laboratory';
import { labs } from '../../src/lib/model';
import { cards } from '../../src/lib/content';
import { curriculum } from '../../src/lib/content';
import { LessonList } from '../../src/components/Catalog';
import type { Card } from '../../src/lib/school';
export function getStaticPaths() {
  return { paths: labs.map((l) => ({ params: { id: l.id } })), fallback: false };
}
export function getStaticProps({ params }: { params: { id: string } }) {
  const ids = new Set(
    curriculum()
      .filter((x) => x.meta.lab === params.id)
      .map((x) => x.meta.slug)
  );
  return { props: { id: params.id, lessons: cards().filter((c) => ids.has(c.slug)) } };
}
export default function Lab({ id, lessons }: { id: string; lessons: Card[] }) {
  const l = labs.find((p) => p.id === id)!;
  return (
    <>
      <Meta title={l.title} />
      <Lead tag="Laboratório / Simulação didática" title={l.title} text={l.description} />
      <section className={id === 'expansao' ? 'wrap block expansion-block' : 'wrap block'}>
        <LabView key={id} id={id} />
        {lessons.length > 0 && (
          <section className="block">
            <h2>Aulas relacionadas</h2>
            <LessonList items={lessons} />
          </section>
        )}
        <a className="text-link" href="/laboratorios/">
          Todos os laboratórios
        </a>
      </section>
    </>
  );
}
