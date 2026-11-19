import { u } from '../lib/url';
import { isVisibleNm, planckShape, seenFrom, wavelengthRgb, type Galaxy, type HubblePoint } from '../lib/motion-lab';
import planckUrl from '../assets/photos/planck-cmb.webp?url';

export type SkyFrame =
  | { kind: 'luz'; nm: number; growth: number; phase: number }
  | { kind: 'expansao'; field: Galaxy[]; observer: { x: number; y: number }; scale: number; select(galaxy: Galaxy): void }
  | { kind: 'hubble'; sample: HubblePoint[]; count: number }
  | { kind: 'frio'; temperature: number; peak: number }
  | { kind: 'giro'; rings: number[]; stars: { ring: number; a: number }[]; dark: number };

type ImageSource = HTMLImageElement;
type Brush = CanvasRenderingContext2D;
const W = 640, H = 278;
const textures = {
  spiral: u('/renders/instruments-hd/m51.webp'),
  barred: u('/renders/instruments-hd/ngc1300.webp'),
  elliptical: u('/renders/instruments-hd/ngc1132.webp'),
  earth: u('/models/worlds-hd/compact/terra-solo/00.webp'),
  planck: planckUrl
};
type Texture = keyof typeof textures;
const required: Record<SkyFrame['kind'], Texture[]> = {
  luz: ['spiral', 'earth'], expansao: ['spiral', 'barred', 'elliptical'], hubble: ['spiral', 'barred', 'elliptical'],
  frio: ['planck'], giro: ['spiral']
};
const cache = new Map<Texture, Promise<ImageSource>>();
const format = (value: number, digits = 0) => value.toLocaleString('pt-BR', { maximumFractionDigits: digits });

function loadTexture(key: Texture): Promise<ImageSource> {
  const cached = cache.get(key);
  if (cached) return cached;
  const task = (async () => {
    const img = new Image();
    img.src = textures[key];
    await img.decode();
    return img;
  })().catch(error => { cache.delete(key); throw error; });
  cache.set(key, task);
  return task;
}

function sprite(g: Brush, img: ImageSource, x: number, y: number, width: number, height: number, angle = 0) {
  g.save();
  g.translate(x, y); g.rotate(angle);
  g.drawImage(img, -width / 2, -height / 2, width, height);
  g.restore();
}
function line(g: Brush, x: number, y: number, endX: number, endY: number, color: string) {
  g.beginPath(); g.moveTo(x, y); g.lineTo(endX, endY); g.strokeStyle = color; g.stroke();
}
const galaxies = ['spiral', 'barred', 'elliptical'] as const;

export class MotionSky {
  private images = new Map<Texture, ImageSource>();
  private ready = false;
  private disposed = false;
  private pick: ((x: number, y: number) => void) | undefined;
  private readonly click = (event: MouseEvent) => {
    const rect = this.canvas.getBoundingClientRect();
    if (rect.width && rect.height) this.pick?.((event.clientX - rect.left) * W / rect.width, (event.clientY - rect.top) * W / rect.width - this.sceneOffsetY);
  };
  private g: Brush | null;
  private caption: HTMLElement;
  private credit: HTMLElement;
  private measures: HTMLButtonElement;
  private diagram: HTMLElement;
  private sceneOffsetY = 0;
  private showDiagram(open: boolean) {
    this.diagram.hidden = !open;
    this.measures.setAttribute('aria-expanded', String(open));
    this.measures.textContent = open ? 'Ocultar medidas' : 'Ver medidas';
  }
  private readonly toggleDiagram = () => this.showDiagram(this.diagram.hidden);
  constructor(private host: HTMLElement, private canvas: HTMLCanvasElement) {
    this.measures = host.parentElement!.querySelector('[data-sci-measures]')!;
    this.diagram = host.parentElement!.querySelector('.sci-diagram')!;
    this.measures.addEventListener('click', this.toggleDiagram);
    try { this.g = canvas.getContext('2d'); } catch { this.g = null; }
    this.caption = host.querySelector('[data-sci-sky-value]')!;
    this.credit = host.closest('figure')!.querySelector('[data-sci-credit]')!;
    canvas.addEventListener('click', this.click);
    canvas.addEventListener('contextlost', this.fallback);
  }

  async load(kind: SkyFrame['kind'], redraw: () => void) {
    if (!this.g) return;
    try {
      const keys = required[kind];
      const sources = await Promise.all(keys.map(loadTexture));
      if (this.disposed || this.g.isContextLost?.()) return;
      keys.forEach((key, i) => this.images.set(key, sources[i]));
      this.ready = true;
      this.host.hidden = this.credit.hidden = this.measures.hidden = false;
      this.showDiagram(false);
      redraw();
    } catch { this.fallback(); }
  }
  private readonly fallback = () => {
    this.ready = false;
    this.host.hidden = this.credit.hidden = this.measures.hidden = true;
    this.showDiagram(true);
  };
  dispose() {
    this.disposed = true;
    this.measures.removeEventListener('click', this.toggleDiagram);
    this.canvas.removeEventListener('click', this.click);
    this.canvas.removeEventListener('contextlost', this.fallback);
    this.images.clear();
  }
  draw(f: SkyFrame) {
    if (!this.ready || !this.g || !this.host.clientWidth) return;
    const g = this.g;
    const w = Math.round(this.host.clientWidth * Math.min(devicePixelRatio || 1, 2));
    const h = Math.round(this.host.clientHeight * w / this.host.clientWidth);
    const worldHeight = h * W / w;
    this.sceneOffsetY = (worldHeight - H) / 2;
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w; this.canvas.height = h;
    }
    g.setTransform(w / W, 0, 0, w / W, 0, 0);
    g.fillStyle = '#091322'; g.fillRect(0, 0, W, worldHeight);
    g.translate(0, this.sceneOffsetY);
    const image = (key: Texture) => this.images.get(key)!;
    let caption: string;
    switch (f.kind) {
      case 'luz': {
        sprite(g, image('spiral'), 90, 148, 160, 115, -.34);
        sprite(g, image('earth'), 567, 141, 105, 105);
        const visible = isVisibleNm(f.nm);
        g.strokeStyle = visible ? 'rgb(' + wavelengthRgb(f.nm).join(',') + ')' : '#e9b797';
        g.setLineDash(visible ? [] : [5, 5]); g.lineWidth = 3;
        g.beginPath();
        for (let x = 146; x <= 522; x += 2) {
          const phase = (x - 146) * Math.PI * 2 / (38 * f.growth) - f.phase;
          const y = 145 + 22 * Math.sin(phase) - (x - 146) * .012;
          if (x === 146) g.moveTo(x, y); else g.lineTo(x, y);
        }
        g.stroke(); g.setLineDash([]);
        caption = 'Emissão 460 nm  →  recepção ' + format(f.nm) + ' nm';
        break;
      }
      case 'expansao': {
        // The camera is inclined over a periodic comoving plane.
        const project = (x: number, y: number) => {
          const perspective = 1 / (1 - y * .054);
          return { x: 320 + x * 82 * perspective, y: 138 + y * 39 * perspective, k: perspective };
        };
        const objects = f.field.map((galaxy, i) => {
          const [x, y] = seenFrom(galaxy, f.observer, f.scale);
          return { ...project(x, y), size: galaxy.size, i };
        }).sort((a, b) => a.y - b.y);
        this.pick = (x, y) => {
          let nearest: Galaxy | undefined;
          let best = 28;
          for (const obj of objects) {
            const distance = Math.hypot(obj.x - x, obj.y - y);
            if (distance < best) { nearest = f.field[obj.i]; best = distance; }
          }
          if (nearest) f.select(nearest);
        };
        for (const obj of objects) {
          const s = 56 * obj.k * obj.size;
          if (obj.y < -this.sceneOffsetY - s || obj.y > H + this.sceneOffsetY + s || obj.x < -s || obj.x > W + s) continue;
          const photo = image(galaxies[obj.i % 3]);
          sprite(g, photo, obj.x, obj.y, s, s * photo.height / photo.width, Math.sin(obj.i) * .9);
        }
        g.beginPath(); g.ellipse(320, 138, 32, 20, 0, 0, Math.PI * 2);
        g.strokeStyle = '#f8ce91'; g.lineWidth = 1.8; g.stroke();
        caption = 'Distâncias relativas  × ' + format(f.scale, 2);
        break;
      }
      case 'hubble': {
        // Depth is distance. The angular directions are illustrative and fixed per object.
        const targets = f.sample.map((pt, i) => {
          const depth = 1 / (1 + pt.mpc / 125);
          const a = i * 2.39996;
          return { x: 180 + Math.cos(a) * 160 * depth, y: 135 + Math.sin(a) * 116 * depth, width: 85 * depth, i };
        });
        const latest = targets[f.count - 1];
        const focus = latest ?? targets[0];
        if (latest) {
          g.lineWidth = 1.2; line(g, 320, H + this.sceneOffsetY, latest.x, latest.y, '#ecd4a9a8');
        }
        targets.sort((a, b) => a.width - b.width).forEach(t => {
          g.globalAlpha = t.i < f.count ? 1 : .32;
          const photo = image(galaxies[t.i % 3]);
          sprite(g, photo, t.x, t.y, t.width, t.width * photo.height / photo.width, Math.sin(t.i) * .8);
        });
        g.globalAlpha = 1;
        if (latest) {
          g.beginPath(); g.arc(latest.x, latest.y, latest.width / 2 + 4, 0, Math.PI * 2);
          g.strokeStyle = '#ffe0aa'; g.stroke();
        }
        if (focus) {
          const photo = image(galaxies[focus.i % 3]);
          sprite(g, photo, 488, 132, 212, 212 * photo.height / photo.width);
          g.fillStyle = '#cddae7'; g.font = '16px system-ui'; g.textAlign = 'center';
          g.fillText(latest ? 'Última medida · ampliação' : 'Primeiro alvo · ampliação', 488, 264);
        }
        const pt = f.sample[f.count - 1];
        caption = pt ? format(pt.mpc, 1) + ' Mpc   ·   ' + format(pt.kms) + ' km/s' : 'Campo simulado · aguardando a primeira medida';
        break;
      }
      case 'frio': {
        // The observed sky is fixed. Only the modeled family of B_lambda curves evolves.
        const map = image('planck');
        g.save(); g.beginPath(); g.ellipse(128, 128, 103, 53, 0, 0, Math.PI * 2); g.clip();
        sprite(g, map, 128, 128, 225, 127); g.restore();
        for (let layer = 9; layer >= 0; layer--) {
          const t = f.temperature * Math.pow(1.15, layer);
          const y0 = 222 - layer * 6;
          const offset = layer * 3.8;
          g.beginPath(); g.moveTo(248 + offset, y0);
          for (let j = 0; j <= 100; j++) {
            const nm = 100 * Math.pow(30000, j / 100);
            g.lineTo(248 + offset + j * 3.05, y0 - 109 * planckShape(nm, t));
          }
          g.lineTo(553 + offset, y0); g.closePath();
          g.fillStyle = '#0d2133'; g.fill();
          g.strokeStyle = layer ? 'rgba(126,183,196,' + (.68 - layer * .04) + ')' : '#ffcf92';
          g.lineWidth = layer ? 1 : 2.6; g.stroke();
        }
        g.fillStyle = '#cddae7'; g.font = '16px system-ui'; g.textAlign = 'center';
        g.fillText('Planck · céu observado', 128, 252);
        g.fillText('Espectros térmicos · modelo', 421, 252);
        caption = format(f.temperature, 2) + ' K   ·   pico ' + format(f.peak / 1000, 2) + ' µm';
        break;
      }
      case 'giro': {
        const cx = 322, cy = 146, radius = 184, tilt = .55;
        g.save(); g.translate(cx, cy); g.rotate(-.12); g.scale(1, tilt);
        if (f.dark) {
          const halo = g.createRadialGradient(0, 0, 65, 0, 0, 217);
          halo.addColorStop(0, '#0000'); halo.addColorStop(.8, 'rgba(93,176,192,' + f.dark * .22 + ')'); halo.addColorStop(1, '#0000');
          g.fillStyle = halo; g.fillRect(-220, -220, 440, 440);
        }
        sprite(g, image('spiral'), 0, 0, radius * 2, radius * 2);
        for (const ring of [1, 4, 8]) {
          const star = f.stars.find(point => point.ring === ring);
          if (!star) continue;
          const r = radius * f.rings[star.ring];
          const x = r * Math.cos(star.a), y = r * Math.sin(star.a);
          g.beginPath(); g.arc(0, 0, r, star.a - .42, star.a);
          g.lineWidth = 2.5; g.strokeStyle = '#ffd1a0'; g.stroke();
          g.beginPath(); g.ellipse(x, y, 3.4, 3.4 / tilt, 0, 0, Math.PI * 2);
          g.fillStyle = star.ring % 2 ? '#9bd5e8' : '#ffe0a2'; g.fill();
        }
        g.restore();
        caption = 'Órbitas de teste  ·  efeito do halo ' + format(f.dark * 100) + '%';
        break;
      }
    }
    if (this.caption.textContent !== caption) this.caption.textContent = caption;
  }
}

