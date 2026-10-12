import { initNav } from './nav';
import { initProgress } from './progress-ui';
import { initTimeline } from './timeline';
import { initPlanets } from './planets';
import { initCompare } from './compare';
import { initStars } from './stars';
import { initQuizzes } from './quiz';
import { initGlossary } from './glossary';
import { initReader } from './reader';
import { initScenes } from './scenes';

/** Um único bundle: cada ilha só age se o seu elemento existir na página. */
function boot(): void {
  for (const init of [initNav, initProgress, initTimeline, initPlanets, initCompare, initStars, initQuizzes, initGlossary, initReader, initScenes]) {
    try { init(); } catch (err) { console.error('[cosmos] falha ao iniciar', init.name, err); }
  }
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true }); else boot();
