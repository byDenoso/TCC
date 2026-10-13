import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
const output = resolve('../../..', 'outputs/pilot'); mkdirSync(output, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || 'C:/Program Files/Google/Chrome/Application/chrome.exe', args: ['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'] });
const results = [];
try {
  for (const width of [390,1440]) {
    const p = await browser.newPage({ viewport: { width, height: 1000 }, colorScheme: 'dark' });
    const errors = []; p.on('pageerror', e=>errors.push(String(e)));
    await p.goto('http://127.0.0.1:4321/?lab=expansao#observatorio');
    const root = p.locator('[data-station="expansao"]');
    await root.locator('[data-guess-skip]').click();
    await root.locator('[data-e-range]').fill('1.45');
    await root.locator('[data-e-volume]').scrollIntoViewIfNeeded();
    await root.locator('.cosmos-volume').waitFor();
    await p.waitForTimeout(500);
    await root.screenshot({ path: resolve(output, `expansao-${width}.png`) });
    results.push({ width, viewport: await p.evaluate(()=>({ w:innerWidth,h:innerHeight,contexts:document.documentElement.dataset.cosmosContexts,overflow:document.documentElement.scrollWidth-innerWidth })), errors });
    await p.close();
  }
} finally { await browser.close(); }
writeFileSync(resolve(output,'pilot.json'),JSON.stringify(results,null,2)); console.log(results);
