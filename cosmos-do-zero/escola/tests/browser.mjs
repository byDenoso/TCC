import assert from 'node:assert/strict';
import { mkdir, readFile } from 'node:fs/promises';
import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const base = (process.env.BASE_URL || 'http://127.0.0.1:4173').replace(/\/$/, '');
const extraArgs = process.env.COSMOS_BROWSER_ARGS
  ? JSON.parse(await readFile(process.env.COSMOS_BROWSER_ARGS, 'utf8'))
  : [];
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_EXECUTABLE || undefined,
  args: [
    ...extraArgs,
    '--no-zygote',
    '--disable-dev-shm-usage',
    '--use-gl=angle',
    '--use-angle=swiftshader',
    '--enable-unsafe-swiftshader',
  ],
});
const bank = JSON.parse(await readFile('src/server/answer-bank.json', 'utf8'));
const labBank = JSON.parse(await readFile('src/server/lab-bank.json', 'utf8'));
const artifacts = 'test-results';
await mkdir(artifacts, { recursive: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  reducedMotion: 'reduce',
});
const p = await context.newPage();
const errors = [];
p.on('pageerror', (e) => errors.push(e.message));
async function page(path) {
  let r = await p.goto(base + path, { waitUntil: 'domcontentloaded' });
  assert.equal(r?.status(), 200, path);
  await p.waitForFunction(() => document.documentElement.dataset.ready === 'true');
  assert((await p.locator('main h1').count()) > 0, path);
}
async function setRange(el, value) {
  await el.evaluate((input, value) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }, String(value));
}
const checks = [];
try {
  await page('/');
  assert.match(await p.title(), /Explore o Universo/);
  await p
    .locator('main img')
    .first()
    .evaluate((i) => i.decode());
  await p.screenshot({ path: artifacts + '/inicio-desktop.png' });
  await p.getByRole('link', { name: 'Começar a aprender', exact: true }).click();
  await p.waitForURL('**/aulas/**');
  const slug = new URL(p.url()).pathname.split('/')[2];
  assert((await p.locator('.katex').count()) > 0);
  checks.push('Início, primeira aula e KaTeX');
  await p.getByRole('button', { name: 'Favoritar' }).click();
  await p.getByText('Minhas anotações', { exact: true }).click();
  await p
    .getByRole('textbox', { name: 'Anotação sobre a aula' })
    .fill('A luz fornece uma régua de tempo.');
  await p.getByRole('button', { name: 'Salvar anotação' }).click();
  await p.locator('.answer-label input').fill(String(bank[slug].exercise.answer));
  await p.getByRole('button', { name: 'Verificar resposta' }).click();
  await p.getByRole('status').filter({ hasText: 'Resposta correta' }).waitFor();
  await page('/painel/');
  await p.getByText(/1 de 82 aulas com exercício resolvido/).waitFor();
  await p.getByRole('button', { name: 'Favoritos', exact: true }).click();
  assert((await p.locator('.activity a').count()) === 1);
  await p.getByRole('button', { name: 'Anotações', exact: true }).click();
  assert.match(await p.locator('.activity').innerText(), /régua de tempo/);
  await p.reload();
  await p.getByText(/1 de 82 aulas com exercício resolvido/).waitFor();
  checks.push('Resposta, favorito, nota e progresso após recarga');
  await page('/avaliacao/1/');
  const items = Object.entries(bank).filter(([, v]) => v.level === 1 && v.order === 2);
  const groups = p.locator('.exam-question');
  for (let i = 0; i < (await groups.count()); i++) {
    const g = groups.nth(i),
      legend = await g.locator('legend').innerText();
    const entry = items.find(([, v]) => legend.includes(v.exercise.prompt));
    assert(entry, 'Questão encontrada no módulo');
    const q = entry[1].exercise;
    if (q.kind === 'choice') await g.getByRole('radio').nth(q.answer).check();
    else await g.getByRole('textbox').fill(String(q.answer));
  }
  await p.getByRole('button', { name: 'Corrigir avaliação' }).click();
  await p.getByText(/5 de 5 respostas corretas/).waitFor();
  checks.push('Avaliação de módulo e nota 5/5');
  await page('/trilhas/');
  await p.getByRole('searchbox').fill('quântica');
  await p.getByText(/2 aulas no currículo/).waitFor();
  await page('/laboratorios/');
  const links = await p.locator('.index-card').evaluateAll((els) => els.map((a) => a.pathname));
  assert.equal(links.length, 15);
  for (const href of links) {
    await page(href);
    const lab = p.locator('.laboratory');
    const select = lab.getByRole('combobox');
    await lab.getByRole('button', { name: 'Fixar referência' }).click();
    await select.selectOption('1');
    await lab.locator('.baseline').waitFor({ state: 'attached' });
    assert.equal(
      await lab
        .locator('.baseline')
        .evaluate((path) => getComputedStyle(path).strokeDasharray !== 'none'),
      true
    );
    await lab.getByRole('button', { name: 'Reiniciar' }).click();
    assert.equal(await lab.locator('.baseline').count(), 0);
    assert(await lab.locator('.plotline').getAttribute('d'));
    assert(!/NaN|Infinity/.test(await lab.locator('.metric').innerText()));
    const labId = href.split('/').filter(Boolean).at(-1),
      target = labBank[labId];
    const controls = lab.locator('.controls input[type=range]');
    for (let j = 0; j < target.values.length; j++) await setRange(controls.nth(j), target.values[j]);
    await lab.getByRole('button', { name: 'Medir em t = 0' }).click();
    await lab.locator('.challenge input').fill(String(target.metric));
    await lab.getByRole('button', { name: 'Registrar medida' }).click();
    await lab.getByText('Medida reproduzida. Experimento registrado.', { exact: true }).waitFor();
    await lab.getByRole('button', { name: 'Abrir 3D' }).click();
    await lab.locator('canvas').waitFor({ timeout: 15000 });
    await p.waitForTimeout(250);
    assert(await lab.locator('canvas').evaluate((c) => c.width > 0 && c.height > 0));
    await lab.getByRole('button', { name: 'Usar 2D' }).click();
  }
  checks.push('15 bancadas com presets, referência, reinicialização, curva D3 e canvas 3D');
  await p.setViewportSize({ width: 390, height: 844 });
  await page('/');
  await p.screenshot({ path: artifacts + '/inicio-celular.png' });
  await p.getByRole('button', { name: 'Abrir menu' }).click();
  await p.locator('#mobile-menu a').first().click();
  assert.match(p.url(), /trilhas/);
  const audits = [];
  for (const path of [
    '/',
    '/trilhas/',
    '/aulas/' + slug + '/',
    '/laboratorios/orbitas/',
    '/painel/',
    '/explorador/',
  ]) {
    await page(path);
    assert(
      await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
      'Largura móvel ' + path
    );
    const scan = await new AxeBuilder({ page: p }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    const issues = scan.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
    audits.push([path, issues.map((v) => [v.id, v.nodes.map((n) => n.target).slice(0, 4)])]);
  }
  console.log('Auditoria a11y', JSON.stringify(audits));
  assert(
    audits.every((x) => x[1].length === 0),
    'Violações sérias de acessibilidade'
  );
  checks.push('Navegação móvel, 6 páginas sem overflow e auditoria axe');
  await p.addInitScript(() => {
    const get = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, ...args) {
      if (type.startsWith('webgl')) return null;
      return get.call(this, type, ...args);
    };
    Object.defineProperty(navigator, 'gpu', { value: undefined, configurable: true });
  });
  await page('/laboratorios/orbitas/');
  await p.getByRole('button', { name: 'Abrir 3D' }).click();
  await p.locator('.lab-svg').waitFor();
  await p.getByRole('button', { name: 'Animar' }).click();
  await p.waitForTimeout(350);
  await p.getByRole('button', { name: 'Pausar' }).click();
  checks.push('Laboratório em navegador sem WebGL');
  assert.deepEqual(errors, []);
  console.log(checks.join('\n'));
} finally {
  await browser.close();
}
