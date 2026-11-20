import { Lead, Meta } from '../../src/components/Frame';
import { labs } from '../../src/lib/model';
const groups = [
  ['Mecânica e campos', 0, 5],
  ['Relatividade e gravitação', 5, 9],
  ['Cosmologia', 9, 15],
] as const;
export default function LabList() {
  return (
    <>
      <Meta title="Laboratórios científicos" />
      <Lead
        tag="Experimentação"
        title="Laboratórios científicos"
        text="Escolha uma bancada, altere os parâmetros e fixe uma referência para comparar os resultados. Todas incluem uma representação 2D e uma cena tridimensional."
      >
        <a className="btn light" href="/laboratorios/expansao/">
          Começar pela expansão cosmológica
        </a>
      </Lead>
      <div className="wrap block">
        {groups.map(([name, a, b]) => (
          <section key={name} className="lab-group">
            <h2>{name}</h2>
            <div className="index-grid">
              {labs.slice(a, b).map((m) => (
                <a className="index-card" key={m.id} href={'/laboratorios/' + m.id + '/'}>
                  <h3>{m.title}</h3>
                  <p>{m.description}</p>
                  <span>Abrir bancada</span>
                </a>
              ))}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}
