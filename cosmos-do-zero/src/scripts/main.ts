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
import { initLab } from './lab';
import { initTheme } from './theme';
import { initCmb } from './cmb';
import { initHeader } from './header';
import { initMotion } from './motion';
import { initSchool } from './school';
import { initMicro } from './micro/engine';

/** Um único bundle: cada ilha só age se o seu elemento existir na página. */
function boot(): void {
  for (const init of [initTheme, initSchool, initHeader, initCmb, initNav, initProgress, initTimeline, initPlanets, initCompare, initStars, initQuizzes, initGlossary, initReader, initScenes, initLab, initMicro, initMotion]) {
    try { init(); } catch (err) { console.error('[cosmos] falha ao iniciar', init.name, err); }
  }
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true }); else boot();
