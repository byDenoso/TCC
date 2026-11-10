// Rebuild the mobile fallback from the WebGL exhibit. Run against a built preview.
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { chromium } from 'playwright';

const url = process.env.SCALE_URL ?? 'http://127.0.0.1:4321/escalas/';
const output = process.argv[2] ?? 'public/media/scale-journey.mp4';
const fps = 30;
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM || undefined,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']
});

let encoder;
try {
  const page = await browser.newPage({ viewport: { width: 432, height: 900 }, deviceScaleFactor: 1 });
  await page.addInitScript(() => {
    const getContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, options) {
      const attributes = type === 'webgl2' && this.classList.contains('cosmos-volume')
        ? { ...options, preserveDrawingBuffer: true } : options;
      return getContext.call(this, type, attributes);
    };
  });
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-scale-enhanced]');
  await page.evaluate(() => {
    document.documentElement.style.scrollBehavior = 'auto';
    const first = document.querySelector('[data-scale-station]');
    window.scrollBy(0, first.getBoundingClientRect().top);
  });
  await page.waitForSelector('[data-scale-visual-stage][data-media="webgl"] canvas', { timeout: 30000 });
  const canvas = page.locator('[data-scale-canvas] canvas');
  encoder = spawn('ffmpeg', [
    '-hide_banner', '-loglevel', 'error', '-y', '-framerate', String(fps),
    '-f', 'image2pipe', '-vcodec', 'png', '-i', 'pipe:0',
    '-an', '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p', '-preset', 'medium', '-crf', '20', '-g', '3',
    '-movflags', '+faststart', output
  ], { stdio: ['pipe', 'inherit', 'inherit'] });
  const encoded = once(encoder, 'close');

  for (let i = 0; i <= fps * 4; i++) {
    const value = i / fps;
    await page.evaluate(progress => {
      const stations = [...document.querySelectorAll('[data-scale-station]')];
      const step = Math.min(stations.length - 2, Math.floor(progress));
      const a = stations[step].getBoundingClientRect().top;
      const b = stations[step + 1].getBoundingClientRect().top;
      window.scrollBy(0, a + (b - a) * (progress - step));
    }, value);
    await page.waitForFunction(progress =>
      Math.abs(Number(document.querySelector('[data-scale-visual-stage]').dataset.scalePosition) - progress) < .002, value);
    const png = await canvas.evaluate(element => element.toDataURL('image/png').split(',')[1]);
    if (!encoder.stdin.write(Buffer.from(png, 'base64'))) await once(encoder.stdin, 'drain');
  }
  encoder.stdin.end();
  const [code] = await encoded;
  if (code !== 0) throw new Error(`ffmpeg terminou com status ${code}`);
  console.log(`${output} · ${fps * 4 + 1} quadros a ${fps} fps`);
} finally {
  if (encoder?.exitCode === null) encoder.kill();
  await browser.close();
}
