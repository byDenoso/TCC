import { $, $$, setText } from './dom';
import { planets } from '../data/client';
import { catalogFacts } from '../lib/planets';
import { getParam, setParams } from '../lib/url-state';
import { pad2 } from '../lib/format';
import type { PlanetId } from '../types';

type Art = Record<string, { src: string; w: number; h: number; globe: string }>;
export const readArt = (): Art => { try { return JSON.parse(document.getElementById('planet-art-data')?.textContent || '{}'); } catch { return {}; } };

export function initPlanets(): void {
  const root = $('[data-island="planets"]');
  if (!root) return;
  const art = readArt();
  const tabs = $$<HTMLButtonElement>('[data-planet]', $('[data-planet-tabs]', root)!);
  const stage = $('[data-planet-stage]', root)!;
  const img = $<HTMLImageElement>('[data-planet-img]', root)!;
  const ruler = $$<HTMLButtonElement>('[data-ruler]', root);
  let preloaded = false;
  const preload = () => { if (preloaded) return; preloaded = true; Object.values(art).forEach((a) => { const i = new Image(); i.src = a.src; }); };
  const render = (id: PlanetId, o: { url?: boolean } = {}) => {
    const index = planets.findIndex((p) => p.id === id);
    const p = planets[index];
    if (!p) return;
    tabs.forEach((t) => t.setAttribute('aria-pressed', String(t.dataset.planet === id)));
    ruler.forEach((r) => { const active = r.dataset.ruler === id; r.classList.toggle('active', active); r.setAttribute('aria-pressed', String(active)); });
    const a = art[id];
    if (a && img.dataset.planet !== id) {
      stage.classList.add('swap');
      const done = () => stage.classList.remove('swap');
      img.addEventListener('load', done, { once: true });
      img.addEventListener('error', done, { once: true });
      setTimeout(done, 400);
      img.src = a.src; img.width = a.w; img.height = a.h;
    }
    img.dataset.planet = id; img.alt = `Ilustração artística de ${p.name}`;
    setText($('[data-planet-number]', root), pad2(index + 1));
    setText($('[data-planet-kicker]', root), `${pad2(index + 1)} / 08 · ${p.type}`);
    setText($('[data-planet-name]', root), p.name); setText($('[data-planet-description]', root), p.description);
    catalogFacts.forEach((f, i) => setText($(`[data-fact="${i}"]`, root), f.value(p)));
    setText($('[data-planet-composition]', root), p.composition); setText($('[data-planet-atmosphere]', root), p.atmosphere);
    setText($('[data-planet-temperature-note]', root), p.temperatureNote); setText($('[data-planet-fact]', root), p.fact);
    if (o.url !== false) setParams({ planeta: id === 'terra' ? null : id });
    root.dispatchEvent(new CustomEvent('cosmos:worldselection'));
  };
  tabs.forEach((b, i) => {
    b.addEventListener('click', () => { preload(); render(b.dataset.planet as PlanetId); });
    b.addEventListener('pointerenter', preload, { once: true });
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
  void import('./visual/world-view').then(m=>m.initCatalogWorld(root,stage,()=>[img.dataset.planet??'terra']));
}
