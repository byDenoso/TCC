import { journeyProgress, smooth } from '../lib/journey';
import { motionFactor, motionPreference } from './motion-preference';

/** Photography and pre-rendered plates. The camera moves the entire frame as a unit. */
export function initJourney(): void {
  const root = document.querySelector<HTMLElement>('.journey[data-journey]');
  const canvas = root?.querySelector<HTMLCanvasElement>('[data-journey-canvas]');
  const context = canvas?.getContext('2d', { alpha: false });
  if (!root || !canvas || !context || root.dataset.journeyReady) return;
  const stage = canvas.parentElement!;
  const steps = [...root.querySelectorAll<HTMLElement>('[data-journey-step]')];
  if (!steps.length) return;
  const ticks = [...root.querySelectorAll<HTMLElement>('[data-journey-tick]')];
  const when = root.querySelector<HTMLElement>('[data-journey-when]')!;
  const choice = root.querySelector<HTMLSelectElement>('[data-journey-select]')!;
  const pause = root.querySelector<HTMLButtonElement>('[data-journey-pause]')!;
  const missing = root.querySelector<HTMLElement>('[data-journey-missing]')!;
  const saveData = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData;
  const stills = steps.map(step => step.querySelector<HTMLImageElement>('[data-journey-still]')!);
  const cache = new Map<string, HTMLImageElement>();
  const failed = new Set<string>();
  let visible = false, paused = false, active = -1, progress = 0;
  let width = 0, height = 0, ratio = 1, request = 0, last = 0, clock = 0;

  function queue() {
    if (visible && !document.hidden && !request) request = requestAnimationFrame(paint);
  }
  function load(url: string) {
    if (failed.has(url)) return;
    let image = cache.get(url);
    if (!image) {
      image = new Image();
      image.decoding = 'async';
      image.onload = queue;
      image.onerror = () => { failed.add(url); cache.delete(url); queue(); };
      cache.set(url, image);
      image.src = url;
    }
    if (image.complete && image.naturalWidth) return image;
  }
  function imageAt(index: number) {
    const step = steps[index];
    const small = stills[index].getAttribute('src')!;
    const large = step.dataset.journeyLarge!;
    // Portrait screens crop the wide plates. Use the larger source when height requires it.
    const hd = Math.max(width, height * Number(step.dataset.journeyAspect)) * ratio > 900;
    if (!hd) return load(small) || (failed.has(small) ? load(large) : undefined);
    return load(large) || (failed.has(large) ? load(small) : undefined);
  }
  function resize() {
    const bounds = stage.getBoundingClientRect();
    width = Math.max(1, Math.round(bounds.width));
    height = Math.max(1, Math.round(bounds.height));
    ratio = Math.min(devicePixelRatio || 1, 2, 2400 / Math.max(width, height));
    const pixels = [Math.round(width * ratio), Math.round(height * ratio)];
    if (canvas!.width !== pixels[0] || canvas!.height !== pixels[1]) {
      canvas!.width = pixels[0]; canvas!.height = pixels[1];
    }
    queue();
  }
  function measure() {
    const centers = steps.map(step => { const r = step.getBoundingClientRect(); return r.top + r.height / 2; });
    const p = journeyProgress(centers, innerHeight * .58);
    const index = Math.round(p);
    progress = motionPreference.matches ? index : Math.floor(p) + smooth((p % 1 - .22) / .56);
    if (active !== index) {
      active = index;
      choice.value = String(index);
      when.textContent = steps[index].dataset.journeyShort || '';
      canvas!.setAttribute('aria-label', stills[index].alt);
      steps.forEach((step, i) => step.classList.toggle('is-active', i === active));
      ticks.forEach((tick, i) => tick.classList.toggle('is-active', i === active));
      for (const url of cache.keys()) {
        const nearby = steps.slice(Math.max(0,index - 1),index + 2);
        if (!nearby.some(s => s.dataset.journeyLarge === url || s.querySelector('img')?.getAttribute('src') === url)) cache.delete(url);
      }
    }
    queue();
  }
  function paint(now: number) {
    request = 0;
    if (!visible || document.hidden) return;
    const moving = !paused && !motionPreference.matches;
    if (moving && last) clock += Math.min(.08, (now - last) / 1000) * motionFactor();
    last = now;
    const first = Math.floor(progress), mix = progress - first;
    const a = imageAt(first);
    const b = mix > 0 ? imageAt(Math.min(first + 1, steps.length - 1)) : undefined;
    context!.setTransform(ratio, 0, 0, ratio, 0, 0);
    context!.globalAlpha = 1;
    context!.fillStyle = '#0a1018';
    context!.fillRect(0, 0, width, height);
    const draw = (image: HTMLImageElement, alpha: number, index: number) => {
      context!.globalAlpha = alpha;
      // A full-sky projection must retain both poles and both ends of the map.
      if (steps[index].dataset.journeyEra === 'cmb') {
        const compact = width <= 860;
        const span = Math.min(width * (compact ? .98 : .60), height * (compact ? .65 : 1.12));
        const h = span * image.naturalHeight / image.naturalWidth;
        context!.fillStyle = '#080c13';
        context!.fillRect(0, 0, width, height);
        context!.drawImage(image, width * (compact ? .5 : .66) - span / 2, height * (compact ? .36 : .45) - h / 2, span, h);
        return;
      }
      // Slow editorial pan with overscan, preserving the proportions of the observation.
      const phase = motionPreference.matches ? 0 : clock * .075;
      const scale = Math.max(width / image.naturalWidth, height / image.naturalHeight) * (1.022 + .011 * Math.sin(phase));
      const w = image.naturalWidth * scale, h = image.naturalHeight * scale;
      const x = (width - w) * (.5 + .09 * Math.sin(phase));
      context!.drawImage(image, x, (height - h) * .48, w, h);
    };
    if (a) draw(a, 1, first);
    if (b) draw(b, a ? mix : 1, first + 1);
    context!.globalAlpha = 1;
    const displayed = mix >= .5 ? b || a : a || b;
    const plate = displayed?.getAttribute('src') || '';
    if (canvas!.dataset.plate !== plate) canvas!.dataset.plate = plate;
    const unavailable = failed.has(steps[active].dataset.journeyLarge!) && failed.has(stills[active].getAttribute('src')!);
    missing.hidden = !unavailable;
    if (displayed && !saveData && active + 1 < steps.length && mix === 0 && !motionPreference.matches) imageAt(active + 1);
    if (moving && displayed) queue();
  }
  function jump(index: number) {
    if (!steps[index]) return;
    const r = steps[index].getBoundingClientRect();
    window.scrollBy({ top: r.top + r.height / 2 - innerHeight * .58, behavior: 'instant' });
    measure();
  }
  function anchor() {
    const index = steps.findIndex(step => '#' + step.id === location.hash);
    if (index >= 0) jump(index);
  }
  function stopFrame() { cancelAnimationFrame(request); request = 0; last = 0; }
  new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    root!.dataset.journeyVisible = String(visible);
    if (visible) { resize(); measure(); } else stopFrame();
  }).observe(stage);
  new ResizeObserver(() => { if (visible) { resize(); measure(); } }).observe(stage);
  choice.addEventListener('change', () => jump(Number(choice.value)));
  pause.addEventListener('click', () => {
    paused = !paused; last = 0;
    pause.setAttribute('aria-pressed', String(paused));
    pause.textContent = paused ? 'Retomar movimento' : 'Pausar movimento';
    if (paused) stopFrame(); else queue();
  });
  window.addEventListener('scroll', () => { if (visible) measure(); }, { passive: true });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopFrame(); else queue(); });
  motionPreference.addEventListener('change', () => { pause.hidden = motionPreference.matches; last = 0; if (visible) measure(); });
  window.addEventListener('hashchange', anchor);
  pause.hidden = motionPreference.matches;
  root.dataset.journeyReady = 'true';
  anchor();
}
