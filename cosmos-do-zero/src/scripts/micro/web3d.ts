import frames from '../../data/micro-frames.json';
import { u } from '../../lib/url';

interface Reference { paths: string[]; description: string }
const references: Record<string, Reference> = frames;

/** A imagem acompanha a etapa. O SVG continua mostrando os valores contínuos. */
export function mountMicroReference(root: HTMLElement) {
  const reference = references[root.dataset.mx!];
  const toggle = root.querySelector<HTMLButtonElement>('[data-mx-reference-toggle]');
  const panel = root.querySelector<HTMLElement>('[data-mx-reference-panel]');
  const image = panel?.querySelector<HTMLImageElement>('[data-mx-reference]');
  if (!reference || !toggle || !panel || !image || new URLSearchParams(location.search).get('visual') === 'diagram') return;

  let selected = 0;
  const update = (value: number) => {
    selected = Math.max(0, Math.min(reference.paths.length - 1, Math.round(value)));
    if (panel.hidden) return;
    const src = u(reference.paths[selected]);
    if (image.getAttribute('src') === src) return;
    image.src = src;
    const option = root.querySelector<HTMLElement>(`[data-mx-opt="${selected}"]`);
    image.alt = reference.paths.length > 1
      ? `Ilustração de referência · ${option?.textContent?.replace(/^\d+/, '').trim()}`
      : reference.description;
  };
  toggle.hidden = false;
  toggle.addEventListener('click', () => {
    panel.hidden = !panel.hidden;
    toggle.setAttribute('aria-expanded', String(!panel.hidden));
    update(selected);
  });
  return update;
}
