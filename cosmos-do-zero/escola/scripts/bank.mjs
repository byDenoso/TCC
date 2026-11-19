import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
const lessons = readdirSync('content')
  .filter((x) => x.endsWith('.mdx'))
  .map((name) =>
    JSON.parse(
      readFileSync('content/' + name, 'utf8')
        .replace(/\r/g, '')
        .split('\n---\n')[0]
        .slice(3)
    )
  );
const bank = Object.fromEntries(
  lessons.map((l) => [l.slug, { level: l.level, order: l.order, exercise: l.exercise }])
);
writeFileSync('src/server/answer-bank.json', JSON.stringify(bank) + '\n');

const { labs, simulate } = await import('../src/lib/model.ts');
const bench = Object.fromEntries(
  labs.map((l) => {
    const p =
      l.presets.find((p) => p.values.some((v, i) => v !== l.parameters[i].initial)) ?? l.presets[1];
    return [l.id, { values: p.values, metric: simulate(l.id, p.values, 0).metric.value }];
  })
);
writeFileSync('src/server/lab-bank.json', JSON.stringify(bench) + '\n');
const origin = 'https://cosmos.denerpereira.com.br';
const paths = [
  '/',
  '/trilhas/',
  '/laboratorios/',
  '/explorador/',
  '/fontes/',
  ...Array.from({ length: 6 }, (_, i) => '/niveis/' + (i + 1) + '/'),
  ...Object.keys(bank).map((s) => '/aulas/' + s + '/'),
  ...[
    'orbitas',
    'gravitacao',
    'n-corpos',
    'ondas',
    'campos',
    'relatividade',
    'curvatura',
    'lentes',
    'buracos-negros',
    'expansao',
    'estruturas',
    'rotacao',
    'fator-de-escala',
    'energia-escura',
    'cmb',
  ].map((s) => '/laboratorios/' + s + '/'),
];
writeFileSync(
  'public/sitemap.xml',
  '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
    paths.map((p) => '<url><loc>' + origin + p + '</loc></url>').join('') +
    '</urlset>'
);
