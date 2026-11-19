import type { StagePaint } from '../stage-surface';
import credits from '../../../assets/source/micro-hd/credits.json';

export const hd = '/renders/micro-hd/';
const worldAtlas = '/models/worlds-hd/';
const previous = new WeakMap<StagePaint, Map<string, string>>();

/** The HD and distant atlases both use 36 frames and a 2.4-radius camera. */
export function drawGlobe(s: StagePaint, name: string, x: number, y: number, width: number, frame = 0) {
  const atlas = width >= 64 ? worldAtlas : '/models/solar-turntable/';
  const key = atlas + name + '/';
  const index = ((Math.round(frame) % 36) + 36) % 36;
  const path = key + String(index).padStart(2, '0') + '.webp';
  let ready = previous.get(s);
  if (!ready) { ready = new Map(); previous.set(s, ready); }
  if (s.image(path)) ready.set(key, path);
  const displayed = ready.get(key);
  if (displayed) s.sprite(displayed, x, y, width);
}

export function skyBackdrop(s: StagePaint) {
  s.ctx.fillStyle = '#070c15';
  s.ctx.fillRect(0, 0, 640, 360);
  // A low-contrast crop from the offline Cycles render. Never used before stars form.
  s.sprite('/renders/lesson-depth/stars-far.webp', 320, 180, 640, 1138, .62);
}

/** Add a source once, when its material is first requested by this experiment. */
export function materialCredits(root: HTMLElement, surface: StagePaint): StagePaint {
  const seenPaths = new Set<string>();
  const listed = new Set<string>();
  const details = document.createElement('details');
  details.className = 'mx-detail-note';
  const title = document.createElement('summary');
  title.textContent = 'Materiais e créditos da cena';
  details.append(title);
  const cite = (path: string) => {
    if ((!path.startsWith(hd) && !path.startsWith(worldAtlas)) || seenPaths.has(path)) return;
    seenPaths.add(path);
    const file = path.startsWith(worldAtlas) ? path.slice(worldAtlas.length).split('/')[0] : path.slice(hd.length).replace(/(?:-\d+)?\.webp$/, '');
    const key = ['gigante','azul','branca'].includes(file) ? 'sol' : file === 'saturno-globo' ? 'saturno' : file;
    if (listed.has(key)) return;
    const entry = credits[key as keyof typeof credits];
    if (!entry) return;
    listed.add(key);
    if (!details.isConnected) root.querySelector('.mx-caption')?.after(details);
    const p = document.createElement('p');
    if (entry.page) {
      const source = document.createElement('a');
      source.href = entry.page; source.textContent = entry.credit; p.append(source);
    } else p.append(entry.credit);
    p.append(' · ' + entry.license + '. ' + entry.modification);
    details.append(p);
  };
  return { ...surface,
    image(path) { cite(path); return surface.image(path); },
    sprite(path, x, y, width, height, opacity) {
      cite(path); surface.sprite(path, x, y, width, height, opacity);
    }
  };
}

