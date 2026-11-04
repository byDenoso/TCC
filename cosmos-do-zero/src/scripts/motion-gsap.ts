/** Entradas breves e paralaxe contida. A leitura mantém seu HTML e seu nome acessível. */
import { motionPreference, motionFactor } from './motion-preference';

export async function initGsapMotion(): Promise<void> {
  const hero = document.querySelector<HTMLElement>('.hero-shell');
  if (!hero) return; // As aulas usam as transições do motor didático existente.
  let modules: Promise<[typeof import('gsap'), typeof import('gsap/ScrollTrigger')]> | undefined;
  let revision = 0, entered = false, leaving = false;
  let revert = () => {};
  const apply = async () => {
    const request = ++revision;
    revert(); revert = () => {};
    if (motionPreference.matches || document.hidden || leaving || hero.dataset.ambientPaused === 'true' || hero.dataset.ambientSuspended === 'true') return;
    modules ??= Promise.all([import('gsap'), import('gsap/ScrollTrigger')]);
    const [{ gsap }, { ScrollTrigger }] = await modules;
    if (request !== revision) return;
    gsap.registerPlugin(ScrollTrigger);
    const k = motionFactor();
    document.documentElement.classList.add('gsap-on');
    const context = gsap.context(() => {
      if (!entered) {
        entered = true;
        // O texto fica legível desde o primeiro quadro. Sem letras soltas nem rotação.
        gsap.timeline({ defaults: { ease:'power2.out', duration:.7 } })
          .from(hero.querySelector('.hero-overline'), { opacity:.5, y:10*k }, 0)
          .from(hero.querySelector('h1'), { opacity:.5, y:18*k }, .06)
          .from(hero.querySelector('.hero-introduction'), { opacity:.5, y:14*k }, .12)
          .from(hero.querySelectorAll('.hero-actions > :not([hidden]), .hero-routes, .hero-explore'), { opacity:.5, y:12*k, stagger:.06 }, .18)
          .from(hero.querySelector('.cmb-hero'), { opacity:.6, duration:.85 }, .1)
          .from(hero.querySelectorAll('.hero-foot > *'), { opacity:.6, y:10*k, stagger:.05 }, .25);
      }
      if (matchMedia('(pointer:fine)').matches) {
        // Só alguns pixels de profundidade; nenhum bloqueio ou alteração da rolagem.
        const trigger = { trigger:hero, start:'top top', end:'bottom top', scrub:.5 };
        gsap.to(hero.querySelector('.hero-copy'), { y:-18*k, ease:'none', scrollTrigger:trigger });
        gsap.to(hero.querySelector('.cmb-hero'), { y:-30*k, ease:'none', scrollTrigger:trigger });
      }
    }, hero);
    revert = () => context.revert();
    ScrollTrigger.refresh();
  };
  const sync = () => { void apply().catch(err => console.error('[cosmos] movimento', err)); };
  motionPreference.addEventListener('change', sync);
  document.addEventListener('visibilitychange', sync);
  new MutationObserver(sync).observe(hero, { attributes:true, attributeFilter:['data-ambient-paused','data-ambient-suspended'] });
  window.addEventListener('pagehide', () => { leaving = true; ++revision; revert(); });
  window.addEventListener('pageshow', () => { leaving = false; sync(); });
  await apply();
}
