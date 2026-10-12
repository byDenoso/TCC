/** Tema claro (creme + azul-noite + laranja) ou escuro (céu noturno + creme + laranja). Padrão: o do sistema; a escolha fica salva. */
const KEY = 'cosmos-theme';
type Theme = 'light' | 'dark';
const system = (): Theme => (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
const current = (): Theme => (document.documentElement.dataset.theme as Theme | undefined) ?? system();

export function initTheme(): void {
  const buttons = [...document.querySelectorAll<HTMLButtonElement>('[data-theme-toggle]')];
  const sync = () => {
    const t = current();
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', t === 'dark' ? '#070b18' : '#fff8e7');
    for (const b of buttons) {
      b.setAttribute('aria-pressed', String(t === 'dark'));
      b.setAttribute('aria-label', t === 'dark' ? 'Usar tema claro' : 'Usar tema escuro');
      const label = b.querySelector('[data-theme-label]');
      if (label) label.textContent = t === 'dark' ? 'Claro' : 'Escuro';
      b.dataset.current = t;
    }
  };
  for (const b of buttons) b.addEventListener('click', () => {
    const next: Theme = current() === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem(KEY, next); } catch { /* sem armazenamento: vale só nesta visita */ }
    sync();
  });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    let stored: string | null = null;
    try { stored = localStorage.getItem(KEY); } catch { /* ignora */ }
    if (stored !== 'light' && stored !== 'dark') document.documentElement.dataset.theme = system();
    sync();
  });
  window.addEventListener('storage', (e) => {
    if (e.key === KEY || e.key === null) {
      document.documentElement.dataset.theme = e.newValue === 'light' || e.newValue === 'dark' ? e.newValue : system();
      sync();
    }
  });
  sync();
}
