import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const read = path => readFile(new URL(`../${path}`, import.meta.url), 'utf8');
const [chapterSource, exhibits, engine] = await Promise.all([
  read('src/data/chapters.json'), read('src/scripts/visual/exhibits.ts'), read('src/scripts/micro/engine.ts')
]);
const chapters = JSON.parse(chapterSource);
const micro3d = new Set([...exhibits.matchAll(/^\s*'([^']+)':\s*\{\s*make\s*:/gm)].map(match => match[1]));
const spatialDeclaration = engine.match(/const spatial = new Set\(\[([^\]]+)\]\)/);
if (!spatialDeclaration) throw new Error('Missing visible 3D micro-scene inventory');
const visibleMicro3d = new Set([...spatialDeclaration[1].matchAll(/'([^']+)'/g)].map(match => match[1]));
const chapterRoute = chapter => `/capitulos/${chapter}/`;

export const sceneInventory = [
  ...chapters.flatMap(chapter => chapter.sections.map(section => ({
    id: section.id,
    title: section.title,
    route: chapterRoute(chapter.id),
    anchor: section.id,
    kind: visibleMicro3d.has(section.id) ? '3d' : '2d',
    catalogVariant: micro3d.has(section.id) && !visibleMicro3d.has(section.id),
    activate: visibleMicro3d.has(section.id) ? `[data-mx="${section.id}"] [data-mx-enable-3d]` : undefined,
    stage: `[data-mx="${section.id}"] .mx-volume-stage`
  }))),
  ...chapters.map(chapter => ({
    id: `resumo-${chapter.id}`, title: `Resumo · ${chapter.title}`, route: chapterRoute(chapter.id),
    kind: '3d', story: true, stage: '[data-story-world]'
  })),
  { id: 'saturno-aneis', title: 'Saturno · plano dos anéis', route: chapterRoute('sistema-solar'), anchor: 'saturno-aneis', kind: '3d', native: true },
  { id: 'solar-planetas', title: 'Sistema Solar · planetas', route: chapterRoute('sistema-solar'), anchor: 'sistema-solar-sol-e-planetas', kind: '3d', stage: '[data-solar-stage]' },
  { id: 'endereco-cosmico', title: 'Endereço cósmico', route: chapterRoute('galaxias-e-nebulosas'), kind: '3d', extra: true, stage: '[data-scale-stage]' },
  { id: 'lente-gravitacional', title: 'Lente gravitacional', route: chapterRoute('misterios-do-cosmos'), anchor: 'misterios-do-cosmos-materia-escura', also: ['/laboratorio/#lente-gravitacional'], kind: '3d', activate: '[data-lens-geometry] > summary', stage: '[data-lens-stage]' },
  { id: 'tempo-flrw', title: 'Tempo e distância da luz', route: '/observatorio/', also: ['/capitulos/galaxias-e-nebulosas/#observatorio'], kind: '3d', stage: '[data-t-3d]' },
  { id: 'expansao-observatorio', title: 'Expansão · observatório', route: '/observatorio/', also: ['/capitulos/origem-do-universo/#exploracao'], kind: '3d', activate: '[data-obs-tab="expansao"]', stage: '[data-e-volume]' },
  { id: 'catalogo-planetas', title: 'Catálogo de planetas', route: '/laboratorio/', anchor: 'planetas', kind: '3d', stage: '[data-planet-stage]' },
  { id: 'comparador-planetas', title: 'Comparador de planetas', route: '/laboratorio/', anchor: 'comparador', kind: '3d', stage: '[data-compare-visual]' },
  { id: 'massa-estelar', title: 'Evolução por massa estelar', route: '/laboratorio/', anchor: 'estrelas', kind: '3d', stage: '[data-island="stars"] .mx-stage' },
  { id: 'escala-continua', title: 'Escala contínua', route: '/escalas/', kind: '3d', stage: '[data-scale-canvas]' },
  { id: 'nebulosa-ceu', title: 'Nebulosa', route: '/ceu/', kind: '3d', activate: '[data-hero-gl-enable]', native: true },
  { id: 'mapa-cmb', title: 'Mapa da radiação cósmica de fundo', route: '/ceu/', kind: '2d', stage: '[data-cmb-frame]' },
  { id: 'luz-espectro', title: 'Espectro e luz', route: '/luz/', kind: '2d', stage: '[data-light-exhibit]' },
  { id: 'ciencia-em-movimento', title: 'Ciência em movimento', route: '/', kind: '2d', stage: '[data-sci-lab]' },
  { id: 'jornada-home', title: 'Jornada cósmica', route: '/', kind: '2d', stage: '[data-journey]' },
  { id: 'explorar', title: 'Explorar', route: '/explorar/', kind: '2d' },
  { id: 'imagens', title: 'Explorador de imagens', route: '/imagens/', kind: '2d', stage: '[data-px]' },
  { id: 'laboratorio-orbitas', title: 'Órbitas', route: '/laboratorio/', also: ['/capitulos/sistema-solar/#sistema-solar-sol-e-planetas'], kind: '2d', stage: '[data-orbit-exhibit]' },
  { id: 'laboratorio-expansao', title: 'Expansão', route: '/laboratorio/', also: ['/capitulos/origem-do-universo/#origem-do-universo-expansao'], kind: '2d', stage: '[data-expansion-exhibit]' },
  { id: 'laboratorio-transito', title: 'Trânsito', route: '/laboratorio/', also: ['/capitulos/misterios-do-cosmos/#misterios-do-cosmos-exoplanetas'], kind: '2d', stage: '[data-transit-exhibit]' },
  { id: 'laboratorio-hr', title: 'Diagrama HR', route: '/laboratorio/', also: ['/capitulos/vida-das-estrelas/#vida-das-estrelas-fusao'], kind: '2d', stage: '[data-hr-exhibit]' },
  { id: 'observatorio-hubble', title: 'Diagrama de Hubble', route: '/observatorio/', also: ['/capitulos/misterios-do-cosmos/#observatorio'], kind: '2d', activate: '[data-obs-tab="hubble"]' },
  { id: 'observatorio-receita', title: 'Receita do Universo', route: '/observatorio/', also: ['/capitulos/origem-do-universo/#exploracao', '/capitulos/misterios-do-cosmos/#observatorio'], kind: '2d', activate: '[data-obs-tab="receita"]' },
  { id: 'hubble-guiado', title: 'Medindo o afastamento', route: chapterRoute('origem-do-universo'), anchor: 'origem-do-universo-expansao', kind: '2d' },
  { id: 'buracos-negros', title: 'Como vemos um buraco negro', route: chapterRoute('galaxias-e-nebulosas'), anchor: 'galaxias-e-nebulosas-centros-galacticos', kind: '2d', stage: '#buracos-negros' },
  { id: 'evidencias-do-cosmos', title: 'Evidências do Universo invisível', route: chapterRoute('misterios-do-cosmos'), anchor: 'exploracao', kind: '2d', stage: '[data-scene="evidence"]' }
];

if (!sceneInventory.length || [...visibleMicro3d].some(id => !micro3d.has(id))) {
  throw new Error('A reachable micro scene is missing from the 3D catalog');
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  console.log(JSON.stringify(sceneInventory, null, 2));
}
