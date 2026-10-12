import { $, $$, setText } from './dom';
import { clampMass, massLabel, stellarPath } from '../lib/stars';
import { format } from '../lib/format';
import { getParam, setParams } from '../lib/url-state';

export function initStars(): void {
  const root = $('[data-island="stars"]');
  if (!root) return;
  const slider = $<HTMLInputElement>('[data-star-mass]', root)!;
  const image = $('[data-star-render]', root)!;
  const presets = $$<HTMLButtonElement>('[data-mass]', root);
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
      const n = document.createElement('span'); n.textContent = String(i + 1).padStart(2, '0');
      const p = document.createElement('p'); p.textContent = name; li.append(n, p); return li;
    }));
    image.dataset.mass = String(m);
    presets.forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.mass) === m)));
    if (url) setParams({ massa: m === 1 ? null : String(m).replace('.', ',') });
  };
  slider.addEventListener('input', () => render());
  presets.forEach((b) => b.addEventListener('click', () => { slider.value = b.dataset.mass!; render(); }));
  const q = getParam('massa');
  if (q) slider.value = String(clampMass(Number(q.replace(',', '.'))));
  render(false);
}
