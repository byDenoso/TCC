import { $, $$, setText } from './dom';
import { planets } from '../data/client';
import { compareInsight, compareRows, comparison } from '../lib/planets';
import { getParam, setParams } from '../lib/url-state';
import { readArt } from './planets';

export function initCompare(): void {
  const root = $('[data-island="compare"]');
  if (!root) return;
  const art = readArt();
  const a = $<HTMLSelectElement>('[data-compare-a]', root)!;
  const b = $<HTMLSelectElement>('[data-compare-b]', root)!;
  const find = (id: string) => planets.find((p) => p.id === id);
  const render = (url = true) => {
    const left = find(a.value), right = find(b.value);
    if (!left || !right) return;
    const cmp = comparison(left, right);
    ([['a', left, 0], ['b', right, 1]] as const).forEach(([side, p, i]) => {
      setText($(`[data-compare-name="${side}"]`, root), p.name);
      setText($(`[data-compare-col="${side}"]`, root), p.name);
      const img = $<HTMLImageElement>(`[data-compare-img="${side}"]`, root)!;
      const g = art[p.id]?.globe;
      if (g && img.getAttribute('src') !== g) img.src = g;
      img.style.width = `${cmp.diameters[i].toFixed(3)}%`;
    });
    const insight = compareInsight(left, right);
    setText($('[data-compare-insight]', root), insight);
    $('[data-compare-visual]', root)!.setAttribute('aria-label', `${left.name} e ${right.name} em escala de raio equatorial. ${insight}`);
    const tbody = $('[data-compare-values]', root)!;
    tbody.replaceChildren(...compareRows.map((r) => {
      const tr = document.createElement('tr');
      const th = document.createElement('th'); th.scope = 'row'; th.textContent = r.label; tr.append(th);
      for (const p of [left, right]) { const td = document.createElement('td'); td.textContent = r.value(p); tr.append(td); }
      return tr;
    }));
    if (url) setParams({ a: a.value === 'terra' ? null : a.value, b: b.value === 'jupiter' ? null : b.value });
  };
  const ok = (v: string | null) => (v && find(v) ? v : null);
  a.value = ok(getParam('a')) ?? a.value; b.value = ok(getParam('b')) ?? b.value;
  a.addEventListener('change', () => render()); b.addEventListener('change', () => render());
  $('[data-compare-swap]', root)!.addEventListener('click', () => { [a.value, b.value] = [b.value, a.value]; render(); });
  if (getParam('a') || getParam('b')) render(false);
  void $$;
}
