// Capturas da teia cósmica em WebGL (galaxias-e-nebulosas-teia-cosmica) em vários valores do controle.
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
const BASE = process.env.BASE ?? 'http://localhost:4321';
mkdirSync('docs/screenshots/web3d', { recursive: true });
const b = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
for (const [name, vp] of [['desktop', { width: 1280, height: 860 }], ['mobile', { width: 390, height: 844 }]]) {
  const p = await b.newPage({ viewport: vp, deviceScaleFactor: name === 'mobile' ? 2 : 1, colorScheme: 'light' });
  const errs = []; p.on('pageerror', (e) => errs.push(String(e))); p.on('console', (m) => m.type() === 'error' && errs.push(m.text()));
  await p.goto(`${BASE}/capitulos/galaxias-e-nebulosas/#galaxias-e-nebulosas-teia-cosmica`, { waitUntil: 'load' });
  const root = p.locator('[data-mx="galaxias-e-nebulosas-teia-cosmica"]');
  await root.scrollIntoViewIfNeeded();
  await p.waitForSelector('[data-mx="galaxias-e-nebulosas-teia-cosmica"] .mx-stage--gl', { timeout: 10000 }).catch(() => {});
  const gl = await root.locator('.mx-stage--gl').count();
  for (const v of ['0', '0.5', '1']) {
    await root.locator('[data-mx-range]').evaluate((r, v) => { r.value = v; r.dispatchEvent(new Event('input', { bubbles: true })); }, v);
    await p.waitForTimeout(900);
    await root.locator('.mx-stage').screenshot({ path: `docs/screenshots/web3d/${name}-${v}.png` });
  }
  const fps = await p.evaluate(() => new Promise((res) => { let n = 0; const t0 = performance.now(); const f = () => { n++; if (performance.now() - t0 < 1500) requestAnimationFrame(f); else res(Math.round(n / 1.5)); }; requestAnimationFrame(f); }));
  console.log(name, 'webgl', gl, 'fps', fps, 'erros', errs.length, errs.slice(0, 2).join(' | '));
  await p.close();
}
await b.close();
