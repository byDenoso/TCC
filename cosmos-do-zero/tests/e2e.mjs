// E2E (Playwright/Chromium) contra o build servido em BASE_URL (padrão http://localhost:4321).
// Uso: npm run build && npm run preview &  →  npm run test:e2e   (SHOTS=1 salva capturas em docs/screenshots)
import { chromium } from 'playwright';
import {selectLessonStep,lastLessonStep} from './lib/reader-navigation.mjs';
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
  // navegar no meio de uma transição entre páginas faz o navegador abortá-la; isso vem do teste, não do site
  p.on('pageerror', (e) => { if (!/Transition was aborted/.test(String(e))) p.errors.push(String(e)); });
  p.on('console', (m) => m.type() === 'error' && p.errors.push(m.text()));
  // pedidos cancelados pela própria navegação (ERR_ABORTED) não são falhas
  p.on('requestfailed', (r) => { if (!/ERR_ABORTED/.test(r.failure()?.errorText ?? '')) p.errors.push('requestfailed ' + r.url() + ' ' + (r.failure()?.errorText ?? '')); });
  return p;
}
const unlockLab = (p) => p.evaluate(() => document.querySelectorAll('[data-guess-skip]').forEach((b) => b.click()));
const toLessonEnd = async (p) => { await lastLessonStep(p); await p.waitForTimeout(150); };
const overflow = (p) => p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

// 1 — larguras, rolagem horizontal, erros de console, todas as páginas
section('Larguras × páginas');
for (const w of WIDTHS) {
  const p = await page(w);
  for (const path of ['/', ...CHAPTERS.map((c) => `/capitulos/${c}/`), '/laboratorio/', '/glossario/', '/fontes/', '/404.html']) {
    await p.goto(BASE + path, { waitUntil: 'networkidle' });
    ok(`sem rolagem horizontal ${w}px ${path}`, (await overflow(p)) <= 0, `(+${await overflow(p)}px)`);
    if (await overflow(p) > 0) {
      console.log('OVERFLOW_DETAIL', JSON.stringify(await p.evaluate(() => [...document.querySelectorAll('main *')].map(n => {
        const box = n.getBoundingClientRect(), css = getComputedStyle(n);
        let visibleRight = box.right;
        for (let a = n.parentElement; a && a !== document.body; a = a.parentElement) {
          if (/^(auto|scroll|hidden|clip)$/.test(getComputedStyle(a).overflowX)) visibleRight = Math.min(visibleRight, a.getBoundingClientRect().right);
        }
        return { tag:n.tagName, class:n.className?.baseVal ?? n.className, right:box.right, visibleRight, width:box.width, minWidth:css.minWidth, display:css.display, html:n.outerHTML.slice(0,200) };
      }).filter(n => n.visibleRight > innerWidth + 1 && n.width > 0).slice(0,30))));
      throw new Error(`Overflow real: ${w}px ${path}`);
    }
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
  await toLessonEnd(p);
  await p.locator('[data-complete]').click();
  await p.goto(BASE + '/');
  ok('extra não avança as três jornadas', /0 de 3/.test(await p.locator('[data-progress-label]').first().innerText()));
  await p.goto(BASE + '/capitulos/galaxias-e-nebulosas/');
  // concluir jornada principal → progresso na home
  await toLessonEnd(p);
  await p.locator('[data-complete]').click();
  ok('capítulo marcado como concluído', (await p.locator('[data-complete]').getAttribute('aria-pressed')) === 'true');
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  ok('CTA retoma a segunda jornada', /origem-do-universo/.test(await p.locator('[data-start-journey]').first().getAttribute('href')));
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
  await toLessonEnd(p);
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
  await p.goto(BASE + '/laboratorio/#tempo', { waitUntil: 'networkidle' });
  const n = await p.locator('[data-era-index]').count();
  ok('10 marcos', n === 10, String(n));
  await p.locator('[data-era-index="2"]').click();
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
  await p.goto(BASE + '/laboratorio/#planetas', { waitUntil: 'networkidle' });
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
  await p.goto(BASE + '/laboratorio/#laboratorio', { waitUntil: 'networkidle' });
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
  await bad.goto(BASE + '/laboratorio/?a=xx&b=yy');
  ok('IDs inválidos caem no padrão', (await bad.locator('[data-compare-a]').inputValue()) === 'terra');
  await bad.context().close();
  await p.context().close();
}

// 7 — estrelas
section('Evolução estelar');
{
  const p = await page(1280);
  await p.goto(BASE + '/laboratorio/#laboratorio', { waitUntil: 'networkidle' });
  const r = p.locator('[data-star-mass]');
  const setMass = (v) => r.evaluate((el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); }, v);
  const classes = [];
  for (const v of ['0.3', '1', '3', '12', '30']) {
    await setMass(v);
    classes.push(await p.locator('[data-star-class]').innerText());
  }
  ok('classes distintas por faixa de massa', new Set(classes).size >= 3, classes.join(' | '));
  await setMass('1');
  const svgSun = await p.locator('[data-star-svg]').innerHTML();
  await setMass('30');
  ok('massa altera o dado didático', /30/.test(await p.locator('[data-star-value]').innerText()));
  ok('cena estelar muda com a massa', (await p.locator('[data-star-svg]').innerHTML()) !== svgSun);
  await p.locator('[data-star-step="4"]').click();
  ok('etapa final de estrela massiva diz "pode"', /caminhos possíveis/.test(await p.locator('[data-star-caption]').innerText()));
  await setMass('0.3');
  ok('fim de anã vermelha marcado como previsto', /Previsto/.test(await p.locator('[data-star-caption]').innerText()));
  await p.locator('[data-star-next]').click();
  ok('próxima etapa volta ao início do ciclo', (await p.locator('[data-star-step="0"]').getAttribute('aria-pressed')) === 'true');
  await p.context().close();
}

// 7b — microexperiências, continuidade, links que preservam estado
section('Microexperiências e continuidade');
{
  const p = await page(1280);
  await p.addInitScript(() => localStorage.setItem('cosmos-v5-aula-inteira', '1'));
  for (const ch of ['galaxias-e-nebulosas', 'origem-do-universo', 'misterios-do-cosmos', 'vida-das-estrelas', 'sistema-solar', 'terra-e-atmosfera']) {
    await p.goto(BASE + `/capitulos/${ch}/`, { waitUntil: 'networkidle' });
    const n = await p.locator('.lesson-section').count();
    ok(`${ch}: uma cena por subseção`, (await p.locator('.lesson-section .mx').count()) === n, String(n));
  }
  await p.goto(BASE + '/capitulos/sistema-solar/#sistema-solar-orbitas', { waitUntil: 'networkidle' });
  const mx = p.locator('#sistema-solar-orbitas .mx');
  await mx.scrollIntoViewIfNeeded();
  await p.waitForFunction(() => document.querySelector('#sistema-solar-orbitas .mx')?.classList.contains('is-ready'));
  await mx.locator('[data-mx-guess="1"]').click();
  ok('palpite espera a experiência', await mx.locator('[data-mx-guess-hint]').isVisible() && !(await mx.locator('[data-mx-verdict]').isVisible()));
  const range = mx.locator('[data-mx-range]');
  await range.evaluate((el) => { el.value = '0.2'; el.dispatchEvent(new Event('input', { bubbles: true })); });
  ok('velocidade baixa: cruza limite ilustrativo', /limite central ampliado/.test(await mx.locator('[data-mx-caption]').innerText()));
  ok('palpite revelado depois de mexer', await mx.locator('[data-mx-verdict]').isVisible());
  await range.evaluate((el) => { el.value = '1'; el.dispatchEvent(new Event('input', { bubbles: true })); });
  ok('velocidade de círculo: órbita', /órbita quase circular/.test(await mx.locator('[data-mx-caption]').innerText()));
  await range.evaluate((el) => { el.value = '1.6'; el.dispatchEvent(new Event('input', { bubbles: true })); });
  ok('velocidade alta: escapa', /escapa/.test(await mx.locator('[data-mx-caption]').innerText()));
  await mx.locator('[data-mx-play]').click();
  ok('animar mostra pausar', (await mx.locator('[data-mx-play]').getAttribute('aria-pressed')) === 'true');
  await mx.locator('[data-mx-play]').click();
  ok('pausar para', (await mx.locator('[data-mx-play]').getAttribute('aria-pressed')) === 'false');
  await mx.locator('[data-mx-check="0"]').click();
  ok('verificação certa marca a seção no índice', (await p.locator('[data-toc] a[href="#sistema-solar-orbitas"]').getAttribute('data-practiced')) === 'true');
  await p.goto(BASE + '/capitulos/terra-e-atmosfera/#terra-e-atmosfera-camadas', { waitUntil: 'networkidle' });
  const cam = p.locator('#terra-e-atmosfera-camadas .mx');
  await cam.scrollIntoViewIfNeeded();
  await p.waitForFunction(() => document.querySelector('#terra-e-atmosfera-camadas .mx')?.classList.contains('is-ready'));
  await cam.locator('[data-mx-range]').evaluate((el) => { el.value = '30'; el.dispatchEvent(new Event('input', { bubbles: true })); });
  ok('perfil da atmosfera: 30 km é estratosfera', /estratosfera/.test(await cam.locator('[data-mx-caption]').innerText()));
  await p.context().close();
}
{
  const p = await page(1280);
  await p.goto(BASE + '/?lab=receita&om=2&ol=0', { waitUntil: 'networkidle' });
  await p.locator('.main-nav a[data-spy="observatorio"]').click();
  await p.waitForTimeout(400);
  ok('link do menu preserva o experimento', /om=2/.test(p.url()) && /lab=receita/.test(p.url()), p.url());
  ok('receita continua com matéria demais', /colapsa/.test(await p.locator('[data-r-out="fate"]').innerText()));
  await p.goto(BASE + '/capitulos/origem-do-universo/', { waitUntil: 'networkidle' });
  await p.locator('[data-step-next]').click(); await p.locator('[data-step-next]').click();
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  ok('home oferece retomar a aula', await p.locator('[data-resume]').isVisible() && /#origem-do-universo-fase-quente/.test(await p.locator('[data-resume]').getAttribute('href')));
  await p.goto(BASE + '/capitulos/origem-do-universo/', { waitUntil: 'networkidle' });
  await p.locator('[data-resume-go]').click();
  ok('retomar abre o passo salvo', !(await p.locator('#origem-do-universo-fase-quente').isHidden()));
  await p.goto(BASE + '/?assunto=terra-e-atmosfera#desafio', { waitUntil: 'networkidle' });
  const quiz = p.locator('[data-quiz]').first();
  await quiz.locator('[data-answer]').nth(0).click();
  ok('revisão do quiz leva ao trecho exato', /#terra-e-atmosfera-/.test(await quiz.locator('.quiz-review-link').getAttribute('href')));
  await p.goto(BASE + '/glossario/?q=ano%20luz', { waitUntil: 'networkidle' });
  ok('glossário acha "ano luz"', /^1 termo/.test(await p.locator('[data-glossary-count]').innerText()) || !/^0/.test(await p.locator('[data-glossary-count]').innerText()));
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
  await p.goto(BASE + '/glossario/', { waitUntil: 'networkidle' });
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
  await p.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  ok('abertura desenha o mapa da luz mais antiga', await p.locator('[data-cmb-canvas]').evaluate((c) => { const d = c.getContext('2d').getImageData(c.width / 2, c.height / 2, 1, 1).data; return d[3] === 255; }));
  const frame = p.locator('[data-cmb-frame]'); const box = await frame.boundingBox();
  await p.mouse.move(box.x + box.width * 0.4, box.y + box.height * 0.5);
  ok('mapa responde ao ponteiro com temperatura ilustrativa', /mapa simulado/.test(await p.locator('[data-cmb-read]').innerText()) && /milionésimos de kelvin|na média/.test(await p.locator('[data-cmb-read]').innerText()), await p.locator('[data-cmb-read]').innerText());
  await frame.focus(); await p.keyboard.press('ArrowRight');
  ok('mapa explorável pelo teclado', !(await p.locator('[data-cmb-probe]').isHidden()));
  ok('home sem renders fotorrealistas de IA', await p.locator('img[src*="/renders/"]').count() === 0);
  ok('home sem esferas procedurais', await p.locator('.stellar-orb,.era-orb,.solar-disc,.solar-rim,.eclipse-glow').count() === 0);
  const broken = await p.evaluate(() => [...document.images].filter((i) => i.loading !== 'lazy' || i.getBoundingClientRect().top < innerHeight * 3).filter((i) => i.complete && i.naturalWidth === 0).map((i) => i.src));
  ok('nenhuma imagem quebrada na home', broken.length === 0, broken.join(','));
  const noAlt = await p.evaluate(() => [...document.images].filter((i) => !i.hasAttribute('alt')).length);
  ok('todas as imagens têm atributo alt', noAlt === 0, String(noAlt));
  await p.goto(BASE + '/fontes/', { waitUntil: 'networkidle' });
  const ext = await p.locator('#fontes a[href^="http"]').count();
  ok('fontes têm links externos', ext >= 10, String(ext));
  const unsafe = await p.evaluate(() => [...document.querySelectorAll('a[target=_blank]')].filter((a) => !/noopener/.test(a.rel)).length);
  ok('target=_blank com rel=noopener', unsafe === 0);
  // links internos
  const hrefs = await p.evaluate(() => [...new Set([...document.querySelectorAll('a[href^="/"]')].map((a) => a.getAttribute('href').split('#')[0].split('?')[0]))]);
  for (const h of hrefs) { const r = await p.request.get(new URL(h, BASE + "/").href); ok(`link interno ${h}`, r.ok(), String(r.status())); }
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
  await p.goto(BASE + '/laboratorio/', { waitUntil: 'networkidle' });
  const t = await p.innerText('body');
  ok('experimentos legíveis sem JS (tabela de comparação e percurso estelar)', /Terra/.test(t) && /Júpiter/.test(t) && /Estrela/i.test(t));
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
  ok('home enxuta: dicionário e fontes em páginas próprias', await p.locator('#glossario, #fontes, #planetas').count() === 0);
  ok('trilha do curso com 3 aulas e desafio', await p.locator('[data-course-node]').count() === 4);
  await p.goto(BASE + '/#planetas', { waitUntil: 'networkidle' }); await p.waitForURL(/laboratorio/);
  ok('endereço antigo leva aos planetas', /\/laboratorio\/#planetas$/.test(p.url()) && await p.locator('#planetas').isVisible());
  await p.goto(BASE + '/#glossario', { waitUntil: 'networkidle' }); await p.waitForURL(/glossario/);
  ok('endereço antigo leva ao dicionário', /\/glossario\/$/.test(p.url()));
  // A first click after page load must work even when an optional scene module is slow.
  await p.route('**/_astro/scenes.*.js', async route => {
    await new Promise(resolve => setTimeout(resolve, 2200)); await route.continue();
  });
  await p.goto(BASE + '/capitulos/galaxias-e-nebulosas/');
  ok('primeira jornada leva à expansão', /origem-do-universo/.test(await p.locator('.chapter-pagination a').last().getAttribute('href')));
  ok('cinco escalas disponíveis', await p.locator('[data-scale-step]').count() === 5);
  ok('cinco escalas usam ilustrações vetoriais da identidade', await p.locator('svg [data-scale-visual]').count() === 5);
  ok('galeria começa com uma única ilustração visível', await p.locator('[data-scale-visual]:visible').count() === 1);
  ok('capítulo sem esfera procedural', await p.locator('.concept-orb,.era-orb,.solar-disc,.solar-rim').count() === 0);
  await p.locator('[data-scale-step="4"]').click(); await p.waitForTimeout(1400);
  ok('galeria mantém um palco ativo ou uma alternativa SVG', await p.locator('[data-scale-stage] canvas:visible').count()===1 || await p.locator('[data-scale-visual]:visible').count()===1);
  ok('teia cósmica visível no palco ativo ou fallback', await p.locator('[data-scale-stage] canvas:visible').count()===1 || await p.locator('[data-scale-visual="4"]').isVisible());
  ok('estado visual da teia e legenda correspondem à seleção', await p.locator('[data-scene-status]').first().innerText().then(t=>/Escala 5 de 5/.test(t)) && await p.locator('[data-scale-visual="4"]').getAttribute('data-hidden')==='false');
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
  await light.click(); await p.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' })); await p.waitForTimeout(250);
  ok('luz pausa fora da área visível', (await light.getAttribute('aria-pressed')) === 'false');
  await p.goto(BASE + '/capitulos/origem-do-universo/');
  ok('segunda jornada leva aos mistérios', /misterios-do-cosmos/.test(await p.locator('.chapter-pagination a').last().getAttribute('href')));
  {
    await unlockLab(p);
    const st=p.locator('[data-station="expansao"]');
    const galaxies=st.locator('.e-galaxy');
    const before=await galaxies.nth(1).getAttribute('transform');
    await st.locator('[data-e-range]').evaluate(e=>{e.value='1.5';e.dispatchEvent(new Event('input',{bubbles:true}))});
    ok('expansão: escala altera a separação das galáxias', await galaxies.nth(1).getAttribute('transform') !== before);
    ok('expansão: leitura explica a proporção', /mesma proporção/.test(await st.locator('[data-e-reading]').innerText()));
    const all=await galaxies.evaluateAll(n=>n.map(x=>x.getAttribute('transform')));
    await st.locator('[data-e-observer="1"]').click();
    ok('expansão: tocar numa galáxia muda o referencial', JSON.stringify(all)!==JSON.stringify(await galaxies.evaluateAll(n=>n.map(x=>x.getAttribute('transform')))));
    ok('expansão: galáxia escolhida fica no centro', await st.locator('.e-galaxy.is-observer').getAttribute('transform')==='translate(320.00 200.00)');
    await st.locator('[data-e-play]').click(); await p.waitForTimeout(300);
    ok('expansão inicia por ação explícita', (await st.locator('[data-e-play]').getAttribute('aria-pressed')) === 'true');
    ok('expansão realmente aumenta ao animar', Number(await st.locator('[data-e-range]').inputValue())>1.5);
    await st.locator('[data-e-play]').click();
    const scale=await st.locator('[data-e-range]').inputValue(); await p.waitForTimeout(160);
    ok('expansão pausa sem continuar', await st.locator('[data-e-range]').inputValue() === scale);
  }
  await p.goto(BASE + '/capitulos/misterios-do-cosmos/');
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
  await unlockLab(p);
  await p.locator('[data-e-play]').click();
  ok('movimento reduzido avança um passo estático', (await p.locator('[data-e-play]').getAttribute('aria-pressed'))==='false' && await p.locator('[data-e-range]').inputValue()==='1.25');
  const staticValue=await p.locator('[data-e-range]').inputValue(), staticPositions=await p.locator('.e-galaxy').evaluateAll(n=>n.map(e=>e.getAttribute('transform')));await p.waitForTimeout(220);
  ok('movimento reduzido preserva valor e posições parados', await p.locator('[data-e-range]').inputValue()===staticValue && JSON.stringify(staticPositions)===JSON.stringify(await p.locator('.e-galaxy').evaluateAll(n=>n.map(e=>e.getAttribute('transform')))));
  for(let i=0;i<5;i++)await p.locator('[data-e-play]').click();
  ok('movimento reduzido respeita limite2.5', await p.locator('[data-e-range]').inputValue()==='2.5');
  await p.locator('[data-e-play]').click();ok('movimento reduzido recomeça após o limite', await p.locator('[data-e-range]').inputValue()==='1');
  await p.context().close();
  const n=await page(390,{javaScriptEnabled:false});
  for(const [id,kind] of [['galaxias-e-nebulosas','scale'],['misterios-do-cosmos','evidence']]) {
    await n.goto(BASE + '/capitulos/'+id+'/');
    ok(`cena ${kind} tem conteúdo declarativo`, (await n.locator('[data-scene]').innerText()).length>500 && await n.locator('[data-scene] img, [data-scene] svg').count()>0);
    if(kind==='evidence') ok('quatro evidências legíveis sem JS', await n.locator('[data-evidence-panel]:visible').count()===4);
  }
  await n.goto(BASE + '/');
  ok('sem JS: observatório avisa que precisa de JavaScript', /precisam de JavaScript/.test(await n.locator('#observatorio').innerText()));
  await n.context().close();
}

section('Observatório');
{
  const p=await page(1280);
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  const tabs=p.locator('[data-obs-tab]');
  ok('4 experimentos', await tabs.count()===4);
  // máquina do tempo
  const t=p.locator('[data-station="tempo"]');
  ok('palpite opcional: experimento começa acessível e legível', await t.locator('[data-guess]').isVisible() && !(await t.locator('.obs-grid').evaluate((g) => g.hasAttribute('inert'))));
  await t.locator('[data-opt="b"]').click();
  ok('tempo: palpite revela explicação e destrava', await t.locator('[data-guess-result]').isVisible() && !(await t.locator('.obs-grid').evaluate((g) => g.hasAttribute('inert'))));
  ok('selo do primeiro palpite aparece', await p.locator('.badge-toast').count() >= 1);
  await unlockLab(p);
  await t.locator('[data-t-preset="1090"]').click(); await p.waitForTimeout(1900);
  ok('tempo: luz mais antiga sai aos ~370 mil anos', /37\d mil anos/.test(await t.locator('[data-t-out="age"]').innerText()), await t.locator('[data-t-out="age"]').innerText());
  ok('tempo: viajou ~13,8 bilhões de anos', /13,8 bilhões/.test(await t.locator('[data-t-out="look"]').innerText()));
  ok('tempo: chega como micro-ondas ou infravermelho', /infravermelho|micro-ondas/.test(await t.locator('[data-t-out="line"]').innerText()));
  ok('tempo: URL guarda z', /z=1090/.test(p.url()));
  ok('tempo: época muda para luz liberada', /transparente/.test(await t.locator('[data-t-epoch-title]').innerText()));
  await t.locator('[data-t-preset="0"]').click(); await p.waitForTimeout(1900);
  ok('tempo: hoje sem z na URL', !/[?&]z=/.test(p.url()));
  // teclado nas abas
  await tabs.first().focus(); await p.keyboard.press('ArrowRight');
  ok('abas: seta direita abre o próximo', await p.locator('[data-station="expansao"]').isVisible() && /lab=expansao/.test(p.url()));
  await p.keyboard.press('End');
  ok('abas: End abre o último', await p.locator('[data-station="receita"]').isVisible());
  await unlockLab(p);
  // receita
  const r=p.locator('[data-station="receita"]');
  ok('receita: idade padrão 13,8', /13,8 bilhões/.test(await r.locator('[data-r-out="age"]').innerText()));
  ok('receita: nosso Universo acelera', /acelerando/.test(await r.locator('[data-r-out="accel"]').innerText()));
  await r.locator('[data-r-scenario="crunch"]').click();
  ok('receita: matéria demais colapsa', /colapsa/.test(await r.locator('[data-r-out="fate"]').innerText()));
  await r.locator('[data-r-scenario="materia"]').click();
  ok('receita: só matéria freia', /freando/.test(await r.locator('[data-r-out="accel"]').innerText()) && /mais devagar/.test(await r.locator('[data-r-out="fate"]').innerText()));
  await r.locator('[data-r-ol]').evaluate(e=>{e.value='1.5';e.dispatchEvent(new Event('input',{bubbles:true}))});
  await r.locator('[data-r-om]').evaluate(e=>{e.value='0.05';e.dispatchEvent(new Event('input',{bubbles:true}))});
  ok('receita: receita sem Big Bang mostra aviso', await r.locator('[data-r-warn]').isVisible());
  await r.locator('[data-r-scenario="nosso"]').click();
  await r.locator('[data-r-h0set="73.04"]').click();
  ok('receita: H0 local deixa o Universo mais novo', /12,7 bilhões/.test(await r.locator('[data-r-out="age"]').innerText()), await r.locator('[data-r-out="age"]').innerText());
  // hubble
  await p.locator('[data-obs-tab="hubble"]').click(); await unlockLab(p);
  const h=p.locator('[data-station="hubble"]');
  await h.locator('.h-gal').nth(2).click();
  ok('hubble: medir mostra distância e velocidade', /anos-luz/.test(await h.locator('[data-h-reading]').innerText()) && /km por segundo/.test(await h.locator('[data-h-reading]').innerText()));
  await h.locator('[data-h-all]').click();
  const res=await h.locator('[data-h-result]').innerText();
  const m=res.match(/Cerca de (\d+) km\/s mais rápido/);
  ok('hubble: ritmo medido plausível (18–25 km/s por milhão de anos-luz)', m && Number(m[1])>=18 && Number(m[1])<=25, res.slice(0,80));
  await h.locator('[data-h-reveal]').click();
  ok('hubble: revelar mostra valor do jogo', /valor certo do jogo/.test(await h.locator('[data-h-result]').innerText()));
  await h.locator('[data-h-new]').click();
  ok('hubble: céu novo zera medidas', /Nenhuma medida/.test(await h.locator('[data-h-result]').innerText()));
  ok('observatório sem erros', p.errors.length===0, p.errors.join(' | '));
  // deep link
  const d=await page(390);
  await d.goto(BASE + '/?lab=receita&om=2&ol=0', { waitUntil: 'networkidle' });
  ok('link direto abre a receita com valores', await d.locator('[data-station="receita"]').isVisible() && /colapsa/.test(await d.locator('[data-r-out="fate"]').innerText()));
  await d.context().close();
  await p.context().close();
}

section('Tema claro e escuro');
{
  const p=await page(1280,{colorScheme:'dark'});
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  ok('segue o sistema (escuro)', await p.evaluate(()=>document.documentElement.dataset.theme)==='dark');
  const bgDark=await p.evaluate(()=>getComputedStyle(document.body).backgroundColor);
  await p.locator('[data-theme-toggle]').click();
  ok('botão troca para claro', await p.evaluate(()=>document.documentElement.dataset.theme)==='light' && bgDark!==await p.evaluate(()=>getComputedStyle(document.body).backgroundColor));
  await p.reload({ waitUntil: 'networkidle' });
  ok('escolha persiste ao recarregar', await p.evaluate(()=>document.documentElement.dataset.theme)==='light');
  ok('botão anuncia a próxima ação', /escuro/i.test(await p.locator('[data-theme-toggle]').getAttribute('aria-label')));
  await p.context().close();
  const q=await page(1280,{colorScheme:'light'});
  await q.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('blocked', 'SecurityError'); } }); });
  await q.goto(BASE + '/', { waitUntil: 'networkidle' });
  await q.locator('[data-theme-toggle]').click();
  ok('tema funciona sem armazenamento', await q.evaluate(()=>document.documentElement.dataset.theme)==='dark' && q.errors.length===0, q.errors.join(' | '));
  await q.context().close();
}

section('Reauditoria: fragmentos e histórico das seis aulas');
for (const chapter of CHAPTERS) {
  const p = await page(1280);
  const path = `${BASE}/capitulos/${chapter}/`;
  await p.goto(path, { waitUntil: 'networkidle' });
  const ids = await p.locator('.lesson-section').evaluateAll(nodes => nodes.map(n => n.id));
  const active = () => p.locator('.lesson-section:visible').evaluateAll(nodes => nodes.map(n => n.id));
  await p.goto(`${path}?nivel=profundo#${ids[0]}`, { waitUntil: 'networkidle' });
  await p.locator('[data-step-dot]').last().focus();
  await p.keyboard.press('Enter');
  ok(`${chapter}: teclado seleciona o passo e sincroniza o hash`, new URL(p.url()).hash === `#${ids[5]}` && JSON.stringify(await active()) === JSON.stringify([ids[5]]));
  ok(`${chapter}: passo preserva query`, new URL(p.url()).searchParams.get('nivel') === 'profundo');
  await p.reload({ waitUntil: 'networkidle' });
  ok(`${chapter}: recarga mantém a seção compartilhada`, JSON.stringify(await active()) === JSON.stringify([ids[5]]) && await p.locator('.lesson-resume').count() === 0);
  await p.locator('[data-step-dot="1"]').click();
  await p.goBack();
  ok(`${chapter}: voltar restaura passo e URL`, new URL(p.url()).hash === `#${ids[5]}` && JSON.stringify(await active()) === JSON.stringify([ids[5]]));
  await p.goForward();
  ok(`${chapter}: avançar restaura passo e URL`, new URL(p.url()).hash === `#${ids[1]}` && JSON.stringify(await active()) === JSON.stringify([ids[1]]));
  await p.locator('[data-step-next]').click();
  ok(`${chapter}: próximo sincroniza URL`, new URL(p.url()).hash === `#${ids[2]}`);
  await p.locator('[data-step-prev]').click();
  ok(`${chapter}: anterior sincroniza URL`, new URL(p.url()).hash === `#${ids[1]}`);
  await p.locator('[data-step-dot]').last().click();
  await p.goto(`${path}#${ids[0]}`, { waitUntil: 'networkidle' });
  ok(`${chapter}: âncora do passo 1 prevalece sobre retomada do 6`, JSON.stringify(await active()) === JSON.stringify([ids[0]]) && await p.locator('.lesson-resume').count() === 0);
  await p.locator('[data-step-dot]').last().click();
  await p.goto(path, { waitUntil: 'networkidle' });
  ok(`${chapter}: sem âncora oferece retomada`, await p.locator('[data-resume-go]').isVisible());
  await p.locator('[data-resume-go]').click();
  ok(`${chapter}: retomar também produz URL compartilhável`, new URL(p.url()).hash === `#${ids[5]}`);
  await p.goto(`${path}#${ids[2]}-mx-ask`, { waitUntil: 'networkidle' });
  ok(`${chapter}: alvo interno abre seu passo sem reescrever o link`, JSON.stringify(await active()) === JSON.stringify([ids[2]]) && new URL(p.url()).hash === `#${ids[2]}-mx-ask`);
  await p.locator('[data-step-toggle]').click();
  await p.locator('[data-toc] a').nth(1).click();
  await p.locator('[data-step-toggle]').click();
  ok(`${chapter}: sair da aula inteira mantém a seção do índice`, JSON.stringify(await active()) === JSON.stringify([ids[1]]));
  ok(`${chapter}: navegação sem erros`, p.errors.length === 0, p.errors.join(' | '));
  await p.context().close();
}

section('Reauditoria: laboratório, títulos e procedência');
{
  const p = await page(390);
  await p.goto(`${BASE}/laboratorio/?massa=30`, { waitUntil: 'networkidle' });
  const challenge = p.getByRole('link', { name: '03 Testar suas ideias ↓', exact: true });
  await challenge.focus();
  await Promise.all([p.waitForURL(url => url.pathname === new URL(BASE + '/').pathname && url.hash === '#desafio'), p.keyboard.press('Enter')]);
  await p.locator('#desafio').waitFor({state:'visible'});
  ok('laboratório: link por teclado chega ao desafio da home', new URL(p.url()).pathname === new URL(BASE + '/').pathname && new URL(p.url()).hash === '#desafio' && await p.locator('#desafio').isVisible());
  for (const route of ['glossario', 'fontes']) {
    await p.goto(`${BASE}/${route}/`, { waitUntil: 'networkidle' });
    ok(`${route}: título principal único h1`, await p.locator('main h1').count() === 1);
  }
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  ok('CMB tem procedência simulada visível', /Mapa simulado/.test(await p.locator('#cmb-provenance').innerText()) && /não são medidas/.test(await p.locator('#cmb-provenance').innerText()));
  await p.locator('[data-cmb-frame]').focus(); await p.keyboard.press('ArrowRight');
  ok('CMB teclado informa que o valor é simulado', /mapa simulado/.test(await p.locator('[data-cmb-read]').innerText()));
  ok('idade permanece no valor científico', await p.locator('.hero-foot-center .number').first().innerText() === '13,8');
  ok('ajustes secundários sem erros', p.errors.length === 0, p.errors.join(' | '));
  await p.context().close();
}

section('Cabeçalho acima das cenas após rolar');
for (const width of [390, 1440]) {
  const p = await page(width, { reducedMotion: 'reduce' });
  await p.goto(`${BASE}/?lab=tempo&z=0.5#observatorio`, { waitUntil: 'networkidle' });
  await p.locator('[data-t-preset="0.5"]').click();
  const control = p.locator(width < 700 ? '.mobile-menu summary' : '.main-nav a[href$="/laboratorio/"]');
  ok(`cabeçalho ${width}: uma única navegação`, await p.locator('.header-shell').count() === 1);
  ok(`cabeçalho ${width}: recebe cliques acima dos cartões`, await control.evaluate(a => { const r = a.getBoundingClientRect(); return a.contains(document.elementFromPoint(r.x + r.width/2, r.y + r.height/2)); }));
  await control.click();
  if (width < 700) await p.locator('.mobile-menu a[href$="/laboratorio/"]').click();
  await p.waitForURL(url => url.pathname.endsWith('/laboratorio/'));
  ok(`cabeçalho ${width}: navega após rolar`, /laboratorio/.test(p.url()) && p.errors.length === 0, p.errors.join(' | '));
  await p.context().close();
}

section('Épocas coerentes e retorno ao desafio');
for (const width of [390, 1440]) {
  const p = await page(width, { reducedMotion: 'reduce' });
  await p.goto(`${BASE}/?lab=tempo&z=0.5#observatorio`, { waitUntil: 'networkidle' });
  const age = await p.locator('[data-t-out="age"]').innerText();
  ok(`época ${width}: texto usa a idade do painel`, (await p.locator('[data-t-epoch-text]').innerText()).includes(age));
  ok(`época ${width}: z=0,5 já passou pelo auge`, /já passou/.test(await p.locator('[data-t-epoch-text]').innerText()) && !/época de mais estrelas/i.test(await p.locator('[data-t-epoch-title]').innerText()));
  await p.goto(`${BASE}/?lab=tempo&z=2#observatorio`, { waitUntil: 'networkidle' });
  ok(`época ${width}: z=2 perto do auge`, /auge/.test(await p.locator('[data-t-epoch-title]').innerText()));
  for (const chapterQuiz of [false, true]) {
    await p.goto(BASE + (chapterQuiz ? '/capitulos/galaxias-e-nebulosas/' : '/#desafio'), { waitUntil: 'networkidle' });
    if (chapterQuiz) await toLessonEnd(p);
    const quiz = p.locator('[data-quiz]');
    await quiz.locator('[data-answer]').nth(1).click();
    const question = await quiz.locator('[data-quiz-question]').innerText();
    const counter = await quiz.locator('[data-quiz-counter]').innerText();
    await quiz.locator('.quiz-review-link').first().click();
    const back = p.locator('[data-quiz-return]');
    await back.waitFor({ state: 'visible' });
    ok(`quiz ${width}/${chapterQuiz}: revisão oferece retorno explícito`, await back.isVisible());
    await back.focus(); await p.keyboard.press('Enter');
    await p.locator('[data-quiz]').waitFor({ state: 'visible' });
    ok(`quiz ${width}/${chapterQuiz}: pergunta e posição preservadas`, await p.locator('[data-quiz-question]').innerText() === question && await p.locator('[data-quiz-counter]').innerText() === counter);
    ok(`quiz ${width}/${chapterQuiz}: resposta e foco preservados`, await p.locator('[data-quiz-answers] button:disabled').count() > 0 && await p.locator('[data-quiz-question]').evaluate(n => n === document.activeElement));
    await p.locator('[data-quiz-next]').click();
    ok(`quiz ${width}/${chapterQuiz}: tentativa continua`, /02 \/ /.test(await p.locator('[data-quiz-counter]').innerText()));
  }
  await p.goto(BASE + '/capitulos/origem-do-universo/#origem-do-universo-primeira-luz', { waitUntil: 'networkidle' });
  await p.locator('[data-cmbj]').scrollIntoViewIfNeeded();
  ok(`CMB ${width}: fator de escala tem rótulo preciso`, /Escala das distâncias/i.test(await p.locator('.cmbj-panel').innerText()));
  ok(`regressões ${width}: sem erros e sem overflow`, p.errors.length === 0 && await overflow(p) <= 0, p.errors.join(' | '));
  await p.context().close();
}

section('36 microexperiências: mobile e alternativa sem movimento');
for (const [width, reduced] of [[390, false], [1280, true]]) {
  for (const chapter of CHAPTERS) {
    const p = await page(width, { reducedMotion: reduced ? 'reduce' : 'no-preference' });
    await p.goto(`${BASE}/capitulos/${chapter}/`, { waitUntil: 'networkidle' });
    // a seção da primeira luz usa a jornada da CMB (tests/cmb-journey.mjs) no lugar da microcena
    const found = await p.locator('[data-mx], [data-cmbj]').evaluateAll(nodes => nodes.map(n => ({ id: n.dataset.mx, dot: [...document.querySelectorAll('.lesson-section')].indexOf(n.closest('.lesson-section')) })));
    const ids = found.filter((f) => f.id).map((f) => f.id), dots = found.filter((f) => f.id).map((f) => f.dot);
    ok(`${chapter} ${width}px: seis mecanismos`, found.length === 6);
    for (let i = 0; i < ids.length; i++) {
      const id = ids[i];
      const failuresBefore = fails.length;
      await selectLessonStep(p,dots[i]);
      const root = p.locator(`[data-mx="${id}"]`);
      await root.scrollIntoViewIfNeeded();
      await p.waitForFunction(id => document.querySelector(`[data-mx="${id}"]`)?.classList.contains('is-ready'), id);
      const svg = root.locator('[data-mx-svg]');
      const play = root.locator('[data-mx-play]');
      await root.locator('[data-mx-reset]').click();
      const initial = await svg.innerHTML();
      ok(`${id} ${width}px: cena carregada e descrição acessível`, initial.length > 100 && (await svg.getAttribute('aria-label')).length > 20 && (await root.locator('.mx-limit').innerText()).length > 20);
      const range = root.locator('[data-mx-range]');
      if (await range.count()) {
        await range.focus(); await p.keyboard.press('End');
        ok(`${id} ${width}px: controle por teclado com valor descritivo`, (await range.inputValue()) === await range.getAttribute('max') && !!await range.getAttribute('aria-valuetext'));
      } else {
        await root.locator('[data-mx-opt]').last().focus(); await p.keyboard.press('Enter');
        if (await play.getAttribute('aria-pressed') === 'true') await play.click();
        ok(`${id} ${width}px: opção selecionada por teclado`, await root.locator('[data-mx-opt]').last().getAttribute('aria-pressed') === 'true');
      }
      ok(`${id} ${width}px: manipulação muda a representação`, await svg.innerHTML() !== initial);
      ok(`${id} ${width}px: resultado textual e geometria finita`, (await root.locator('[data-mx-caption]').innerText()).length > 20 && !/NaN|Infinity|undefined/.test(await svg.innerHTML()));
      await root.locator('[data-mx-reset]').click();
      await play.click();
      if (reduced) {
        const still = await svg.innerHTML();
        await p.waitForTimeout(80);
        ok(`${id}: movimento reduzido avança sem animar`, await play.getAttribute('aria-pressed') === 'false' && await svg.innerHTML() === still);
      } else {
        await p.waitForTimeout(100);
        ok(`${id}: iniciar explicita estado ativo`, await play.getAttribute('aria-pressed') === 'true');
        await play.click();
        const paused = await svg.innerHTML(); await p.waitForTimeout(80);
        ok(`${id}: pausar interrompe o desenho`, await play.getAttribute('aria-pressed') === 'false' && await svg.innerHTML() === paused);
      }
      await root.locator('[data-mx-reset]').click();
      ok(`${id} ${width}px: reiniciar recupera estado inicial`, await svg.innerHTML() === initial);
      const box = root.locator('[data-mx-check-box]');
      const right = Number(await box.getAttribute('data-right'));
      const choices = box.locator('[data-mx-check]');
      const wrong = (right + 1) % await choices.count();
      await choices.nth(wrong).click();
      ok(`${id} ${width}px: erro permite revisão e nova tentativa`, /Ainda não/.test(await box.locator('[data-mx-check-label]').innerText()) && await choices.nth(right).isEnabled());
      await choices.nth(right).click();
      ok(`${id} ${width}px: acerto registra esta verificação`, /nesta visita/.test(await root.locator('[data-mx-history]').innerText()));
      console.log('MICRO_RESULT', JSON.stringify({ chapter, id, width, reducedMotion: reduced, passed: fails.length === failuresBefore }));
    }
    await p.reload({ waitUntil: 'networkidle' });
    const lastId = ids[ids.length - 1];
    const last = p.locator(`[data-mx="${lastId}"]`);
    await last.scrollIntoViewIfNeeded();
    await p.waitForFunction(id => document.querySelector(`[data-mx="${id}"]`)?.classList.contains('is-ready'), lastId);
    ok(`${chapter} ${width}px: histórico distingue visita anterior`, /visita anterior/.test(await last.locator('[data-mx-history]').innerText()) && await last.locator('[data-mx-check]').first().isEnabled());
    ok(`${chapter} ${width}px: todas as cenas sem erros`, p.errors.length === 0, p.errors.join(' | '));
    ok(`${chapter} ${width}px: cena sem overflow`, await overflow(p) <= 0);
    await p.context().close();
  }
}


// Regressões da revisão de UX: armazenamento inválido e controles acessíveis.
section('Leitura, busca e régua acessível');
{
  const p = await page(390, { reducedMotion: 'reduce' });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await p.evaluate(() => localStorage.setItem('cosmos-v6-onde', 'null'));
  await p.goto(BASE + '/#%E0%A4%A', { waitUntil: 'networkidle' });
  ok('hash e posição inválidos não quebram navegação', p.errors.length === 0 && await p.locator('.hero-actions .cta').isVisible());
  await p.goto(BASE + '/glossario/?q=Ano-luz#termo-4', { waitUntil: 'networkidle' });
  ok('link do dicionário abre o termo pedido', await p.locator('#termo-4').getAttribute('open') !== null);
  await p.locator('[data-glossary-reset]').click();
  ok('limpar busca preserva foco e recupera termos', await p.locator('[data-glossary-input]').inputValue() === '' && await p.locator('[data-term-index]:visible').count() === 26);
  await p.goto(BASE + '/laboratorio/', { waitUntil: 'networkidle' });
  const ruler = p.locator('[data-ruler="saturno"]');
  await ruler.focus(); await p.keyboard.press('Enter');
  ok('régua escolhe planeta pelo teclado', await ruler.getAttribute('aria-pressed') === 'true' && await p.locator('[data-planet-name]').innerText() === 'Saturno');
  await p.goto(BASE + '/capitulos/origem-do-universo/', { waitUntil: 'networkidle' });
  await p.locator('.reader-entry .cta').click();
  ok('atalho abre o primeiro passo da aula', p.url().includes('#origem-do-universo-o-universo') && await p.locator('.lesson-section').first().isVisible());
  ok('seletor mobile está visível e rotulado', await p.getByLabel('Passo da aula', { exact: true }).isVisible());
  ok('alvos da trilha têm área útil de toque', await p.locator('[data-step-select], [data-step-prev], [data-step-next]').evaluateAll(nodes => nodes.length === 3 && nodes.every(n => { const r = n.getBoundingClientRect(); return r.width >= 44 && r.height >= 48; })));
  await selectLessonStep(p, 2);
  ok('seletor mobile sincroniza passo e URL', await p.locator('[data-step-select]').inputValue() === '2' && new URL(p.url()).hash === await p.locator('.lesson-section').nth(2).getAttribute('id').then(id => '#' + id));
  await p.evaluate(() => sessionStorage.setItem(`cosmos-quiz:${location.pathname}:origem-do-universo`, JSON.stringify({ ids: ['big-bang'], position: -1, answered: true, choice: 99, history: [null], finished: false })));
  await p.reload({ waitUntil: 'networkidle' });
  ok('quiz inválido recupera a primeira pergunta sem erro', p.errors.length === 0);
  await p.context().close();
}

section('Hubble: exemplo, teclado e alternativa leve');
for(const width of [390,1440]){
 const p=await page(width,{reducedMotion:'reduce'});
 await p.goto(BASE+'/capitulos/origem-do-universo/#origem-do-universo-expansao',{waitUntil:'networkidle'});
 const module=p.locator('[data-hubble-lesson]');
 ok(`Hubble ${width}: pré-requisito aponta para a aula anterior`,await p.locator('.lesson-path a').getAttribute('href')===new URL(BASE+'/capitulos/galaxias-e-nebulosas/').pathname);
 const slider=module.getByRole('slider');await slider.focus();await p.keyboard.press('ArrowRight');
 ok(`Hubble ${width}: régua responde ao teclado`,/1.750/.test(await module.locator('[data-hubble-value]').innerText()));
 await module.getByRole('radio',{name:'700 km/s',exact:true}).check();await module.getByRole('button',{name:'Conferir resposta'}).click();
 ok(`Hubble ${width}: erro orienta nova tentativa`,await module.locator('[data-hubble-feedback]').getAttribute('data-correct')==='false');
 await module.getByRole('radio',{name:'2.100 km/s',exact:true}).check();await module.getByRole('button',{name:'Conferir resposta'}).click();
 ok(`Hubble ${width}: acerto explica a conta`,await module.locator('[data-hubble-feedback]').getAttribute('data-correct')==='true'&&/70 × 30/.test(await module.locator('[data-hubble-feedback]').innerText()));
 await module.locator('.hubble-values summary').click();ok(`Hubble ${width}: tabela acessível`,await module.locator('tbody tr').count()===5);
 ok(`Hubble ${width}: sem overflow`,await overflow(p)<=0);
 const contrast=await module.locator('.hubble-control p').evaluate(n=>{const c=getComputedStyle(n).color,b=getComputedStyle(n.closest('[data-hubble-lesson]')).backgroundColor;const luminance=s=>{const a=(s.match(/[\d.]+/g)||[]).slice(0,3).map(Number).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return .2126*a[0]+.7152*a[1]+.0722*a[2]};const x=luminance(c),y=luminance(b);return(Math.max(x,y)+.05)/(Math.min(x,y)+.05)});
 ok(`Hubble ${width}: contraste do valor >= 4,5`,contrast>=4.5,`ratio ${contrast}`);
 await p.context().close();
}
{
 const p=await page(390,{javaScriptEnabled:false,reducedMotion:'reduce'});
 await p.goto(BASE+'/capitulos/origem-do-universo/#origem-do-universo-expansao');
 const m=p.locator('[data-hubble-lesson]');await m.locator('.hubble-values summary').click();await m.locator('.hubble-solution summary').click();
 ok('Hubble sem JS: explicação, gráfico, tabela e resolução disponíveis',await m.locator('svg').isVisible()&&await m.locator('tbody tr').count()===5&&await m.locator('.hubble-solution p').isVisible());
 await p.context().close();
}

await browser.close();
console.log(`\n${pass} verificações OK, ${fails.length} falhas`);
if (fails.length) { console.log(fails.map((f) => ' - ' + f).join('\n')); process.exit(1); }
