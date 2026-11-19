import { $, $$, setText } from './dom';
import { planets } from '../data/client';
import { catalogFacts } from '../lib/planets';
import { getParam, setParams } from '../lib/url-state';
import { pad2 } from '../lib/format';
import type { PlanetId } from '../types';

import { mountWorldView } from './visual/world-view';

export function initPlanets(): void {
  const root = $('[data-island="planets"]');
  if (!root) return;
  const tabs = $$<HTMLButtonElement>('[data-planet]', $('[data-planet-tabs]', root)!);
  const stage = $('[data-planet-stage]', root)!;
  const img = $<HTMLImageElement>('[data-planet-img]', root)!;
  const ruler = $$<HTMLButtonElement>('[data-ruler]', root);
  const view = mountWorldView(root, stage, () => [img.dataset.planet ?? 'terra']);
  const render = (id: PlanetId, o: { url?: boolean } = {}) => {
    const index = planets.findIndex((p) => p.id === id);
    const p = planets[index];
    if (!p) return;
    tabs.forEach((t) => t.setAttribute('aria-pressed', String(t.dataset.planet === id)));
    ruler.forEach((r) => { const active = r.dataset.ruler === id; r.classList.toggle('active', active); r.setAttribute('aria-pressed', String(active)); });
    img.dataset.planet = id; img.alt = `Ilustração artística de ${p.name}`;
    setText($('[data-planet-number]', root), pad2(index + 1));
    setText($('[data-planet-kicker]', root), `${pad2(index + 1)} / 08 · ${p.type}`);
    setText($('[data-planet-name]', root), p.name); setText($('[data-planet-description]', root), p.description);
    catalogFacts.forEach((f, i) => setText($(`[data-fact="${i}"]`, root), f.value(p)));
    setText($('[data-planet-composition]', root), p.composition); setText($('[data-planet-atmosphere]', root), p.atmosphere);
    setText($('[data-planet-temperature-note]', root), p.temperatureNote); setText($('[data-planet-fact]', root), p.fact);
    if (o.url !== false) setParams({ planeta: id === 'terra' ? null : id });
    view.setFrame(0);
  };
  tabs.forEach((b, i) => {
    b.addEventListener('click', () => { render(b.dataset.planet as PlanetId); });
    b.addEventListener('keydown', (e) => {
      if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(e.key)) return;
      e.preventDefault();
      const j = e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : (i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length;
      tabs[j].focus(); render(tabs[j].dataset.planet as PlanetId);
    });
  });
  ruler.forEach((r) => r.addEventListener('click', () => render(r.dataset.ruler as PlanetId)));
  const fromUrl = getParam('planeta');
  if (fromUrl && planets.some((p) => p.id === fromUrl)) render(fromUrl as PlanetId, { url: false });
  // Deep link vindo de outras partes da página (ex.: ?planeta=saturno#planetas)
  window.addEventListener('popstate', () => { const q = getParam('planeta'); render((q && planets.some((p) => p.id === q) ? q : 'terra') as PlanetId, { url: false }); });
}
