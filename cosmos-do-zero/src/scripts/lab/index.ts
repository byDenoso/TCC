import { qa } from './common';
import { getParam, setParams } from '../../lib/url-state';
import { initTempo } from './tempo';
import { initExpansao } from './expansao';
import { initHubble } from './hubble';
import { initReceita } from './receita';

const stations: Record<string, (root: HTMLElement) => void> = { tempo: initTempo, expansao: initExpansao, hubble: initHubble, receita: initReceita };

/** Observatório: cada estação é inicializada na primeira vez que fica visível (ou imediatamente se já estiver visível). */
export function initLab(): void {
  for (const root of qa<HTMLElement>(document, '[data-observatory]')) {
    const panels = qa<HTMLElement>(root, '[data-station]');
    const tabs = qa<HTMLButtonElement>(root, '[data-obs-tab]');
    const started = new Set<string>();
    const start = (name: string) => {
      if (started.has(name)) return;
      started.add(name);
      const panel = panels.find((p) => p.dataset.station === name);
      if (!panel) return;
      try { stations[name](panel); } catch (err) { console.error('[cosmos] falha no instrumento', name, err); }
    };
    if (!tabs.length) { panels.forEach((p) => start(p.dataset.station!)); continue; }
    const show = (name: string, focus = false, persist = true) => {
      tabs.forEach((t) => { const on = t.dataset.obsTab === name; t.setAttribute('aria-selected', String(on)); t.tabIndex = on ? 0 : -1; if (on && focus) t.focus(); });
      panels.forEach((p) => { p.hidden = p.dataset.station !== name; });
      start(name);
      if (persist) setParams({ lab: name === tabs[0].dataset.obsTab ? null : name });
    };
    tabs.forEach((t, i) => {
      t.addEventListener('click', () => show(t.dataset.obsTab!));
      t.addEventListener('keydown', (e) => {
        const k = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : e.key === 'Home' ? -i : e.key === 'End' ? tabs.length : 0;
        if (!k) return; e.preventDefault();
        show(tabs[e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : (i + k + tabs.length) % tabs.length].dataset.obsTab!, true);
      });
    });
    const fromUrl = getParam('lab');
    const hasParams = ['z', 'om', 'ol', 'h0'].some((k) => getParam(k) !== null);
    const initial = fromUrl && tabs.some((t) => t.dataset.obsTab === fromUrl) ? fromUrl : hasParams ? (getParam('z') !== null ? 'tempo' : 'receita') : tabs[0].dataset.obsTab!;
    show(initial, false, false);
  }
}
