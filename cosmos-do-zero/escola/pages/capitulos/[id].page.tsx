import Redirect from '../../src/components/Redirect';
import { chapters } from '../../src/lib/legacy';
export function getStaticPaths() {
  return { paths: Object.keys(chapters).map((id) => ({ params: { id } })), fallback: false };
}
export function getStaticProps({ params }: { params: { id: string } }) {
  return { props: { to: '/aulas/' + chapters[params.id] + '/' } };
}
export default Redirect;
