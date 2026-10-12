import { chromium } from 'playwright';
const b = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
for (const [name, vp] of [['desktop', { width: 1280, height: 800 }], ['mobile', { width: 390, height: 844 }]]) {
  const p = await b.newPage({ viewport: vp, deviceScaleFactor: name === 'mobile' ? 3 : 1, colorScheme: 'dark' });
  const errs = []; p.on('pageerror', (e) => errs.push(String(e))); p.on('console', (m) => m.type() === 'error' && errs.push(m.text()));
  await p.goto('http://localhost:4321/capitulos/galaxias-e-nebulosas/', { waitUntil: 'load' });
  const st = await p.$('[data-station="tempo"]');
  await st.scrollIntoViewIfNeeded();
  const skip = await st.$('[data-guess-skip]'); if (skip && await skip.isVisible()) await skip.click();
  await p.waitForTimeout(1500);
  const has3d = await p.evaluate(() => { const h = document.querySelector('[data-t-3d]'); return { hidden: h?.hidden, canvas: !!h?.querySelector('canvas') }; });
  for (const [preset, wait] of [['0.5', 3500], ['1090', 4200], ['0', 1500]]) {
    await st.$(`[data-t-preset="${preset}"]`).then((e) => e.click());
    await p.waitForTimeout(wait);
    await (await st.$('.obs-grid')).screenshot({ path: `docs/screenshots/cmb/tempo3d-${name}-z${preset}.png` });
  }
  // pausar congela a cena; continuar volta a animar
  await st.$(`[data-t-preset="0.5"]`).then((e) => e.click()); await p.waitForTimeout(1200);
  const btn = await st.$(`[data-3d-play]`);
  await btn.click(); await p.waitForTimeout(1500); // a câmera desacelera até parar
  const a1 = await p.evaluate(() => document.querySelector('[data-3d-wave]').style.transform); await p.waitForTimeout(600);
  const a2 = await p.evaluate(() => document.querySelector('[data-3d-wave]').style.transform);
  const paused = await btn.getAttribute('aria-pressed');
  await btn.click(); await p.waitForTimeout(400);
  console.log(name, 'pausar:', paused === 'false' && a1 === a2 ? 'ok' : `FALHA ${paused} ${a1 !== a2}`, '| continuar:', await btn.getAttribute('aria-pressed'));
  console.log(name, JSON.stringify(has3d), 'erros:', errs.length, errs.slice(0, 3).join(' | '));
  await p.close();
}
await b.close();
