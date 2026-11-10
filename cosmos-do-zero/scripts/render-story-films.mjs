/**
 * Recria a mídia das aulas a partir dos palcos Three.js e das legendas do site.
 * CHROMIUM pode indicar outro binário. IDs opcionais limitam as aulas exportadas.
 * Sem BASE_URL, os mapas e modelos são servidos dos arquivos locais de public/.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createHash } from 'node:crypto';
import { chromium } from 'playwright';
import { rolldown } from 'rolldown';
import sharp from 'sharp';
import { STORIES, sampleStory, renderStory, storyProgress } from '../src/lib/story-scenes.ts';

const root = fileURLToPath(new URL('../', import.meta.url));
const outputDir = path.resolve(process.env.STORY_OUTPUT_DIR ?? path.join(root, 'public/media/stories'));
const localOrigin = 'http://story-render.invalid';
const base = (process.env.BASE_URL ?? localOrigin).replace(/\/$/, '');
const basePath = new URL(base).pathname.replace(/\/$/, '') + '/';
const captureUrl = base + '/__story-capture__/';
const duration = 20;
const fps = Number(process.env.STORY_FPS ?? 24);
if (!Number.isInteger(fps) || fps < 1 || fps > 60) throw new RangeError('STORY_FPS deve ser um inteiro entre 1 e 60.');
const ids = process.argv.length > 2 ? [...new Set(process.argv.slice(2))] : Object.keys(STORIES);
for (const id of ids) if (!Object.hasOwn(STORIES, id)) throw new RangeError('Aula desconhecida: ' + id);
await fs.mkdir(outputDir, { recursive: true });

const bundle = await rolldown({
  input: path.join(root, 'scripts/render-story-stage.ts'),
  platform: 'browser',
  transform: { define: { 'import.meta.env.BASE_URL': JSON.stringify(basePath) } }
});
const { output: [entry] } = await bundle.generate({ format: 'iife', name: 'StoryCapture', codeSplitting: false });
await bundle.close();

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM || undefined,
  args: ['--no-zygote', '--single-process', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']
});

const escapeXml = value => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;');
function wrap(value, maximum = 75) {
  const lines = [];
  let current = '';
  for (const word of value.split(' ')) {
    const next = current ? current + ' ' + word : word;
    if (next.length > maximum && current) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  }
  return [...lines, current].join('\n');
}
function startTime(phase) {
  return phase.at === 0 ? 0 : 3 + phase.at * 12;
}
const vttTime = seconds => '00:' + seconds.toFixed(3).padStart(6, '0');

function filmOverlay(id, progress) {
  const story = STORIES[id];
  const { phase } = sampleStory(id, progress);
  const overlay = renderStory(id, progress, 'film').replace('<svg ', '<svg x="160" y="60" width="960" height="540" ');
  const stages = story.phases.map((step, index) => {
    const selected = index === phase;
    const x = 64 + index * 388;
    return `<rect x="${x}" y="16" width="372" height="36" rx="8" fill="${selected ? '#154660' : '#08233d'}" stroke="${selected ? '#74dceb' : '#254661'}"/><text x="${x + 18}" y="40" font-size="17" fill="#eef6ff">${index + 1}. ${escapeXml(step.label)}</text>`;
  }).join('');
  return Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" font-family="Arial,Helvetica,sans-serif">${stages}${overlay}<text x="64" y="700" font-size="12" fill="#aec7db">COSMOS DO ZERO · ${escapeXml(story.limit)}</text></svg>`);
}
async function compositeFrame(id, progress, visual) {
  return sharp({ create: { width: 1280, height: 720, channels: 3, background: '#070c18' } })
    .composite([{ input: visual, left: 160, top: 60 }, { input: filmOverlay(id, progress) }])
    .png({ compressionLevel: 1 }).toBuffer();
}
async function encodeFilm(id, capture, firstFrame, finalFrame) {
  const target = path.join(outputDir, id + '.mp4');
  const temporary = target + '.tmp';
  const ffmpeg = spawn('ffmpeg', [
    '-y', '-hide_banner', '-loglevel', 'error', '-f', 'image2pipe', '-vcodec', 'png', '-r', String(fps),
    '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-threads', '2', '-preset', 'fast', '-crf', '22', '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart', '-f', 'mp4', temporary
  ], { stdio: ['pipe', 'ignore', 'pipe'] });
  const done = once(ffmpeg, 'close');
  // The child may fail before the first frame while Chromium is rendering it.
  void done.catch(() => {});
  let stderr = '';
  ffmpeg.stderr.on('data', chunk => { stderr += chunk; });
  ffmpeg.stdin.on('error', () => {});
  try {
    for (let index = 0; index < duration * fps; index++) {
      const seconds = index / fps;
      const progress = storyProgress(seconds);
      const frame = progress === 0 ? firstFrame : progress === 1 ? finalFrame : await compositeFrame(id, progress, await capture(progress, seconds));
      await new Promise((resolve, reject) => {
        ffmpeg.stdin.write(frame, error => error ? reject(error) : resolve());
      });
    }
    ffmpeg.stdin.end();
    const [status] = await done;
    if (status !== 0) throw new Error(stderr || 'ffmpeg saiu com código ' + status);
    await fs.rename(temporary, target);
  } catch (error) {
    ffmpeg.kill();
    await done.catch(() => {});
    await fs.rm(temporary, { force: true });
    throw error;
  }
}
async function describe(file) {
  const data = await fs.readFile(path.join(outputDir, file));
  return { file, bytes: data.length, sha256: createHash('sha256').update(data).digest('hex') };
}

try {
  const page = await browser.newPage({ viewport: { width: 980, height: 560 }, deviceScaleFactor: 1, reducedMotion: 'reduce' });
  const browserErrors = [];
  page.on('pageerror', error => browserErrors.push(error.message));
  page.on('console', message => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  await page.route(captureUrl, route => route.fulfill({
    contentType: 'text/html',
    body: '<!doctype html><html lang="pt-BR"><title>Exportação 3D</title><body style="margin:0"><main data-story-world style="width:960px;height:540px"></main></body></html>'
  }));
  if (!process.env.BASE_URL) {
    await page.route(localOrigin + '/models/**', route => {
      const request = new URL(route.request().url());
      return route.fulfill({ path: path.join(root, 'public', request.pathname) });
    });
  }
  await page.goto(captureUrl);
  await page.addScriptTag({ content: entry.code });
  const capture = async (progress, seconds) => {
    const data = await page.evaluate(({ progress, seconds }) => window.StoryCapture.captureStory(progress, seconds), { progress, seconds });
    if (browserErrors.length) throw new Error(browserErrors.join('\n'));
    if (!data.startsWith('data:image/png;base64,')) throw new Error('Quadro sem imagem PNG.');
    return Buffer.from(data.slice(data.indexOf(',') + 1), 'base64');
  };
  const provenanceFile = path.join(outputDir, 'provenance.json');
  const previous = await fs.readFile(provenanceFile, 'utf8').then(JSON.parse).catch(error => {
    if (error.code !== 'ENOENT') throw error;
    return {};
  });
  const media = previous.media ?? {};
  for (const id of ids) {
    const started = performance.now();
    console.log(`[${id}] preparando palco Three.js`);
    await page.evaluate(id => window.StoryCapture.openStory(id), id);
    await page.waitForFunction(() => document.querySelector('[data-story-world]').dataset.qualityPending !== 'true');
    const story = STORIES[id];
    const firstVisual = await capture(0, 0);
    const finalVisual = await capture(1, 15);
    const posters = [];
    // Redshift's continuous 2D alternative computes the current wavelengths instead of using stills.
    const posterPhases = id === 'origem-do-universo' ? story.phases.slice(0, 1) : story.phases;
    for (const [index, phase] of posterPhases.entries()) {
      const filename = id + (index === 0 ? '' : '-' + (index + 1)) + '.webp';
      const visual = index === 0 ? firstVisual : await capture(phase.at, startTime(phase));
      await sharp(visual).webp({ quality: 86 }).toFile(path.join(outputDir, filename));
      posters.push(filename);
    }
    console.log(`[${id}] ${posters.length} pôsteres; codificando vídeo ${fps} fps`);
    const [firstFrame, finalFrame] = await Promise.all([
      compositeFrame(id, 0, firstVisual), compositeFrame(id, 1, finalVisual)
    ]);
    await encodeFilm(id, capture, firstFrame, finalFrame);
    const starts = story.phases.map(startTime);
    const vtt = 'WEBVTT\n\n' + story.phases.map((phase, index) => {
      const end = starts[index + 1] === undefined ? duration : starts[index + 1] - 0.001;
      return `${vttTime(starts[index])} --> ${vttTime(end)}\n${wrap(phase.say)}\n`;
    }).join('\n');
    await fs.writeFile(path.join(outputDir, id + '.vtt'), vtt);
    media[id] = {
      fps,
      files: await Promise.all([id + '.mp4', id + '.vtt', ...posters].map(describe))
    };
    const provenance = {
      sources: ['src/scripts/visual/story-exhibit.ts', 'src/lib/story-scenes.ts'],
      duration,
      dimensions: [1280, 720],
      posterDimensions: [960, 540],
      captions: 'Arquivos VTT em português. As réguas e unidades são compostas sobre o quadro 3D.',
      models: 'Texturas observacionais quando disponíveis, modelos educativos e escalas descritas em cada cena.',
      references: [
        'https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/',
        'https://nssdc.gsfc.nasa.gov/planetary/factsheet/mercuryfact.html',
        'https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html',
        'https://science.nasa.gov/asset/webb/what-is-cosmological-redshift/'
      ],
      ids: Object.keys(STORIES).filter(chapter => Object.hasOwn(media, chapter)),
      media
    };
    await fs.writeFile(provenanceFile, JSON.stringify(provenance, null, 2) + '\n');
    console.log(`[${id}] ${duration}s, ${duration * fps} quadros; ${Math.round(media[id].files[0].bytes / 1024)} KiB; ${Math.round((performance.now() - started) / 1000)} s de exportação`);
  }
} finally {
  await browser.close();
}
