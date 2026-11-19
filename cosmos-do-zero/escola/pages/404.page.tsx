import { Meta, Lead } from '../src/components/Frame';
export default function NotFound() {
  return (
    <>
      <Meta title="Página não encontrada" />
      <Lead
        tag="Cosmos / 404"
        title="Esta página saiu de órbita."
        text="Encontre a aula ou a experiência pelo catálogo."
      >
        <a className="btn light" href="/trilhas/">
          Consultar as trilhas
        </a>
      </Lead>
    </>
  );
}
