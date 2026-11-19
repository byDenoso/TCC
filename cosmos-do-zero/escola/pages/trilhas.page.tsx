import { Lead, Meta } from '../src/components/Frame';
import { LevelCard, LibrarySearch } from '../src/components/Catalog';
import { cards } from '../src/lib/content';
import { levels, type Card } from '../src/lib/school';
export function getStaticProps() {
  return { props: { all: cards() } };
}
export default function Trails({ all }: { all: Card[] }) {
  return (
    <>
      <Meta title="Trilhas de aprendizagem" />
      <Lead
        tag="Escola Cosmos"
        title="Trilhas de aprendizagem"
        text="Comece em Fundamentos ou escolha o nível que corresponde à sua experiência. Cada disciplina avança do conceito à aplicação."
      />
      <section className="wrap block">
        <div className="level-grid">
          {levels.map((l, i) => (
            <LevelCard key={l.name} i={i} />
          ))}
        </div>
      </section>
      <LibrarySearch all={all} />
    </>
  );
}
