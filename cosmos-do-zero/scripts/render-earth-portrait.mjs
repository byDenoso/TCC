// Regenerate the transparent 2D fallback from the same Earth model and shaders used on the site.
// Start the built site locally, then run: CHROMIUM=/path/to/chromium node scripts/render-earth-portrait.mjs [output.webp]
import { rolldown } from 'rolldown';
import { chromium } from 'playwright';
import sharp from 'sharp';
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const bundle = await rolldown({ input: 'scripts/render-earth-scene.ts', platform: 'browser' });
const { output } = await bundle.generate({ format: 'iife', name: 'EarthPortrait' });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
try {
  const page = await browser.newPage();
  await page.goto((process.env.BASE_URL ?? 'http://127.0.0.1:4321') + '/404.html', { waitUntil: 'domcontentloaded' });
  await page.addScriptTag({ content: output[0].code });
  const url = await page.evaluate(() => window.EarthPortrait.renderEarthPortrait());
  const portrait = Buffer.from(url.split(',')[1], 'base64');
  if (process.argv[2]) {
    await writeFile(resolve(process.argv[2]), portrait);
  } else {
    await Promise.all(['public/models/portraits/terra.webp', 'src/assets/planets/terra.webp'].map(path => writeFile(resolve(path), portrait)));
    const caption = Buffer.from('<svg width="1200" height="800" xmlns="http://www.w3.org/2000/svg"><text x="30" y="780" fill="#d1d9e4" font-family="sans-serif" font-size="22">Terra · mapa MODIS; oceanos, nuvens e iluminação ilustrativos</text></svg>');
    const poster = await sharp({ create: { width: 1200, height: 800, channels: 4, background: '#070c18' } })
      .composite([{ input: portrait, left: 216, top: 0 }, { input: caption, left: 0, top: 0 }]).webp({ quality: 88 }).toBuffer();
    const small = await sharp(poster).resize(600, 400).webp({ quality: 84 }).toBuffer();
    await Promise.all([writeFile('public/posters/earth.webp', poster), writeFile('public/posters/earth-small.webp', small)]);
    const manifestPath = 'public/posters/manifest.json';
    const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
    const earth = manifest.assets.find(row => row.name === 'earth');
    earth.origin = 'NASA MODIS July 2004 land map; browser render from scripts/render-earth-portrait.mjs; ocean color, clouds, atmosphere and lighting are illustrative';
    earth.caption = 'Terra · mapa MODIS; oceanos, nuvens e iluminação ilustrativos';
    earth.files = [['earth.webp', poster], ['earth-small.webp', small]].map(([file, bytes]) => ({ file, bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') }));
    await writeFile(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
  }
  console.log('Retrato e alternativas da Terra renderizados a partir do mapa MODIS e das camadas ilustrativas.');
} finally { await browser.close(); await bundle.close(); }
