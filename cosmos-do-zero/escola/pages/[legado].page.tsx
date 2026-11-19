import Redirect from '../src/components/Redirect';
import { oldPages } from '../src/lib/legacy';
export function getStaticPaths() {
  return { paths: Object.keys(oldPages).map((legado) => ({ params: { legado } })), fallback: false };
}
export function getStaticProps({ params }: { params: { legado: string } }) {
  return { props: { to: oldPages[params.legado] } };
}
export default Redirect;
