import { motionPreference } from './motion-preference';
/** O movimento da moldura é decorativo e pode ser desligado sem afetar os experimentos. */
export function initAmbient(): void {
  const hero = document.querySelector<HTMLElement>('.hero-shell');
  const button = hero?.querySelector<HTMLButtonElement>('[data-ambient-toggle]');
  if (!hero || !button) return;
  const preference = motionPreference;
  const rect = hero.getBoundingClientRect();
  let paused = false, visible = rect.bottom > 0 && rect.top < innerHeight;
  const sync = () => {
    hero.dataset.ambientPaused = String(paused || preference.matches);
    hero.dataset.ambientSuspended = String(!visible || document.hidden);
    button.hidden = preference.matches;
    button.textContent = paused ? 'Retomar o céu animado' : 'Pausar o céu animado';
    if (paused || preference.matches) {
      const stars = hero.querySelector<HTMLElement>('.starfield');
      if (stars) stars.style.transform = '';
    }
  };
  button.addEventListener('click', () => { paused = !paused; sync(); });
  preference.addEventListener('change', sync);
  document.addEventListener('visibilitychange', sync);
  new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; sync(); }).observe(hero);
  sync();
}
