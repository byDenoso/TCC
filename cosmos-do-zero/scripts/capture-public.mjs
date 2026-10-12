import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
const base = (process.env.BASE_URL ?? '').replace(/\/$/, '');
if (!/^https:\/\/bydenoso\.github\.io\/TCC\/cosmos-do-zero$/.test(base)) {
  throw new Error('Capture precisa apontar para a URL publica real do Cosmos do Zero.');
}
const browser = await chromium.launch({ headless: true });
try {
  await mkdir('docs/screenshots', { recursive: true });
  for (const [label, width, height] of [['desktop', 1440, 900], ['mobile', 390, 844]]) {
    const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    const response = await page.goto(`${base}/`, { waitUntil: 'networkidle', timeout: 60_000 });
    if (!response?.ok()) throw new Error(`Pagina publica falhou (${response?.status() ?? 'sem status'}).`);
    await page.screenshot({ path: `docs/screenshots/publicado-${label}.png`, fullPage: true });
    console.log(`Captura: ${label} ${response.url()}`);
    await context.close();
  }
} finally {
  await browser.close();
}
