import { initMotionPreference } from './motion-preference';
import { initExperience } from './experience';
import { initNav } from './nav';
import { initProgress } from './progress-ui';
import { initTheme } from './theme';
import { initHeader } from './header';
import { initMotion } from './motion';
import { initAmbient } from './ambient';
import { initSchool } from './school';
import { initGuesses } from './lab/common';
import { initReader } from './reader';
import { initScenes } from './scenes';

const instruments: [string, () => Promise<void>][] = [
  ['[data-light-exhibit]', async () => (await import('./light-exhibit')).initLightExhibit()],
  ['[data-orbit-exhibit]', async () => (await import('./orbit-exhibit')).initOrbitExhibit()],
  ['[data-expansion-exhibit]', async () => (await import('./expansion-exhibit')).initExpansionExhibit()],
  ['[data-transit-exhibit]', async () => (await import('./transit-exhibit')).initTransitExhibit()],
  ['[data-hr-exhibit]', async () => (await import('./hr-exhibit')).initHRExhibit()],
  ['[data-lens]', async () => (await import('./visual/lensing')).initLensing()],
  ['[data-solar-studio]', async () => (await import('./visual/solar-studio')).initSolarStudio()],
  ['[data-cmb]', async () => (await import('./cmb')).initCmb()],
  ['[data-island="timeline"]', async () => (await import('./timeline')).initTimeline()],
  ['[data-island="planets"]', async () => (await import('./planets')).initPlanets()],
  ['[data-island="compare"]', async () => (await import('./compare')).initCompare()],
  ['[data-island="stars"]', async () => (await import('./stars')).initStars()],
  ['[data-quiz]', async () => (await import('./quiz')).initQuizzes()],
  ['[data-island="glossary"]', async () => (await import('./glossary')).initGlossary()],
  ['[data-observatory]', async () => (await import('./lab')).initLab()],
  ['[data-mx]', async () => (await import('./micro/engine')).initMicro()],
  ['[data-cmbj]', async () => (await import('./cmb-journey')).initCmbJourney()],
  ['[data-sci-lab]', async () => (await import('./motion-lab')).initSciLab()],
  ['[data-journey]', async () => (await import('./journey')).initJourney()],
  ['[data-px]', async () => (await import('./photo-explorer')).initPhotoExplorer()],
  ['[data-story]', async () => (await import('./story')).initStories()]
];

/** Carrega apenas os instrumentos presentes; o leitor prepara os passos antes das cenas. */
async function boot(): Promise<void> {
  for (const init of [initMotionPreference, initExperience, initTheme, initSchool, initHeader, initNav, initProgress, initGuesses]) {
    try { init(); } catch (err) { console.error('[cosmos] falha ao iniciar', init.name, err); }
  }
  if (document.querySelector('.chapter-reader')) {
    try { initReader(); } catch (err) { console.error('[cosmos] leitor', err); }
  }
  // SSR controls must be bound before load completes, including on a cold connection.
  const skyButton = document.querySelector<HTMLButtonElement>('[data-hero-gl-enable]');
  const skyImage = document.querySelector<HTMLImageElement>('[data-nebula-plate]');
  if (skyButton && skyImage) {
    skyButton.hidden = false;
    skyButton.addEventListener('click', () => {
      const show = skyImage.hidden;
      if (show && !skyImage.src) skyImage.src = skyImage.dataset.src!;
      skyImage.hidden = !show;
      skyButton.setAttribute('aria-pressed', String(show));
      skyButton.textContent = show ? 'Ocultar nebulosa ilustrativa' : 'Mostrar nebulosa ilustrativa';
    });
    skyImage.addEventListener('error', () => {
      skyImage.hidden = true;
      skyImage.removeAttribute('src');
      skyButton.setAttribute('aria-pressed', 'false');
      skyButton.textContent = 'Tentar carregar a nebulosa';
    });
  }
  if (document.querySelector('[data-scene]')) {
    try { initScenes(); } catch (err) { console.error('[cosmos] instrumento', '[data-scene]', err); }
  }
  await Promise.all(instruments.filter(([selector]) => document.querySelector(selector)).map(async ([selector, init]) => {
    try { await init(); } catch (err) { console.error('[cosmos] instrumento', selector, err); }
  }));
  initAmbient();
  initMotion();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => void boot(), { once: true }); else void boot();
