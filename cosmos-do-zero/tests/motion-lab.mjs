/**
 * QA do painel "Ciência em movimento" (home) em Chromium real.
 * Uso: npm run build && npm run serve   (porta 4321)   e, em outro terminal:
 *   BASE_URL=http://127.0.0.1:4321 CHROMIUM=/caminho/do/chromium node tests/motion-lab.mjs
 * Confere: abas, as cinco cenas, movimento (liga, pausa, para fora da tela), movimento reduzido,
 * texto com tamanho real legível, alvos de toque, texto dentro do quadro, ausência de NaN e de erros no console.
 */
import { chromium } from 'playwright';
import { existsSync } from 'node:fs';

const BASE = (process.env.BASE_URL ?? process.env.BASE ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const exe = [process.env.CHROMIUM].find((p) => p && existsSync(p));
const browser = await chromium.launch(exe ? { executablePath: exe, args: ['--no-sandbox'] } : { args: ['--no-sandbox'] });
const IDS = ['luz', 'expansao', 'hubble', 'frio', 'giro'];
let pass = 0, fail = 0;
const ok = (name, cond, detail = '') => { if (cond) pass++; else { fail++; console.log(`FAIL  ${name}${detail ? ' — ' + detail : ''}`); } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const snap = (page, id) => page.evaluate((id) => document.querySelector(`[data-sci-panel="${id}"] [data-sci-svg]`).innerHTML, id);

async function open(vp, { reduced = false, scheme = 'light' } = {}) {
  const touch = vp.width <= 430;
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1, isMobile: touch, hasTouch: touch, colorScheme: scheme, reducedMotion: reduced ? 'reduce' : 'no-preference', locale: 'pt-BR' });
  const page = await ctx.newPage();
  await page.addInitScript(theme => localStorage.setItem('cosmos-theme', theme), scheme);
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto(`${BASE}/`, { waitUntil: 'load' });
  await page.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; document.querySelector('#movimento').scrollIntoView({ block: 'start' }); window.scrollBy(0, 220); });
  await page.waitForSelector('[data-sci-lab].is-ready', { timeout: 15000 });
  return { ctx, page, errors };
}

for (const vp of [{ name: '390', width: 390, height: 844 }, { name: '768', width: 768, height: 1024 }, { name: '1280', width: 1280, height: 800 }]) {
  for (const reduced of [false, true]) {
    const label = `${vp.name}${reduced ? ' reduzido' : ''}`;
    const { ctx, page, errors } = await open(vp, { reduced });
    const tabs = page.locator('[data-sci-tab]');
    ok(`${label}: 5 abas visíveis`, (await tabs.count()) === 5 && (await page.locator('[data-sci-tabs]').isVisible()));
    ok(`${label}: só a primeira aba começa selecionada e só um painel visível`, (await page.evaluate(() => [...document.querySelectorAll('[data-sci-tab]')].map((t) => t.getAttribute('aria-selected')).join())) === 'true,false,false,false,false' && (await page.locator('[data-sci-panel]:visible').count()) === 1);
    ok(`${label}: sem rolagem horizontal`, await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth));

    for (const [i, id] of IDS.entries()) {
      await tabs.nth(i).click();
      await page.waitForTimeout(250);
      const panel = page.locator(`[data-sci-panel="${id}"]`);
      ok(`${label}/${id}: painel aparece e os outros somem`, (await panel.isVisible()) && (await page.locator('[data-sci-panel]:visible').count()) === 1);
      const info = await page.evaluate((id) => {
        const root = document.querySelector(`[data-sci-panel="${id}"]`), svg = root.querySelector('[data-sci-svg]'), stage = root.querySelector('[data-sci-stage]');
        const scale = stage.clientWidth / 480;
        const texts = [...svg.querySelectorAll('text.sci-t')].filter((t) => t.textContent.trim() && getComputedStyle(t).opacity !== '0');
        const real = texts.map((t) => parseFloat(getComputedStyle(t).fontSize) * scale);
        const outside = texts.filter((t) => { const b = t.getBBox(); return b.x < -0.5 || b.y < -0.5 || b.x + b.width > 480.5 || b.y + b.height > 300.5; }).map((t) => t.textContent);
        const small = [...root.querySelectorAll('button:not([hidden]), input')].filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.height < 43.5; }).map((e) => e.textContent.trim() || e.type);
        return { children: svg.querySelectorAll('*').length, ready: stage.classList.contains('is-ready'), nan: /NaN|undefined|Infinity/.test(svg.innerHTML), minReal: Math.min(...real), outside, small, read: root.querySelector('[data-sci-read]').textContent.trim().length, value: root.querySelector('[data-sci-value]').textContent.trim(), w: Math.round(stage.clientWidth) };
      }, id);
      ok(`${label}/${id}: desenho montado (${info.children} elementos)`, info.ready && info.children > 12);
      ok(`${label}/${id}: sem NaN/undefined no SVG`, !info.nan);
      ok(`${label}/${id}: texto do desenho ≥ 13 px reais (mín ${info.minReal.toFixed(1)})`, info.minReal >= 13);
      ok(`${label}/${id}: texto inteiro dentro do quadro`, info.outside.length === 0, info.outside.join(' | '));
      ok(`${label}/${id}: botões e barra com ≥ 44 px de altura`, info.small.length === 0, info.small.join(', '));
      ok(`${label}/${id}: texto de leitura e valor preenchidos`, info.read > 30 && info.value.length > 0, info.value);

      // barra de rolagem muda o desenho e o valor
      const before = await snap(page, id), valBefore = info.value;
      await page.evaluate((id) => { const r = document.querySelector(`[data-sci-panel="${id}"] [data-sci-range]`); r.value = '0.6'; r.dispatchEvent(new Event('input', { bubbles: true })); }, id);
      await page.waitForTimeout(120);
      const mid = await snap(page, id);
      const valMid = await page.locator(`[data-sci-panel="${id}"] [data-sci-value]`).textContent();
      ok(`${label}/${id}: mexer na barra muda o desenho`, mid !== before);
      ok(`${label}/${id}: mexer na barra muda o valor mostrado`, valMid !== valBefore, `${valBefore} → ${valMid}`);
      await page.evaluate((id) => { const r = document.querySelector(`[data-sci-panel="${id}"] [data-sci-range]`); r.value = '1'; r.dispatchEvent(new Event('input', { bubbles: true })); }, id);
      await page.waitForTimeout(60);
      ok(`${label}/${id}: extremo da barra sem NaN`, !/NaN|undefined|Infinity/.test(await snap(page, id)));
    }

    if (!reduced) {
      // movimento: cada cena anima sozinha na tela; pausar congela; sair da tela congela
      for (const [i, id] of IDS.entries()) {
        await tabs.nth(i).click();
        await page.click(`[data-sci-panel="${id}"] [data-sci-reset]`);
        await page.click(`[data-sci-panel="${id}"] [data-sci-play]`);
        const a = await snap(page, id); await sleep(700); const b = await snap(page, id);
        ok(`${label}/${id}: anima quando "Animar"`, a !== b);
        ok(`${label}/${id}: botão vira "Pausar"`, (await page.locator(`[data-sci-panel="${id}"] [data-sci-play-label]`).textContent()) === 'Pausar');
        await page.click(`[data-sci-panel="${id}"] [data-sci-play]`);
        const c = await snap(page, id); await sleep(500); const d = await snap(page, id);
        ok(`${label}/${id}: "Pausar" congela`, c === d);
      }
      await tabs.nth(0).click();
      await page.click('[data-sci-panel="luz"] [data-sci-play]');
      await page.evaluate(() => window.scrollTo(0, 0)); await sleep(400);
      const e = await snap(page, 'luz'); await sleep(500); const f = await snap(page, 'luz');
      ok(`${label}: para de animar fora da tela`, e === f);
      await page.evaluate(() => document.querySelector('#movimento').scrollIntoView({ block: 'start' })); await sleep(500);
      const g1 = await snap(page, 'luz'); await sleep(500); const g2 = await snap(page, 'luz');
      ok(`${label}: volta a animar ao reaparecer`, g1 !== g2);
    } else {
      // movimento reduzido: nada anda sozinho; "Avançar" avança um estado
      await tabs.nth(0).click();
      const a = await snap(page, 'luz'); await sleep(900); const b = await snap(page, 'luz');
      ok(`${label}: nada se move sozinho`, a === b);
      ok(`${label}: botão principal vira "Avançar"`, (await page.locator('[data-sci-panel="luz"] [data-sci-play-label]').textContent()) === 'Avançar');
      await page.click('[data-sci-panel="luz"] [data-sci-play]'); await sleep(150);
      ok(`${label}: "Avançar" muda o estado`, (await snap(page, 'luz')) !== b);
      ok(`${label}: nenhum quadro animado depois de Avançar`, await page.evaluate(async () => { const s = document.querySelector('[data-sci-panel="luz"] [data-sci-svg]').innerHTML; await new Promise((r) => setTimeout(r, 600)); return s === document.querySelector('[data-sci-panel="luz"] [data-sci-svg]').innerHTML; }));
    }

    // teclado nas abas
    await tabs.nth(0).click(); await tabs.nth(0).focus(); await page.keyboard.press('ArrowRight'); await page.waitForTimeout(150);
    ok(`${label}: seta → leva à próxima aba`, (await tabs.nth(1).getAttribute('aria-selected')) === 'true' && (await page.locator('[data-sci-panel="expansao"]').isVisible()));
    await page.keyboard.press('End'); await page.waitForTimeout(100);
    ok(`${label}: End vai à última aba`, (await tabs.nth(4).getAttribute('aria-selected')) === 'true');
    await page.keyboard.press('Home'); await page.waitForTimeout(100);
    ok(`${label}: Home volta à primeira aba`, (await tabs.nth(0).getAttribute('aria-selected')) === 'true');

    // expansão: trocar de galáxia muda a vista
    await tabs.nth(1).click(); await page.evaluate(() => { const r = document.querySelector('[data-sci-panel="expansao"] [data-sci-range]'); r.value = '0.5'; r.dispatchEvent(new Event('input', { bubbles: true })); });
    const act = page.locator('[data-sci-panel="expansao"] [data-sci-action]');
    ok(`${label}/expansao: botão "Ver de outra galáxia" aparece`, await act.isVisible());
    const v0 = await snap(page, 'expansao'); await act.click(); await sleep(reduced ? 150 : 950);
    ok(`${label}/expansao: trocar de galáxia muda a vista`, (await snap(page, 'expansao')) !== v0);
    ok(`${label}: nenhum erro no console`, errors.length === 0, errors.slice(0, 3).join(' | '));
    await ctx.close();
  }
}

// tema escuro: legibilidade (contraste do texto da figura contra o fundo do quadro) e ausência de erros
for (const vp of [{ width: 390, height: 844 }, { width: 1280, height: 800 }]) {
  const { ctx, page, errors } = await open(vp, { scheme: 'dark' });
  for (const [i, id] of IDS.entries()) {
    await page.locator('[data-sci-tab]').nth(i).click(); await page.waitForTimeout(250);
    const bad = await page.evaluate((id) => {
      const lum = (c) => { const m = c.match(/\d+(\.\d+)?/g).slice(0, 3).map(Number).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]; };
      const stage = document.querySelector(`[data-sci-panel="${id}"] [data-sci-stage]`);
      const bg = lum(getComputedStyle(document.documentElement).getPropertyValue('--surface').trim().startsWith('#') ? (() => { const h = getComputedStyle(document.documentElement).getPropertyValue('--surface').trim(); const n = parseInt(h.slice(1), 16); return `rgb(${n >> 16},${(n >> 8) & 255},${n & 255})`; })() : getComputedStyle(stage).backgroundColor);
      return [...stage.querySelectorAll('text.sci-t')].filter((t) => t.textContent.trim()).map((t) => { const l = lum(getComputedStyle(t).fill); const hi = Math.max(l, bg), lo = Math.min(l, bg); return { t: t.textContent, cr: (hi + 0.05) / (lo + 0.05) }; }).filter((x) => x.cr < 4.5);
    }, id);
    ok(`escuro ${vp.width}/${id}: contraste do texto ≥ 4,5:1`, bad.length === 0, JSON.stringify(bad.slice(0, 3)));
  }
  ok(`escuro ${vp.width}: nenhum erro no console`, errors.length === 0, errors.slice(0, 3).join(' | '));
  await ctx.close();
}

await browser.close();
console.log(`${pass} verificações OK, ${fail} falhas`);
process.exit(fail ? 1 : 0);
