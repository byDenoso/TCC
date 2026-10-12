/** Cabeçalho que acompanha a rolagem, com barra de progresso da página. */
export function initHeader(): void {
  const shell = document.querySelector<HTMLElement>('.header-shell');
  if (!shell) return;
  const bar = shell.querySelector<HTMLElement>('[data-header-progress]');
  let ticking = false, stuck = false;
  const update = () => {
    ticking = false;
    const doc = document.documentElement;
    const y = doc.scrollTop || document.body.scrollTop;
    const next = y > 140;
    if (next !== stuck) { stuck = next; shell.classList.toggle('is-stuck', stuck); }
    const total = doc.scrollHeight - doc.clientHeight;
    if (bar) bar.style.transform = `scaleX(${total > 0 ? Math.min(1, Math.max(0, y / total)) : 0})`;
  };
  addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
  addEventListener('resize', update, { passive: true });
  update();
}
