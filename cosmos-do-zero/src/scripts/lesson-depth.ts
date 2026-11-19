import { u } from '../lib/url';

export const baked = (name: string) =>
  '/renders/lesson-depth/' + name + '.webp';
export const reel = (name: string) => '/renders/reel-cycles/' + name + '.webp';
export const portrait = (name: string) => '/models/portraits/' + name + '.webp';

export function localSprites(refresh: () => void) {
  const images = new Map<string, HTMLImageElement>();
  return (path: string) => {
    let image = images.get(path);
    if (!image) {
      image = new Image();
      images.set(path, image);
      image.onload = refresh;
      image.src = u(path);
    }
    return image.complete && image.naturalWidth ? image : null;
  };
}

type Sprites = ReturnType<typeof localSprites>;
type Paint = (
  ctx: CanvasRenderingContext2D,
  image: Sprites,
  w: number,
  h: number,
) => void;

/** Draw on state change only. Async image loads always repaint the latest state. */
export function depthCanvas(canvas: HTMLCanvasElement | null, paint: Paint) {
  if (!canvas) return () => {};
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    canvas.hidden = true;
    return () => {};
  }
  const width = canvas.width,
    height = canvas.height;
  let visible = false,
    frame = 0;
  const images = localSprites(refresh);
  function refresh() {
    if (visible && !document.hidden && !frame)
      frame = requestAnimationFrame(draw);
  }
  function draw() {
    frame = 0;
    if (!visible || document.hidden) return;
    ctx!.clearRect(0, 0, width, height);
    ctx!.save();
    paint(ctx!, images, width, height);
    ctx!.restore();
  }
  const observer = new IntersectionObserver((entries) => {
    visible = entries[entries.length - 1].isIntersecting;
    refresh();
  });
  observer.observe(canvas);
  document.addEventListener('visibilitychange', refresh);
  window.addEventListener('pagehide', (event) => {
    if (event.persisted) return;
    observer.disconnect();
    cancelAnimationFrame(frame);
    document.removeEventListener('visibilitychange', refresh);
  });
  return refresh;
}

/** Objects are ordered back to front. Depth scales both size and orbital parallax. */
export function eraObjects(
  ctx: CanvasRenderingContext2D,
  image: Sprites,
  era: string,
  x: number,
  y: number,
  size: number,
  phase: number,
) {
  const object = (
    path: string,
    dx: number,
    dy: number,
    radius: number,
    depth: number,
  ) => {
    const sprite = image(path);
    if (!sprite) return;
    const scale = 1 / (1.3 - depth * 0.3);
    const span = size * radius * scale;
    const left =
      x + size * dx + size * 0.06 * depth * Math.sin(phase) - span / 2;
    const height = (span * sprite.naturalHeight) / sprite.naturalWidth;
    ctx.drawImage(sprite, left, y + dy * size - height / 2, span, height);
  };
  switch (era) {
    case 'primordial':
    case 'nucleosynthesis':
    case 'cmb': {
      if (era === 'cmb') {
        for (let i = 0; i < 5; i++) {
          const dx = 0.33 * Math.cos(i * 2.4),
            dy = 0.23 * Math.sin(i * 2.4);
          const depth = 0.2 + i * 0.16,
            angle = phase + i * 1.7;
          object(baked('proton'), dx, dy, 0.15, depth);
          object(
            baked('electron'),
            dx + 0.08 * Math.cos(angle),
            dy + 0.035 * Math.sin(angle),
            0.06,
            depth + 0.04,
          );
        }
        break;
      }
      for (let i = 0; i < 12; i++) {
        const angle = i * 2.4 + phase * 0.15;
        const distance = Math.sqrt(i / 12) * 0.47;
        const path =
          i % 3 === 0
            ? 'electron'
            : era === 'nucleosynthesis' && i % 3 === 1
              ? 'helium'
              : 'proton';
        object(
          baked(path),
          distance * Math.cos(angle),
          distance * Math.sin(angle) * 0.65,
          0.09 + i * 0.012,
          i / 12,
        );
      }
      break;
    }
    case 'dark-ages':
    case 'reionization':
    case 'first-stars':
      object(reel('nebula'), 0, 0, 1.02, 0);
      if (era !== 'dark-ages') {
        object(baked('star'), -0.22, 0.12, 0.13, 0.45);
        object(baked('star'), 0.16, -0.1, 0.24, 0.85);
      }
      break;
    case 'solar-system':
      object(reel('orbits'), 0, 0, 1.08, 0.1);
      object(baked('star'), 0, 0, 0.15, 0.5);
      object(
        portrait('terra'),
        0.34 * Math.cos(phase),
        0.1 * Math.sin(phase),
        0.12,
        0.9,
      );
      break;
    case 'earth':
    case 'oxygen':
      object(portrait('terra'), -0.08, 0, 0.79, 0.35);
      object(
        portrait('lua'),
        0.34 * Math.cos(phase),
        0.15 * Math.sin(phase),
        0.2,
        0.9,
      );
      break;
    default:
      object(reel('cosmic-web'), 0, 0, 1.08, 0);
      object(reel('galaxy'), -0.24, -0.1, 0.35, 0.38);
      object(reel('galaxy'), 0.14, 0.08, 0.68, 0.88);
  }
}
