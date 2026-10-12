import { $, $$, setText } from './dom';
import { terms } from '../data/client';
import { countLabel, filterTerms, suggestTerms } from '../lib/glossary';
import { getParam, setParams } from '../lib/url-state';
import { CHAPTER_IDS, type ChapterId } from '../types';

export function initGlossary(): void {
  const root = $('[data-island="glossary"]');
  if (!root) return;
  const input = $<HTMLInputElement>('[data-glossary-input]', root)!;
  const entries = $$<HTMLDetailsElement>('[data-term-index]', root);
  const chips = $$<HTMLButtonElement>('[data-glossary-chip]', root);
  const empty = $('[data-glossary-empty]', root)!;
  let chapter: ChapterId | '' = '';
  const render = (url = true) => {
    const hits = new Set(filterTerms(terms, input.value, chapter));
    entries.forEach((node, i) => {
      const show = hits.has(Number(node.dataset.termIndex ?? i));
      node.hidden = !show;
      if (!show) node.open = false;
    });
    chips.forEach((c) => c.setAttribute('aria-pressed', String((c.dataset.glossaryChip ?? '') === chapter)));
    setText($('[data-glossary-count]', root), countLabel(hits.size));
    empty.hidden = hits.size > 0;
    const box = $('[data-glossary-suggest]', root);
    if (box) {
      const list = hits.size ? [] : suggestTerms(terms, input.value);
      box.replaceChildren(...list.map((i) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'glossary-suggest-btn'; b.textContent = terms[i].term; b.addEventListener('click', () => { input.value = terms[i].term; chapter = ''; render(); const entry = entries.find((e) => Number(e.dataset.termIndex) === i); if (entry) { entry.open = true; entry.querySelector('summary')?.focus(); } }); return b; }));
      box.closest<HTMLElement>('[data-glossary-suggest-wrap]')!.hidden = list.length === 0;
    }
    if (url) setParams({ q: input.value.trim() || null, jornada: chapter || null });
  };
  input.addEventListener('input', () => render());
  input.addEventListener('keydown', (e) => { if (e.key === 'Escape' && input.value) { input.value = ''; render(); } });
  chips.forEach((c) => c.addEventListener('click', () => { chapter = (c.dataset.glossaryChip ?? '') as ChapterId | ''; render(); }));
  $('[data-glossary-clear]', root)!.addEventListener('click', () => { input.value = ''; chapter = ''; render(); input.focus(); });
  const q = getParam('q'), j = getParam('jornada');
  if (q) input.value = q;
  if (j && (CHAPTER_IDS as readonly string[]).includes(j)) chapter = j as ChapterId;
  if (q || j) render(false);
}
