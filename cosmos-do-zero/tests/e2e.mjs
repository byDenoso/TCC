// E2E (Playwright/Chromium) contra o build servido em BASE_URL (padrão http://localhost:4321).
// Uso: npm run build && npm run preview &  →  npm run test:e2e   (SHOTS=1 salva capturas em docs/screenshots)
import { chromium } from 'playwright';
import { mkdirSync, existsSync } from 'node:fs';

const BASE = (process.env.BASE_URL ?? 'http://localhost:4321').replace(/\/$/, '');
const SHOTS = process.env.SHOTS === '1';
const WIDTHS = [360, 390, 768, 1024, 1440];
const PRIMARY = ['galaxias-e-nebulosas', 'origem-do-universo', 'misterios-do-cosmos'];
const CHAPTERS = [...PRIMARY, 'vida-das-estrelas', 'sistema-solar', 'terra-e-atmosfera'];
const PLANETS = ['mercurio', 'venus', 'terra', 'marte', 'jupiter', 'saturno', 'urano', 'netuno'];

const exe = ['/opt/pw-browsers/chromium', process.env.CHROMIUM].find((p) => p && existsSync(p));
const browser = await chromium.launch(exe ? { executablePath: exe } : {});
let pass = 0; const fails = [];
const ok = (name, cond, extra = '') => { if (cond) pass++; else { fails.push(`${name} ${extra}`); console.log('  ✗', name, extra); } };
const section = (t) => console.log('\n' + t);

async function page(width = 1280, opts = {}) {
  const ctx = await browser.newContext({ viewport: { width, height: width < 700 ? 800 : 900 }, ...opts });
  const p = await ctx.newPage();
  p.errors = [];
  p.on('pageerror', (e) => p.errors.push(String(e)));
  p.on('console', (m) => m.type() === 'error' && p.errors.push(m.text()));
  p.on('requestfailed', (r) => p.errors.push('requestfailed ' + r.url()));
  return p;
}
const overflow = (p) => p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

// 1 — larguras, rolagem horizontal, erros de console, todas as páginas
section('Larguras × páginas');
for (const w of WIDTHS) {
  const p = await page(w);
  for (const path of ['/', ...CHAPTERS.map((c) => `/capitulos/${c}/`), '/404.html']) {
    await p.goto(BASE + path, { waitUntil: 'networkidle' });
    ok(`sem rolagem horizontal ${w}px ${path}`, (await overflow(p)) <= 0, `(+${await overflow(p)}px)`);
    ok(`sem erros ${w}px ${path}`, p.errors.length === 0, p.errors.join(' | '));
    if (SHOTS && (path === '/' || PRIMARY.some(id => path.includes(id)) || path.includes('sistema-solar'))) {
      mkdirSync('docs/screenshots', { recursive: true });
      await p.screenshot({ path: `docs/screenshots/${path === '/' ? 'home' : path.split('/')[2]}-${w}.png`, fullPage: true });
    }
  }
  await p.context().close();
}

// 2 — menu móvel
section('Menu móvel');
{
  const p = await page(390);
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  const menu = p.locator('[data-mobile-menu]');
  await menu.locator('summary').click();
  ok('menu abre', await menu.evaluate((d) => d.open));
  await p.keyboard.press('Escape');
  ok('Esc fecha o menu', !(await menu.evaluate((d) => d.open)));
  await menu.locator('summary').click();
  await menu.locator('nav a').nth(2).click();
  ok('link fecha o menu', !(await menu.evaluate((d) => d.open)));
  await p.context().close();
}

// 3 — jornadas, leitor, níveis, índice, progresso
section('Leitor e progresso');
{
  const p = await page(1280);
  await p.goto(BASE + '/capitulos/sistema-solar/');
  const depth = (k) => p.locator(`button[data-depth="${k}"]`);
  ok('nível essencial ativo por padrão', (await depth('essential').getAttribute('aria-pressed')) === 'true');
  await depth('more').click();
  ok('URL guarda ?nivel=entender', p.url().includes('nivel=entender'));
  await depth('deep').click();
  ok('URL guarda ?nivel=profundo', p.url().includes('nivel=profundo'));
  await p.reload();
  ok('nível persiste ao recarregar', (await depth('deep').getAttribute('aria-pressed')) === 'true');
  const tocLinks = p.locator('[data-toc] a');
  ok('índice com 6 seções', (await tocLinks.count()) === 6);
  await tocLinks.nth(3).click();
  ok('índice navega para a âncora', p.url().includes('#'));
  await p.goBack();
  ok('voltar não sai do capítulo', p.url().includes('/capitulos/sistema-solar/'));

  // Complementary progress is retained but does not advance the core journey.
  await p.locator('[data-complete]').click();
  await p.goto(BASE + '/');
  ok('extra não avança as três jornadas', /0 de 3/.test(await p.locator('[data-progress-label]').first().innerText()));
  await p.goto(BASE + '/capitulos/galaxias-e-nebulosas/');
  // concluir jornada principal → progresso na home
  await p.locator('[data-complete]').click();
  ok('capítulo marcado como concluído', (await p.locator('[data-complete]').getAttribute('aria-pressed')) === 'true');
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  ok('CTA retoma a segunda jornada', /origem-do-universo/.test(await p.locator('[data-start-journey]').getAttribute('href')));
  const label = await p.locator('[data-progress-label]').first().innerText();
  ok('home reflete 1 de 3', /1 de 3/.test(label), label);
  await p.reload();
  ok('progresso persiste', /1 de 3/.test(await p.locator('[data-progress-label]').first().innerText()));
  await p.locator('[data-reset-progress]').click();
  ok('reiniciar volta a 0', /0 de 3/.test(await p.locator('[data-progress-label]').first().innerText()));
  await p.context().close();
}

section('Progresso sem localStorage');
{
  const p = await page(1280);
  await p.addInitScript(() => {
    const deny = () => { throw new DOMException('blocked', 'SecurityError'); };
    Object.defineProperty(window, 'localStorage', { get: deny });
  });
  await p.goto(BASE + '/capitulos/origem-do-universo/');
  await p.locator('[data-complete]').click();
  ok('conclui sem storage (memória)', (await p.locator('[data-complete]').getAttribute('aria-pressed')) === 'true');
  ok('sem erros sem storage', p.errors.length === 0, p.errors.join(' | '));
  await p.locator('button[data-depth="more"]').click();
  ok('níveis funcionam sem storage', (await p.locator('button[data-depth="more"]').getAttribute('aria-pressed')) === 'true');
  await p.context().close();
}

// 4 — linha do tempo
section('Linha do tempo');
{
  const p = await page(1280);
  await p.goto(BASE + '/#tempo', { waitUntil: 'networkidle' });
  const n = await p.locator('[data-era-index]').count();
  ok('10 marcos', n === 10, String(n));
  await p.locator('[data-era-index="2"]').click();
  ok('CMB com render artístico e sem mapa observado', /ancient-light\.webp$/.test(await p.locator('[data-era-render]').getAttribute('src')) && /não é mapa CMB/i.test(await p.locator('[data-era-render-note]').innerText()));
  await p.locator('[data-era-index="0"]').click();
  const t0 = await p.locator('[data-era-title]').innerText();
  await p.locator('[data-era-index="4"]').click();
  ok('marco atualiza imagem renderizada', /galaxies\.webp$/.test(await p.locator('[data-era-render]').getAttribute('src')));
  ok('marco muda o título', (await p.locator('[data-era-title]').innerText()) !== t0);
  ok('?marco= na URL', /marco=/.test(p.url()));
  await p.locator('[data-era-index="4"]').focus();
  await p.keyboard.press('End');
  ok('End vai ao último', (await p.locator('[data-era-index="9"]').getAttribute('aria-pressed')) === 'true');
  await p.keyboard.press('Home');
  ok('Home vai ao primeiro', (await p.locator('[data-era-index="0"]').getAttribute('aria-pressed')) === 'true');
  await p.context().close();
}

// 5 — planetas
section('Planetas');
{
  const p = await page(1280);
  await p.goto(BASE + '/#planetas', { waitUntil: 'networkidle' });
  const seen = new Set();
  for (const id of PLANETS) {
    await p.locator(`button[data-planet="${id}"]`).click();
    await p.waitForTimeout(80);
    const name = await p.locator('[data-planet-name]').innerText();
    seen.add(name);
    ok(`planeta ${id} ativo`, (await p.locator(`button[data-planet="${id}"]`).getAttribute('aria-pressed')) === 'true');
    ok(`planeta ${id} URL`, p.url().includes(`planeta=${id}`) || id === 'terra');
    const img = await p.locator('[data-planet-img]').first().evaluate((i) => i.complete && i.naturalWidth > 0);
    ok(`planeta ${id} imagem carrega`, img);
  }
  ok('8 nomes distintos', seen.size === 8, [...seen].join(','));
  await p.locator('[data-ruler="mercurio"]').click({ force: true });
  ok('régua de tamanhos seleciona', (await p.locator('button[data-planet="mercurio"]').getAttribute('aria-pressed')) === 'true');
  await p.context().close();
}

// 6 — comparador
section('Comparador');
{
  const p = await page(1280);
  await p.goto(BASE + '/#laboratorio', { waitUntil: 'networkidle' });
  const a = p.locator('[data-compare-a]'), b = p.locator('[data-compare-b]');
  ok('padrão Terra × Júpiter', (await a.inputValue()) === 'terra' && (await b.inputValue()) === 'jupiter');
  await p.locator('[data-compare-swap]').click();
  ok('trocar lados', (await a.inputValue()) === 'jupiter' && (await b.inputValue()) === 'terra');
  await a.selectOption('marte'); await b.selectOption('marte');
  const ins = await p.locator('[data-compare-insight]').innerText();
  ok('mesmo planeta → razões 1', /mesmo planeta/i.test(ins), ins);
  await a.selectOption('jupiter'); await b.selectOption('terra');
  const ins2 = await p.locator('[data-compare-insight]').innerText();
  ok('gramática "da Terra"', /vezes o da Terra/.test(ins2), ins2);
  await a.selectOption('venus'); await b.selectOption('mercurio');
  ok('tabela atualiza cabeçalhos', (await p.locator('[data-compare-col="a"]').innerText()).includes('Vênus'));
  ok('?a=&b= na URL', /a=venus/.test(p.url()) && /b=mercurio/.test(p.url()));
  const bad = await page(1280);
  await bad.goto(BASE + '/?a=xx&b=yy');
  ok('IDs inválidos caem no padrão', (await bad.locator('[data-compare-a]').inputValue()) === 'terra');
  await bad.context().close();
  await p.context().close();
}

// 7 — estrelas
section('Evolução estelar');
{
  const p = await page(1280);
  await p.goto(BASE + '/#laboratorio', { waitUntil: 'networkidle' });
  const r = p.locator('[data-star-mass]');
  const setMass = (v) => r.evaluate((el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); }, v);
  const classes = [];
  for (const v of ['0.3', '1', '3', '12', '30']) {
    await setMass(v);
    classes.push(await p.locator('[data-star-class]').innerText());
  }
  ok('classes distintas por faixa de massa', new Set(classes).size >= 3, classes.join(' | '));
  await setMass('1');
  const initialRender=await p.locator('[data-star-render]').getAttribute('src');
  const initialWidth=await p.locator('[data-star-render]').evaluate(e => e.getBoundingClientRect().width);
  await setMass('30');
  ok('massa altera o dado didático', /30/.test(await p.locator('[data-star-value]').innerText()));
  ok('render estelar permanece sem escala quantitativa', await p.locator('[data-star-render]').getAttribute('src') === initialRender && await p.locator('[data-star-render]').evaluate(e => e.getBoundingClientRect().width) === initialWidth && /star\.webp$/.test(initialRender));
  await p.context().close();
}

// 8 — quiz
section('Quiz');
{
  const p = await page(1280);
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  const quiz = p.locator('[data-quiz]');
  let rights = 0;
  for (let i = 0; i < 9; i++) {
    await quiz.locator('[data-answer]').nth(0).click();
    const fb = await quiz.locator('[data-quiz-feedback]').innerText();
    ok(`pergunta ${i + 1} dá feedback`, fb.length > 20);
    if (/correta|certo|acertou/i.test(fb.slice(0, 40))) rights++;
    const next = quiz.locator('[data-quiz-next]');
    if (await next.isVisible()) await next.click();
  }
  ok('resultado exibido ao fim', (await quiz.innerText()).match(/\d+\s*(de|\/)\s*9/) !== null);
  ok('há erros e botão "Refazer só as que errei"', await quiz.locator('[data-quiz-retry-missed]').isVisible());
  await p.getByRole('button', { name: /Refazer|Recome/ }).first().click();
  ok('reinício volta à pergunta 1', /01 \/ /.test(await quiz.locator('[data-quiz-counter]').innerText()));
  await p.locator('[data-quiz-filter]').selectOption('vida-das-estrelas');
  ok('filtro por assunto muda o total', /\/ 0?2\b/.test(await quiz.locator('[data-quiz-counter]').innerText()), await quiz.locator('[data-quiz-counter]').innerText());
  await p.context().close();
}

// 9 — glossário
section('Glossário');
{
  const p = await page(1280);
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  const input = p.locator('[data-glossary-input]');
  const count = () => p.locator('[data-glossary-count]').innerText();
  ok('26 termos de início', /26/.test(await count()), await count());
  await input.fill('fusao');
  const c1 = await count();
  ok('busca sem acento acha "fusão"', !/26/.test(c1) && !/nenhum/i.test(c1), c1);
  await input.fill('FUSÃO');
  ok('busca com acento/caixa', (await count()) === c1);
  await input.fill('zzzzqq');
  ok('estado vazio visível', await p.locator('[data-glossary-empty]').isVisible());
  await p.locator('[data-glossary-clear]').click();
  ok('recuperar lista', /26/.test(await count()) && (await input.inputValue()) === '');
  await p.locator('[data-glossary-chip="sistema-solar"]').click();
  ok('chip filtra por jornada', !/26/.test(await count()), await count());
  await p.context().close();
}

// 10 — imagens, créditos, links
section('Imagens, créditos e links');
{
  const p = await page(1280);
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await p.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 600) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 40)); } });
  ok('hero usa render prioritário', await p.locator('.hero-render').getAttribute('fetchpriority') === 'high' && /hero-eclipse\.webp$/.test(await p.locator('.hero-render').getAttribute('src')));
  ok('previews usam renders raster', await p.locator('.preview-card img.preview-render').count() === 3 && await p.locator('.preview-card svg').count() === 0);
  ok('home sem esferas procedurais', await p.locator('.stellar-orb,.era-orb,.solar-disc,.solar-rim,.eclipse-glow').count() === 0);
  const broken = await p.evaluate(() => [...document.images].filter((i) => i.loading !== 'lazy' || i.getBoundingClientRect().top < innerHeight * 3).filter((i) => i.complete && i.naturalWidth === 0).map((i) => i.src));
  ok('nenhuma imagem quebrada na home', broken.length === 0, broken.join(','));
  const noAlt = await p.evaluate(() => [...document.images].filter((i) => !i.hasAttribute('alt')).length);
  ok('todas as imagens têm atributo alt', noAlt === 0, String(noAlt));
  const ext = await p.locator('#fontes a[href^="http"]').count();
  ok('fontes têm links externos', ext >= 10, String(ext));
  const unsafe = await p.evaluate(() => [...document.querySelectorAll('a[target=_blank]')].filter((a) => !/noopener/.test(a.rel)).length);
  ok('target=_blank com rel=noopener', unsafe === 0);
  // links internos
  const hrefs = await p.evaluate(() => [...new Set([...document.querySelectorAll('a[href^="/"]')].map((a) => a.getAttribute('href').split('#')[0].split('?')[0]))]);
  for (const h of hrefs) { const r = await p.request.get(BASE + h); ok(`link interno ${h}`, r.ok(), String(r.status())); }
  for (const c of CHAPTERS) {
    await p.goto(`${BASE}/capitulos/${c}/`, { waitUntil: 'networkidle' });
    const refs = await p.locator('a[href^="http"]').count();
    ok(`referências em ${c}`, refs >= 3, String(refs));
  }
  await p.context().close();
}

// 11 — movimento reduzido, foco, teclado
section('Acessibilidade');
{
  const p = await page(1280, { reducedMotion: 'reduce' });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  const anim = await p.evaluate(() => [...document.querySelectorAll('*')].filter((e) => { const s = getComputedStyle(e); return s.animationName !== 'none' && parseFloat(s.animationDuration) > 0.05 && s.animationIterationCount === 'infinite'; }).length);
  ok('sem animações infinitas com movimento reduzido', anim === 0, String(anim));
  await p.keyboard.press('Tab');
  const skip = await p.evaluate(() => document.activeElement?.className + '|' + document.activeElement?.textContent);
  ok('primeiro Tab = link de pular', /pular|skip/i.test(skip), skip);
  let focusVisible = 0;
  for (let i = 0; i < 12; i++) { await p.keyboard.press('Tab'); await p.waitForTimeout(350); focusVisible += await p.evaluate(() => { const s = getComputedStyle(document.activeElement); return (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || s.boxShadow !== 'none' ? 1 : 0; }); }
  ok('foco visível nos primeiros 12 elementos', focusVisible >= 11, String(focusVisible));
  await p.context().close();
}

// 12 — JS desligado: conteúdo ainda legível
section('Sem JavaScript');
{
  const p = await page(1280, { javaScriptEnabled: false });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await p.locator('[data-extras] > summary').click();
  const t = await p.innerText('body');
  ok('home legível sem JS (tabela de comparação e percurso estelar)', /Terra/.test(t) && /Júpiter/.test(t) && /Estrela/i.test(t));
  await p.goto(BASE + '/capitulos/sistema-solar/');
  ok('capítulo legível sem JS', (await p.innerText('body')).length > 3000);
  await p.context().close();
}


section('Três jornadas e explorações');
{
  const p = await page(1280);
  await p.goto(BASE + '/');
  const journeys = await p.locator('#capitulos [data-journey]').evaluateAll(nodes => nodes.map(n => n.dataset.journey));
  ok('jornadas na ordem aprovada', JSON.stringify(journeys) === JSON.stringify(PRIMARY));
  ok('exploração complementar recolhida', !(await p.locator('[data-extras]').evaluate(d => d.open)));
  await p.goto(BASE + '/#planetas');
  ok('hash legado abre exploração complementar', await p.locator('[data-extras]').evaluate(d => d.open));
  await p.goto(BASE + '/capitulos/galaxias-e-nebulosas/');
  ok('primeira jornada leva à expansão', /origem-do-universo/.test(await p.locator('.chapter-pagination a').last().getAttribute('href')));
  ok('cinco escalas disponíveis', await p.locator('[data-scale-step]').count() === 5);
  ok('cinco escalas usam imagens raster', await p.locator('img[data-scale-visual]').count() === 5);
  ok('galeria começa com uma única imagem visível', await p.locator('img[data-scale-visual]:visible').count() === 1);
  ok('capítulo sem esfera procedural', await p.locator('.concept-orb,.era-orb,.solar-disc,.solar-rim').count() === 0);
  await p.locator('[data-scale-step="4"]').click();
  ok('galeria alterna mantendo uma única imagem visível', await p.locator('img[data-scale-visual]:visible').count() === 1);
  ok('teia usa imagem renderizada', /cosmic-web\.webp$/.test(await p.locator('img[data-scale-visual="4"]').getAttribute('src')) && await p.locator('img[data-scale-visual="4"]').isVisible());
  ok('teia selecionada e texto de limite visível', (await p.locator('[data-scale-step="4"]').getAttribute('aria-pressed')) === 'true' && await p.locator('[data-scale-panel="4"]').isVisible());
  await p.locator('[data-scale-step="2"]').focus(); await p.keyboard.press('Enter');
  ok('escala funciona com teclado', await p.locator('[data-scale-panel="2"]').isVisible());
  const light = p.locator('[data-light-play]');
  ok('luz começa parada', (await light.getAttribute('aria-pressed')) === 'false');
  await light.click(); await p.waitForTimeout(250);
  const x = await p.locator('[data-light-pulse]').getAttribute('cx');
  ok('luz avança ao iniciar', Number(x)>45);
  await light.click();
  const stoppedX = await p.locator('[data-light-pulse]').getAttribute('cx');
  await p.waitForTimeout(160);
  ok('luz pausa sem continuar', (await p.locator('[data-light-pulse]').getAttribute('cx')) === stoppedX && (await light.getAttribute('aria-pressed'))==='false');
  await light.click(); await p.evaluate(() => window.scrollTo(0,0)); await p.waitForTimeout(200);
  ok('luz pausa fora da área visível', (await light.getAttribute('aria-pressed')) === 'false');
  await p.goto(BASE + '/capitulos/origem-do-universo/');
  ok('segunda jornada leva aos mistérios', /misterios-do-cosmos/.test(await p.locator('.chapter-pagination a').last().getAttribute('href')));
  const galaxies=p.locator('[data-expansion-galaxy]');
  const initial=await galaxies.first().getAttribute('transform');
  const bound=await p.locator('[data-bound-system]').getAttribute('src');
  const boundSize=await p.locator('[data-bound-system]').evaluate(e => ({width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}));
  await p.locator('[data-expansion-scale]').fill('1.5');
  ok('escala altera separação das galáxias', await galaxies.first().getAttribute('transform') !== initial);
  ok('sistema ligado mantém imagem e tamanho', await p.locator('[data-bound-system]').getAttribute('src') === bound && JSON.stringify(await p.locator('[data-bound-system]').evaluate(e => ({width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}))) === JSON.stringify(boundSize));
  const observerBefore=await galaxies.evaluateAll(nodes => nodes.map(n => n.getAttribute('transform')));
  await p.locator('[data-expansion-observer]').selectOption('11');
  ok('trocar observador muda o referencial', JSON.stringify(observerBefore) !== JSON.stringify(await galaxies.evaluateAll(nodes => nodes.map(n => n.getAttribute('transform')))));
  ok('observador escolhido permanece na origem do referencial', await p.locator('[data-galaxy-id="11"]').getAttribute('transform')==='translate(0 0)');
  ok('imagem renderizada preservada ao trocar observador', /galaxy-marker\.png$/.test(await p.locator('[data-galaxy-id="11"] [data-galaxy-body]').getAttribute('href')) && await p.locator('[data-galaxy-id="11"]').getAttribute('data-observer') === 'true' && await p.locator('[data-galaxy-id="12"]').getAttribute('data-observer') === 'false');
  ok('observador selecionado é destacado', await p.locator('[data-galaxy-id="11"] [data-observer-ring]').getAttribute('data-hidden') === 'false');
  await p.locator('[data-expansion-play]').click(); await p.waitForTimeout(300);
  ok('expansão inicia por ação explícita', (await p.locator('[data-expansion-play]').getAttribute('aria-pressed')) === 'true');
  await p.locator('[data-expansion-play]').click();
  const scale=await p.locator('[data-expansion-scale]').inputValue(); await p.waitForTimeout(160);
  ok('expansão pausa sem continuar', await p.locator('[data-expansion-scale]').inputValue() === scale);
  await p.goto(BASE + '/capitulos/misterios-do-cosmos/');
  ok('luz antiga não é rotulada como mapa CMB', /não é um mapa CMB/.test(await p.locator('[data-evidence-panel="1"] figcaption').textContent()));
  ok('terceira jornada fecha no quiz', /#desafio/.test(await p.locator('.chapter-pagination a').last().getAttribute('href')));
  for(let i=0;i<4;i++) {
    await p.locator(`[data-evidence-select="${i}"]`).click();
    ok(`evidência ${i+1} usa imagem raster`, await p.locator(`[data-evidence-panel="${i}"] img`).count() === 1);
    ok(`evidência ${i+1} revela painel`, await p.locator(`[data-evidence-panel="${i}"]`).isVisible());
    ok(`evidência ${i+1} contém observação interpretação limite`, await p.locator(`[data-evidence-panel="${i}"] dt`).count() === 3);
  }
  ok('quiz de jornada principal tem 3 perguntas', /01 \/ 03/.test(await p.locator('[data-quiz-counter]').innerText()));
  await p.context().close();
}
section('Cenas sem movimento e sem JavaScript');
{
  const p=await page(390,{reducedMotion:'reduce'});
  await p.goto(BASE + '/capitulos/origem-do-universo/');
  await p.locator('[data-expansion-play]').click();
  ok('movimento reduzido usa mudança estática', (await p.locator('[data-expansion-play]').getAttribute('aria-pressed'))==='false' && await p.locator('[data-expansion-scale]').inputValue()==='1.6');
  await p.context().close();
  const n=await page(390,{javaScriptEnabled:false});
  for(const [id,kind] of [['galaxias-e-nebulosas','scale'],['origem-do-universo','expansion'],['misterios-do-cosmos','evidence']]) {
    await n.goto(BASE + '/capitulos/'+id+'/');
    ok(`cena ${kind} tem conteúdo declarativo`, (await n.locator('[data-scene]').innerText()).length>500 && await n.locator('[data-scene] img').count()>0);
    if(kind==='evidence') ok('quatro evidências legíveis sem JS', await n.locator('[data-evidence-panel]:visible').count()===4);
  }
  await n.context().close();
}

await browser.close();
console.log(`\n${pass} verificações OK, ${fails.length} falhas`);
if (fails.length) { console.log(fails.map((f) => ' - ' + f).join('\n')); process.exit(1); }
