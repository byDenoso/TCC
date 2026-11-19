import { u } from '../lib/url';

export interface StagePaint {
  ctx: CanvasRenderingContext2D;
  image(path: string): HTMLImageElement | null;
  backdrop(): void;
  sprite(path: string, x: number, y: number, width: number, height?: number, opacity?: number): void;
  label(text: string, x: number, y: number, opts?: { size?: number; color?: string; align?: CanvasTextAlign }): void;
}

const stars = Array.from({ length: 79 }, (_, n) => {
  const sample = (k: number) => {
    const v = Math.sin((n + 1) * k) * 18347.172;
    return v - Math.floor(v);
  };
  return { x: sample(64.7) * 640, y: sample(27.9) * 360, r: .28 + sample(17.2) * .7 };
});

/** One draw, in 640 × 360 logical units. Only asset loads and real size changes request a repaint. */
export function createStageSurface(canvas: HTMLCanvasElement, invalidate: () => void) {
  const ctx = canvas.getContext('2d', { alpha: false });
  if (!ctx) return null;
  const resources = new Map<string, HTMLImageElement>();
  const broken = new Set<string>();
  let failed = false, waiting = false, disposed = false, pending = 0;
  const invalidateSoon = () => {
    if (!disposed && !pending) pending = requestAnimationFrame(() => { pending = 0; invalidate(); });
  };
  const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(invalidateSoon);
  const host = canvas.parentElement!;
  observer?.observe(host);

  const image = (path: string) => {
    if (broken.has(path)) { failed = true; return null; }
    let asset = resources.get(path);
    if (!asset) {
      asset = new Image();
      resources.set(path, asset);
      asset.decoding = 'async';
      asset.onload = invalidateSoon;
      asset.onerror = () => { broken.add(path); invalidateSoon(); };
      asset.src = u(path);
    }
    if (asset.complete && asset.naturalWidth > 0) return asset;
    waiting = true;
    return null;
  };
  const surface: StagePaint = {
    ctx, image,
    backdrop() {
      const sky = ctx.createLinearGradient(0, 0, 0, 360);
      sky.addColorStop(0, '#111b2b'); sky.addColorStop(.65, '#080e19'); sky.addColorStop(1, '#030810');
      ctx.fillStyle = sky; ctx.fillRect(0, 0, 640, 360);
      ctx.fillStyle = '#aab9ca';
      ctx.beginPath();
      for (const star of stars) { ctx.moveTo(star.x + star.r, star.y); ctx.arc(star.x,star.y,star.r,0,2*Math.PI); }
      ctx.fill();
    },
    sprite(path, x, y, width, height = width, opacity = 1) {
      const asset = image(path);
      if (!asset || width <= 0 || height <= 0 || opacity <= 0) return;
      ctx.save(); ctx.globalAlpha *= Math.min(1, opacity);
      ctx.drawImage(asset, x - width / 2, y - height / 2, width, height);
      ctx.restore();
    },
    label(text, x, y, { size = 18, color = '#f3f5f5', align = 'left' } = {}) {
      ctx.save();
      ctx.font = `550 ${size}px "Inter Variable", system-ui, sans-serif`;
      ctx.textAlign = align; ctx.textBaseline = 'middle';
      ctx.fillStyle = color; ctx.shadowColor = '#03070e'; ctx.shadowBlur = 4;
      ctx.fillText(text, x, y); ctx.restore();
    }
  };
  return {
    surface,
    get loading() { return waiting && !failed; },
    draw(paint: (surface: StagePaint) => boolean) {
      const width = host.clientWidth, height = host.clientHeight;
      if (disposed || !width || !height) return false;
      const scale = Math.min(window.devicePixelRatio || 1, 2, 1440 / width);
      const w = Math.max(1, Math.round(width * scale)), h = Math.max(1, Math.round(height * scale));
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
      const fit = Math.min(w / 640, h / 360);
      ctx.save();
      ctx.fillStyle = '#09111d'; ctx.fillRect(0, 0, w, h);
      ctx.setTransform(fit, 0, 0, fit, (w - 640 * fit) / 2, (h - 360 * fit) / 2);
      ctx.beginPath(); ctx.rect(0, 0, 640, 360); ctx.clip();
      failed = false; waiting = false;
      try { return paint(surface) && !failed; }
      finally { ctx.restore(); }
    },
    dispose() {
      disposed = true; cancelAnimationFrame(pending); observer?.disconnect();
      for (const asset of resources.values()) { asset.onload = null; asset.onerror = null; }
      resources.clear();
    }
  };
}

