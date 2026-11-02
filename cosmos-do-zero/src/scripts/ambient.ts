/** O movimento da moldura é decorativo e pode ser desligado sem afetar os experimentos. */
export function initAmbient(): void {
  const hero = document.querySelector<HTMLElement>('.hero-shell');
  const button = hero?.querySelector<HTMLButtonElement>('[data-ambient-toggle]');
  if (!hero || !button) return;
  const preference = matchMedia('(prefers-reduced-motion: reduce)');
  let paused = false;
  const sync = () => {
    hero.dataset.ambientPaused = String(paused || preference.matches);
    button.hidden = preference.matches;
    button.textContent = paused ? 'Retomar o céu animado' : 'Pausar o céu animado';
    if (paused || preference.matches) {
      const stars = hero.querySelector<HTMLElement>('.starfield');
      if (stars) stars.style.transform = '';
    }
  };
  button.addEventListener('click', () => { paused = !paused; sync(); });
  preference.addEventListener('change', sync);
  sync();
}
