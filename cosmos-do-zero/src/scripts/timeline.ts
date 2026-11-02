import { motionPreference } from './motion-preference';
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
  const range=$<HTMLInputElement>('[data-era-range]',root)!;
  let selected = 0, transition=0;
  const detail=$<HTMLElement>('.timeline-detail',root)!;
  range.addEventListener('input',()=>render(Number(range.value)));
  const render = (index: number, o: { focus?: boolean; scroll?: boolean; url?: boolean } = {}) => {
    selected = Math.max(0, Math.min(eras.length - 1, index));
    const era = eras[selected];
    range.value=String(selected);range.setAttribute('aria-valuetext',`${selected+1} de ${eras.length}: ${era.title}, ${era.time}`);
    if(!motionPreference.matches){detail.classList.remove('is-changing');void detail.offsetWidth;detail.classList.add('is-changing');clearTimeout(transition);transition=window.setTimeout(()=>detail.classList.remove('is-changing'),400);}
    buttons.forEach((b, i) => { b.setAttribute('aria-pressed', String(i === selected)); b.classList.toggle('active', i === selected); });
    visual.className = `timeline-visual ${era.visual}`;
    visual.dataset.era = String(selected);
    const image = $<HTMLImageElement>('[data-era-render]', root)!;
    const src = buttons[selected].dataset.renderSrc!;
    visual.dataset.loading='true';
    const loaded=()=>{visual.dataset.loading='false';};image.onload=loaded;image.onerror=loaded;
    image.srcset = `${src.replace(/\.webp$/, '-small.webp')} 600w, ${src} 1200w`;
    image.src = src;
    if(image.complete)visual.dataset.loading='false';
    image.alt = buttons[selected].dataset.renderAlt!;
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
  range.disabled=false;root.dataset.timelineReady='true';
}
