import './plate.css';
import { u } from '../../lib/url';
import { animator, reduced, svg } from './common';
import { motionPreference } from '../motion-preference';

const paths = {
  star: '/renders/instruments-hd/solar-photosphere.webp',
  earth: '/models/worlds-hd/compact/terra-solo/00.webp',
  spiral: '/renders/instruments-hd/m51.webp',
  barred: '/renders/instruments-hd/ngc1300.webp',
  elliptical: '/renders/instruments-hd/ngc1132.webp',
  milkyWay: '/models/lab/barred-spiral.webp',
  plasma: '/renders/instruments-hd/early-light.webp',
} as const;

type Asset = keyof typeof paths;
type Paint = (ctx: CanvasRenderingContext2D, image: (key: Asset) => HTMLImageElement) => void;
const cache = new Map<Asset, Promise<HTMLImageElement>>();

export function loadPlateImage(key: Asset) {
  let pending = cache.get(key);
  if (!pending) {
    const image = new Image();
    image.src = u(paths[key]);
    pending = image.decode().then(() => image);
    cache.set(key, pending);
    pending.catch(() => cache.delete(key));
  }
  return pending;
}

/** One transparent raster layer in the same coordinate system as the accessible SVG. */
export function plate(stage: SVGSVGElement, keys: Asset[], paint: Paint, before: Element | null = null) {
  const { width, height } = stage.viewBox.baseVal;
  const layer = svg('foreignObject', { width, height, 'aria-hidden': 'true', 'pointer-events': 'none' });
  stage.insertBefore(layer, before);
  const canvas = document.createElement('canvas');
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(width * ratio);
  canvas.height = Math.round(height * ratio);
  canvas.style.cssText = 'display:block;width:100%;height:100%;pointer-events:none';
  layer.append(canvas);
  const ctx = canvas.getContext('2d');
  const images = new Map<Asset, HTMLImageElement>();
  let loading = false, visible = false, disposed = false;
  function refresh() {
    if (!ctx || disposed || !visible || document.hidden || images.size !== keys.length) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    paint(ctx, key => images.get(key)!);
    stage.dataset.labPlate = 'ready';
  }
  const observer = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    if (!visible || !ctx) return;
    if (loading) { refresh(); return; }
    loading = true;
    Promise.all(keys.map(loadPlateImage)).then(decoded => {
      if (disposed) return;
      keys.forEach((key, i) => images.set(key, decoded[i]));
      refresh();
    }).catch(() => { if (!disposed) stage.dataset.labPlate = 'fallback'; });
  });
  observer.observe(stage);
  const pagehide = (event: PageTransitionEvent) => { if (!event.persisted) dispose(); };
  function dispose() {
    disposed = true; observer.disconnect(); layer.remove(); delete stage.dataset.labPlate;
    document.removeEventListener('visibilitychange', refresh);
    window.removeEventListener('pagehide', pagehide);
  }
  document.addEventListener('visibilitychange', refresh);
  window.addEventListener('pagehide', pagehide);
  return { refresh, dispose };
}

export function disc(ctx: CanvasRenderingContext2D, image: HTMLImageElement, x: number, y: number, r: number, crop: number, tint?: string) {
  const side = Math.min(image.width, image.height) * crop;
  ctx.save();
  ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.clip();
  ctx.drawImage(image, (image.width-side)/2, (image.height-side)/2, side, side, x-r, y-r, 2*r, 2*r);
  if (tint) {
    ctx.fillStyle = tint; ctx.fillRect(x-r, y-r, 2*r, 2*r);
  }
  ctx.restore();
}

export const galaxies = ['spiral', 'barred', 'elliptical'] as const;
export function galaxy(ctx: CanvasRenderingContext2D, image: HTMLImageElement, x: number, y: number, radius: number, angle: number, tilt = 1) {
  ctx.save(); ctx.translate(x,y); ctx.rotate(angle); ctx.scale(1,tilt);
  const height = radius * image.naturalHeight / image.naturalWidth;
  ctx.drawImage(image,-radius,-height,2*radius,2*height); ctx.restore();
}

/** Two projected sky coordinates and a fixed depth for each comoving galaxy. */
export function galaxyGroup(stage: SVGSVGElement) {
  let scale = 1;
  const fallback = svg('g', { 'data-lab-body':'' }, stage);
  const bodies = Array.from({length:13}, (_, i) => ({
    x: (i*167 % 565)-282, y: (i*71 % 127)-63, radius: 20+(i%4)*5,
    node: svg('ellipse', { rx:7, ry:4, fill:'#c6bbce' }, fallback)
  }));
  const surface = plate(stage, [...galaxies], (ctx, img) => {
    for (const [i, body] of bodies.entries()) {
      galaxy(ctx, img(galaxies[i%3]), 320+body.x*scale, 80+body.y*scale, body.radius, i*.6);
    }
  });
  return (spacing: number) => {
    scale = spacing;
    for (const body of bodies) {
      body.node.setAttribute('cx', String(320+body.x*scale));
      body.node.setAttribute('cy', String(80+body.y*scale));
    }
    surface.refresh();
  };
}

/** Manual transport shares visibility, page lifecycle and reduced-motion rules with the observatory. */
export function phaseControl(stage: SVGSVGElement, button: HTMLButtonElement,
  tick: (ms: number) => boolean, step: () => void) {
  const label = button.textContent!;
  const animation = animator(stage, ms => {
    const more = tick(ms);
    if (!more) queueMicrotask(sync);
    return more;
  });
  function sync() {
    button.textContent = reduced() ? 'Avançar um passo' : animation.running() ? 'Pausar' : label;
    button.setAttribute('aria-pressed', String(animation.running()));
  }
  const stop = () => { animation.stop(); sync(); };
  button.addEventListener('click', () => {
    if (reduced()) step();
    else if (animation.running()) animation.stop();
    else animation.start();
    sync();
  });
  stage.addEventListener('cosmos:autopause', sync);
  motionPreference.addEventListener('change', stop);
  window.addEventListener('pagehide', event => {
    if (!event.persisted) {
      animation.dispose();
      motionPreference.removeEventListener('change', stop);
    }
  });
  sync(); button.hidden = false;
  return stop;
}
