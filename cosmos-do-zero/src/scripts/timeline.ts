import { $, $$, behavior, setText } from './dom';
import { eras } from '../data/client';
import { getParam, setParams } from '../lib/url-state';
import { chapterUrl } from '../lib/url';
import { pad2 } from '../lib/format';

export function initTimeline(): void {
  const root = $('[data-island="timeline"]');
  if (!root) return;
  const buttons = $$<HTMLButtonElement>('[data-era-index]', root);
  const visual = $('[data-timeline-visual]', root)!;
  const prev = $<HTMLButtonElement>('[data-era-prev]', root)!;
  const next = $<HTMLButtonElement>('[data-era-next]', root)!;
  let selected = 0;
  const render = (index: number, o: { focus?: boolean; scroll?: boolean; url?: boolean } = {}) => {
    selected = Math.max(0, Math.min(eras.length - 1, index));
    const era = eras[selected];
    buttons.forEach((b, i) => { b.setAttribute('aria-pressed', String(i === selected)); b.classList.toggle('active', i === selected); });
    visual.className = `timeline-visual ${era.visual}`;
    visual.dataset.era = String(selected);
    const image = $<HTMLImageElement>('[data-era-render]', root)!;
    const src = buttons[selected].dataset.renderSrc!;
    image.srcset = `${src.replace(/\.webp$/, '-small.webp')} 600w, ${src} 1200w`;
    image.src = src;
    image.alt = `Representação artística para ${era.title}; sem escala física.`;
    setText($('[data-era-render-note]', root), era.id === 'cmb' ? 'Render conceitual da luz antiga por IA · não é mapa CMB' : 'Render conceitual por IA · sem escala');
    const pos = `${pad2(selected + 1)} / ${pad2(eras.length)}`;
    setText($('[data-era-number]', root), pos); setText($('[data-era-position]', root), pos);
    setText($('[data-era-evidence]', root), era.evidence); setText($('[data-era-time]', root), era.time);
    setText($('[data-era-title]', root), era.title); setText($('[data-era-text]', root), era.text);
    $<HTMLAnchorElement>('[data-era-link]', root)!.href = chapterUrl(era.chapter);
    prev.disabled = selected === 0; next.disabled = selected === eras.length - 1;
    if (o.focus) buttons[selected].focus({ preventScroll: true });
    if (o.scroll) buttons[selected].scrollIntoView({ inline: 'nearest', block: 'nearest', behavior: behavior() });
    if (o.url !== false) setParams({ marco: selected === 0 ? null : String(selected + 1) });
  };
  buttons.forEach((b, i) => {
    b.addEventListener('click', () => render(i));
    b.addEventListener('keydown', (e) => {
      const step = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
      if (step) { e.preventDefault(); render(selected + step, { focus: true, scroll: true }); }
      else if (e.key === 'Home') { e.preventDefault(); render(0, { focus: true, scroll: true }); }
      else if (e.key === 'End') { e.preventDefault(); render(eras.length - 1, { focus: true, scroll: true }); }
    });
  });
  prev.addEventListener('click', () => render(selected - 1, { scroll: true }));
  next.addEventListener('click', () => render(selected + 1, { scroll: true }));
  const fromUrl = Number(getParam('marco'));
  render(Number.isInteger(fromUrl) && fromUrl >= 1 && fromUrl <= eras.length ? fromUrl - 1 : 0, { url: false });
}
