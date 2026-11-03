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
  ['[data-story],[data-story-preview]', async () => (await import('./story')).initStories()]
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
  // Motion graphics (GSAP) e abertura em WebGL: carregados à parte; se falharem, a página continua igual.
  void import('./motion-gsap').then((m) => m.initGsapMotion()).catch((err) => console.error('[cosmos] motion', err));
  if (document.querySelector('.hero-shell')) void import('./hero-gl').then((m) => m.initHeroGl()).catch((err) => console.error('[cosmos] webgl', err));
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
