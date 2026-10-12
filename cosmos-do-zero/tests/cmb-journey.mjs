/**
 * QA da experiência "A luz mais antiga" num navegador real (Chromium/Chrome via Playwright).
 * Uso: suba o servidor (npm run dev ou npm run preview) e rode
 *   CHROMIUM="C:/Program Files/Google/Chrome/Application/chrome.exe" BASE=http://localhost:4321 node tests/cmb-journey.mjs
 * Saída: capturas em docs/screenshots/cmb/ e um relatório JSON com tempos, quadros por segundo e verificações.
 */
import { chromium } from 'playwright';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';

const BASE = process.env.BASE ?? 'http://localhost:4321';
const OUT = 'docs/screenshots/cmb';
mkdirSync(OUT, { recursive: true });
const exe = [process.env.CHROMIUM].find((p) => p && existsSync(p));
const browser = await chromium.launch(exe ? { executablePath: exe } : {});
const report = { base: BASE, browser: exe ?? 'playwright-chromium', ua: '', runs: [], checks: [] };
const URL_ = (q = '') => `${BASE}/capitulos/origem-do-universo/${q}#origem-do-universo-primeira-luz`;
const ok = (name, pass, detail = '') => { report.checks.push({ name, pass, detail }); console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? ' — ' + detail : ''}`); };

async function frameRate(page, ms = 1500) {
  return page.evaluate((ms) => new Promise((res) => { let n = 0; const t0 = performance.now(); const f = () => { n++; if (performance.now() - t0 < ms) requestAnimationFrame(f); else res(Math.round((n * 1000) / ms)); }; requestAnimationFrame(f); }), ms);
}
async function focusScene(page) {
  await page.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; const r = document.querySelector('[data-cmbj]'); window.scrollTo(0, r.getBoundingClientRect().top + scrollY - 70); });
  await page.waitForSelector('[data-cmbj].is-ready', { timeout: 10000 });
}

for (const vp of [{ name: 'desktop', width: 1280, height: 800, dpr: 1 }, { name: 'mobile', width: 390, height: 844, dpr: 3, mobile: true }]) {
  for (const scheme of ['dark', 'light']) {
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: vp.dpr, isMobile: !!vp.mobile, hasTouch: !!vp.mobile, colorScheme: scheme });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    await page.goto(URL_(), { waitUntil: 'load' });
    report.ua ||= await page.evaluate(() => navigator.userAgent);
    await focusScene(page);
    const run = { viewport: vp.name, scheme, steps: [] };
    // primeiro clique depois de carregar: tempo até o botão refletir o estado e o próximo quadro ser pintado
    const firstClick = await page.evaluate(async () => {
      const b = document.querySelector('[data-cmbj-play]');
      const t0 = performance.now(); b.click();
      const pressed = b.getAttribute('aria-pressed') === 'true';
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      return { pressed, msToPaint: Math.round(performance.now() - t0) };
    });
    run.firstClick = firstClick;
    const dur = [3500, 7500, 9000];
    for (let i = 0; i < 3; i++) {
      if (i > 0) await page.click(vp.mobile ? '[data-cmbj-next]' : '[data-cmbj-next]');
      const fps = await frameRate(page);
      await page.waitForTimeout(dur[i]);
      const st = await page.evaluate(() => { const r = document.querySelector('[data-cmbj]'); return { step: r.dataset.step, url: location.search, time: r.querySelector('[data-cmbj-time]').textContent, temp: r.querySelector('[data-cmbj-temp]').textContent, scale: r.querySelector('[data-cmbj-scale]').textContent, lambda: r.querySelector('[data-cmbj-lambda]').textContent, band: r.querySelector('[data-cmbj-band]').textContent, changedVisible: getComputedStyle(r.querySelector('.cmbj-changed')).opacity }; });
      run.steps.push({ ...st, fps });
      const el = await page.$('[data-cmbj] .cmbj-scene');
      await el.screenshot({ path: `${OUT}/${vp.name}-${scheme}-${i + 1}-${st.step}.png` });
      if (i === 2) await (await page.$('[data-cmbj]')).screenshot({ path: `${OUT}/${vp.name}-${scheme}-componente.png` });
    }
    run.errors = errors;
    report.runs.push(run);
    // verificações deste contexto
    const last = run.steps[2];
    ok(`${vp.name}/${scheme}: URL da etapa 3`, last.url.includes('luz=3'), last.url);
    ok(`${vp.name}/${scheme}: hoje em micro-ondas`, last.band === 'micro-ondas' && /2,7 K/.test(last.temp), `${last.temp} · ${last.lambda} · ${last.band}`);
    ok(`${vp.name}/${scheme}: etapa B no infravermelho a ~3 000 K`, run.steps[1].band === 'infravermelho' && /2 970 K/.test(run.steps[1].temp), `${run.steps[1].temp} · ${run.steps[1].lambda}`);
    ok(`${vp.name}/${scheme}: sem erros de console`, errors.length === 0, errors.join(' | '));
    ok(`${vp.name}/${scheme}: primeiro clique responde`, firstClick.pressed && firstClick.msToPaint < 150, `${firstClick.msToPaint} ms até pintar`);
    // sem rolagem horizontal
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    ok(`${vp.name}/${scheme}: sem rolagem horizontal`, overflow <= 0, `${overflow}px`);
    await ctx.close();
  }
}

// pausa automática fora da tela e retomada ao voltar; pausa pelo botão não retoma sozinha
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  await page.goto(URL_('?luz=3'), { waitUntil: 'load' });
  await focusScene(page);
  await page.click('[data-cmbj-play]');
  await page.waitForTimeout(400);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(500);
  const away = await page.evaluate(() => document.querySelector('[data-cmbj-play]').getAttribute('aria-pressed'));
  await focusScene(page);
  await page.waitForTimeout(500);
  const back = await page.evaluate(() => document.querySelector('[data-cmbj-play]').getAttribute('aria-pressed'));
  ok('fora da tela: pausa sozinha', away === 'false', away);
  ok('de volta à tela: retoma sozinha', back === 'true', back);
  await page.click('[data-cmbj-play]');
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);
  await focusScene(page);
  await page.waitForTimeout(500);
  const manual = await page.evaluate(() => document.querySelector('[data-cmbj-play]').getAttribute('aria-pressed'));
  ok('pausa pelo botão: continua pausada ao voltar', manual === 'false', manual);
  await ctx.close();
}

// movimento reduzido: quadro estático equivalente em cada etapa, botão não anima
{
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, reducedMotion: 'reduce', colorScheme: 'light' });
  const page = await ctx.newPage();
  await page.goto(URL_('?luz=3'), { waitUntil: 'load' });
  await focusScene(page);
  const st = await page.evaluate(() => { const r = document.querySelector('[data-cmbj]'); r.querySelector('[data-cmbj-play]').click(); return { step: r.dataset.step, playing: r.querySelector('[data-cmbj-play]').getAttribute('aria-pressed'), temp: r.querySelector('[data-cmbj-temp]').textContent, changed: getComputedStyle(r.querySelector('.cmbj-changed')).opacity }; });
  ok('movimento reduzido: abre direto na etapa da URL', st.step === 'expansao', st.step);
  ok('movimento reduzido: não anima, mostra o estado final', st.playing === 'false' && /2,7 K/.test(st.temp) && st.changed === '1', JSON.stringify(st));
  await (await page.$('[data-cmbj] .cmbj-scene')).screenshot({ path: `${OUT}/reduzido-3-expansao.png` });
  // voltar de B para A sem animação: os elétrons têm de estar livres de novo
  await page.click('[data-cmbj-goto="1"]'); const inB = await page.evaluate(() => Number(document.querySelector('[data-cmbj]').dataset.bound));
  await page.click('[data-cmbj-goto="0"]'); const inA = await page.evaluate(() => Number(document.querySelector('[data-cmbj]').dataset.bound));
  ok('movimento reduzido: B mostra átomos e A volta a ter elétrons livres', inB > 0 && inA === 0, `presos em B: ${inB}, em A: ${inA}`);
  await ctx.close();
}

// teclado, verificação, persistência e recarga
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  await page.goto(URL_(), { waitUntil: 'load' });
  await focusScene(page);
  await page.focus('[data-cmbj-goto="0"]');
  await page.keyboard.press('ArrowRight');
  const afterKey = await page.evaluate(() => ({ step: document.querySelector('[data-cmbj]').dataset.step, focus: document.activeElement?.getAttribute('data-cmbj-goto'), outline: getComputedStyle(document.activeElement).outlineStyle }));
  ok('teclado: seta para a direita avança a etapa e leva o foco', afterKey.step === 'atomos' && afterKey.focus === '1', JSON.stringify(afterKey));
  ok('teclado: foco visível', afterKey.outline !== 'none', afterKey.outline);
  // responder: uma errada e as certas
  const boxes = await page.$$('[data-cmbj-check]');
  for (const box of boxes) {
    const right = Number(await box.getAttribute('data-right'));
    const n = (await box.$$('[data-cmbj-opt]')).length;
    await (await box.$(`[data-cmbj-opt="${(right + 1) % n}"]`)).click();
    await (await box.$(`[data-cmbj-opt="${right}"]`)).click();
  }
  const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('cosmos-v6-praticado') ?? '[]'));
  ok('verificação: acertar as perguntas grava o progresso', saved.includes('origem-do-universo-primeira-luz'), JSON.stringify(saved));
  await page.reload({ waitUntil: 'load' });
  await focusScene(page);
  const hist = await page.evaluate(() => { const h = document.querySelector('[data-cmbj-history]'); return { hidden: h.hidden, text: h.textContent, toc: document.querySelector('[data-toc] a[href="#origem-do-universo-primeira-luz"]')?.dataset.practiced }; });
  ok('recarga: histórico de acerto anterior aparece', !hist.hidden && /visita anterior/.test(hist.text), hist.text);
  ok('recarga: índice marca a seção praticada', hist.toc === 'true', String(hist.toc));
  // voltar pelo histórico do navegador: a URL da etapa não empilha histórico, então voltar sai da página
  await page.goto(`${BASE}/`, { waitUntil: 'load' });
  await page.goto(URL_('?luz=2'), { waitUntil: 'load' });
  await page.goBack({ waitUntil: 'load' });
  ok('histórico: voltar retorna à página anterior', new URL(page.url()).pathname === '/', page.url());
  await page.goForward({ waitUntil: 'load' });
  await page.waitForURL(/luz=2/); await page.waitForLoadState('load'); await page.waitForTimeout(300);
  await focusScene(page);
  const fwd = await page.evaluate(() => document.querySelector('[data-cmbj]').dataset.step);
  ok('histórico: avançar reabre a etapa da URL', fwd === 'atomos', fwd);
  await ctx.close();
}

await browser.close();
writeFileSync(`${OUT}/report.json`, JSON.stringify(report, null, 2));
const failed = report.checks.filter((c) => !c.pass).length;
console.log(`\n${report.checks.length - failed}/${report.checks.length} verificações passaram. Navegador: ${report.browser}`);
process.exit(failed ? 1 : 0);
