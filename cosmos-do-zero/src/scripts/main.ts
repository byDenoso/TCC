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
  // Reader still prepares the chapter first; scene assets and 3D remain lazy.
  // A abertura em WebGL só é carregada quando solicitada.
  const hero3d = document.querySelector<HTMLButtonElement>('[data-hero-gl-enable]');
  if (hero3d) {
    let renderer: typeof import('./hero-gl') | undefined;
    let pending = false;
    const updateButton = (active: boolean, failed = false) => {
      hero3d.removeAttribute('aria-busy');
      hero3d.setAttribute('aria-pressed', String(active));
      hero3d.textContent = active ? 'Desativar nebulosa 3D' :
        failed ? 'Nebulosa 3D indisponível · tentar novamente' : 'Ativar nebulosa 3D';
    };
    hero3d.hidden = false;
    updateButton(false);
    hero3d.closest('.hero-shell')?.addEventListener('cosmos:hero3dlost', event => {
      updateButton(false, event instanceof CustomEvent && event.detail?.failed === true);
    });
    hero3d.addEventListener('click', async () => {
      if (pending) return;
      if (hero3d.getAttribute('aria-pressed') === 'true') {
        renderer?.stopHeroGl();
        return;
      }
      pending = true;
      hero3d.setAttribute('aria-busy', 'true');
      hero3d.textContent = 'Preparando nebulosa 3D…';
      try {
        renderer ??= await import('./hero-gl');
        const ready = await renderer.initHeroGl();
        updateButton(ready, !ready);
      } catch (error) {
        console.warn('[cosmos] nebulosa 3D indisponível', error);
        updateButton(false, true);
      } finally {
        pending = false;
      }
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
