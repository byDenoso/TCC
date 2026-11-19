import fs from 'node:fs';
import path from 'node:path';
import { evaluate } from '@mdx-js/mdx';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import * as runtime from 'react/jsx-runtime';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { rank, type Lesson, type Card } from './school';
let loaded: { meta: Lesson; body: string }[] | undefined;
export function curriculum() {
  if (loaded) return loaded;
  const root = path.join(process.cwd(), 'content');
  loaded = fs
    .readdirSync(root)
    .filter((x) => x.endsWith('.mdx'))
    .map((file) => {
      const source = fs.readFileSync(path.join(root, file), 'utf8').replace(/\r/g, '');
      const parts = /^---\s*\n([\s\S]+?)\n---\s*\n([\s\S]+)$/.exec(source);
      if (!parts) throw Error('MDX inválido: ' + file);
      return { meta: JSON.parse(parts[1]) as Lesson, body: parts[2] };
    })
    .sort((a, b) => rank(a.meta) - rank(b.meta));
  return loaded;
}
export function cards(): Card[] {
  return curriculum().map(({ meta: m }) => ({
    slug: m.slug,
    title: m.title,
    level: m.level,
    subject: m.subject,
    order: m.order,
    objective: m.objective,
  }));
}
export async function renderBody(body: string) {
  const mod = await evaluate(body, {
    ...runtime,
    remarkPlugins: [remarkMath],
    rehypePlugins: [[rehypeKatex, { throwOnError: true, strict: 'ignore', trust: false }]],
    development: false,
  });
  return renderToStaticMarkup(createElement(mod.default));
}
