export const $ = <T extends Element = HTMLElement>(sel: string, root: ParentNode = document): T | null => root.querySelector<T>(sel);
export const $$ = <T extends Element = HTMLElement>(sel: string, root: ParentNode = document): T[] => [...root.querySelectorAll<T>(sel)];
export const setText = (el: Element | null, value: string): void => { if (el && el.textContent !== value) el.textContent = value; };
export const reducedMotion = (): boolean => matchMedia('(prefers-reduced-motion: reduce)').matches;
export const behavior = (): ScrollBehavior => (reducedMotion() ? 'auto' : 'smooth');
/** Executa quando o elemento chega perto da tela, ao receber foco/ponteiro ou, sem IntersectionObserver, imediatamente. */
export function lazyInit(node: Element | null, run: () => void): void {
  if (!node) return;
  let done = false;
  const go = () => { if (done) return; done = true; io?.disconnect(); run(); };
  let io: IntersectionObserver | undefined;
  node.addEventListener('focusin', go, { once: true });
  node.addEventListener('pointerdown', go, { once: true });
  if ('IntersectionObserver' in window) { io = new IntersectionObserver((e) => e.some((x) => x.isIntersecting) && go(), { rootMargin: '300px' }); io.observe(node); } else go();
}
