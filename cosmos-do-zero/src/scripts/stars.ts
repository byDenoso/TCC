import { $, $$, setText } from './dom';
import { clampMass, massLabel, stellarPath } from '../lib/stars';
import { format } from '../lib/format';
import { getParam, setParams } from '../lib/url-state';
import { drawStellar } from './micro/stellar';

/** Laboratório estelar: a massa escolhe o caminho; as etapas são desenhadas e podem ser percorridas passo a passo. */
export function initStars(): void {
  const root = $('[data-island="stars"]');
  if (!root) return;
  const slider = $<HTMLInputElement>('[data-star-mass]', root)!;
  const presets = $$<HTMLButtonElement>('[data-mass]', root);
  const svg = $<SVGSVGElement>('[data-star-svg]', root);
  const caption = $('[data-star-caption]', root);
  const play = $<HTMLButtonElement>('[data-star-play]', root);
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const layer = svg ? document.createElementNS('http://www.w3.org/2000/svg', 'g') : null;
  if (svg && layer) svg.append(layer);
  let step = 2, t = 1, playing = false, frame = 0, last = 0;

  const paint = () => {
    const m = clampMass(Number(slider.value));
    if (layer && caption) caption.textContent = drawStellar(layer, m, step, t);
    $$<HTMLButtonElement>('[data-star-step]', root).forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.starStep) === step)));
  };
  const setPlaying = (on: boolean) => {
    playing = on;
    if (!play) return;
    play.setAttribute('aria-pressed', String(on));
    setText($('[data-star-play-label]', play), on ? 'Pausar' : reduced.matches ? 'Avançar' : 'Animar a vida');
    $('.mx-ico', play)!.textContent = on ? '❚❚' : '▶';
  };
  const stop = () => { if (!playing) return; cancelAnimationFrame(frame); setPlaying(false); t = 1; paint(); };
  const tick = (now: number) => {
    if (!playing) return;
    t = Math.min(1, t + (last ? Math.min(64, now - last) : 16) / 1500); last = now;
    if (t >= 1) { if (step < 4) { step += 1; t = 0; } else { stop(); return; } }
    paint(); frame = requestAnimationFrame(tick);
  };
  const next = () => { stop(); step = step >= 4 ? 0 : step + 1; t = 1; paint(); };

  const render = (url = true) => {
    const m = clampMass(Number(slider.value));
    const path = stellarPath(m);
    setText($('[data-star-value]', root), massLabel(m, (n) => format(n)));
    setText($('[data-star-class]', root), path.category); setText($('[data-star-title]', root), path.title);
    setText($('[data-star-summary]', root), path.summary); setText($('[data-star-time]', root), path.time);
    setText($('[data-star-note]', root), path.note);
    const list = $('[data-star-path]', root)!;
    list.replaceChildren(...path.steps.map((name, i) => {
      const li = document.createElement('li');
      const b = document.createElement('button'); b.type = 'button'; b.dataset.starStep = String(i);
      const n = document.createElement('span'); n.textContent = String(i + 1).padStart(2, '0');
      const p = document.createElement('p'); p.textContent = name; b.append(n, p);
      b.addEventListener('click', () => { stop(); step = i; t = 1; paint(); });
      li.append(b); return li;
    }));
    presets.forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.mass) === m)));
    paint();
    if (url) setParams({ massa: m === 1 ? null : String(m).replace('.', ',') });
  };
  slider.addEventListener('input', () => render());
  presets.forEach((b) => b.addEventListener('click', () => { slider.value = b.dataset.mass!; render(); }));
  play?.addEventListener('click', () => {
    if (playing) { stop(); return; }
    if (reduced.matches) { next(); return; }
    if (step >= 4) step = 0;
    t = 0; last = 0; setPlaying(true); frame = requestAnimationFrame(tick);
  });
  $('[data-star-next]', root)?.addEventListener('click', next);
  $('[data-star-reset]', root)?.addEventListener('click', () => { stop(); step = 2; t = 1; paint(); });
  if (svg && 'IntersectionObserver' in window) new IntersectionObserver(([e]) => { if (!e.isIntersecting) stop(); }).observe(svg);
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
  const q = getParam('massa');
  if (q) slider.value = String(clampMass(Number(q.replace(',', '.'))));
  setPlaying(false);
  render(false);
}
