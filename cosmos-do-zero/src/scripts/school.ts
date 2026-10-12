/** Escola: selos conquistados com experimentos, palpites e aulas. Guardados neste navegador. */
import { createLocalStore } from '../lib/progress';
import { PRIMARY_CHAPTER_IDS } from '../types';

const KEY = 'cosmos-v5-selos';
export const BADGES = [
  { id: 'palpite', icon: '✦', title: 'Primeiro palpite', how: 'Faça um palpite em qualquer experimento.' },
  { id: 'luz-antiga', icon: '◐', title: 'Leitor da luz antiga', how: 'Viaje até a luz mais antiga na Máquina do tempo.' },
  { id: 'sem-centro', icon: '✺', title: 'Sem centro', how: 'Mude de galáxia e deixe o espaço crescer.' },
  { id: 'hubble', icon: '⟋', title: 'Medidor de galáxias', how: 'Meça pelo menos 8 galáxias.' },
  { id: 'receita', icon: '◎', title: 'Cozinheiro cósmico', how: 'Experimente três receitas de Universo.' },
  { id: 'aula-galaxias-e-nebulosas', icon: '1', title: 'Endereço cósmico', how: 'Conclua a aula 1.' },
  { id: 'aula-origem-do-universo', icon: '2', title: 'Testemunha da expansão', how: 'Conclua a aula 2.' },
  { id: 'aula-misterios-do-cosmos', icon: '3', title: 'Detetive das evidências', how: 'Conclua a aula 3.' },
  { id: 'formado', icon: '★', title: 'Cosmologia do zero', how: 'Conclua as três aulas.' }
] as const;
type BadgeId = (typeof BADGES)[number]['id'];

let memory: BadgeId[] = [];
const read = (): BadgeId[] => { try { const v = JSON.parse(localStorage.getItem(KEY) || '[]'); if (Array.isArray(v)) memory = v.filter((x) => BADGES.some((b) => b.id === x)); } catch { /* memória */ } return memory; };
const save = (ids: BadgeId[]) => { memory = ids; try { localStorage.setItem(KEY, JSON.stringify(ids)); } catch { /* vale nesta visita */ } };

let toastHost: HTMLElement | null = null;
function toast(id: BadgeId): void {
  const b = BADGES.find((x) => x.id === id)!;
  if (!toastHost) {
    toastHost = document.createElement('div');
    toastHost.className = 'badge-toasts';
    toastHost.setAttribute('role', 'status');
    toastHost.setAttribute('aria-live', 'polite');
    document.body.append(toastHost);
  }
  const t = document.createElement('div');
  t.className = 'badge-toast';
  t.innerHTML = `<span class="badge-icon" aria-hidden="true"></span><span><small>Selo conquistado</small><strong></strong></span>`;
  t.querySelector('.badge-icon')!.textContent = b.icon;
  t.querySelector('strong')!.textContent = b.title;
  toastHost.append(t);
  setTimeout(() => t.classList.add('is-out'), 4200);
  setTimeout(() => t.remove(), 4800);
}

function paint(): void {
  const have = read();
  for (const list of document.querySelectorAll<HTMLElement>('[data-badges]')) {
    for (const li of list.querySelectorAll<HTMLElement>('[data-badge]')) {
      const on = have.includes(li.dataset.badge as BadgeId);
      li.dataset.earned = String(on);
      li.setAttribute('aria-label', `${li.querySelector('strong')?.textContent}: ${on ? 'conquistado' : 'ainda não conquistado'}`);
    }
    const c = list.querySelector('[data-badge-count]');
    if (c) c.textContent = `${have.length} de ${BADGES.length} selos`;
  }
}

export function award(id: BadgeId): void {
  const have = read();
  if (have.includes(id)) return;
  save([...have, id]);
  toast(id);
  paint();
}

export function initSchool(): void {
  paint();
  const progress = createLocalStore();
  const checkLessons = (done: string[]) => {
    for (const id of PRIMARY_CHAPTER_IDS) if (done.includes(id)) award(`aula-${id}` as BadgeId);
    if (PRIMARY_CHAPTER_IDS.every((id) => done.includes(id))) award('formado');
  };
  document.addEventListener('cosmos:guess', () => award('palpite'));
  document.addEventListener('cosmos:badge', (e) => award((e as CustomEvent<{ id: BadgeId }>).detail.id));
  document.addEventListener('cosmos:progress', (e) => { const d = (e as CustomEvent<{ done: string[] }>).detail.done; checkLessons(d); paintCourse(d); });
  checkLessons(progress.read());
  paintCourse(progress.read());
}

/** Trilha: estrelas acesas para aulas concluídas, a próxima pulsa; a linha avança junto. */
function paintCourse(done: string[]): void {
  const map = document.querySelector<HTMLElement>('[data-course-map]');
  if (!map) return;
  const ids = [...PRIMARY_CHAPTER_IDS] as string[];
  const next = ids.find((id) => !done.includes(id)) ?? 'desafio';
  let lit = 0;
  for (const li of map.querySelectorAll<HTMLElement>('[data-course-node]')) {
    const id = li.dataset.courseNode!;
    const state = done.includes(id) ? 'done' : id === next ? 'next' : 'todo';
    if (state === 'done') lit++;
    li.dataset.state = state;
    const label = li.querySelector('[data-course-state]');
    if (label) label.textContent = state === 'done' ? 'Concluída ✓' : state === 'next' ? (done.length ? 'Próxima aula' : 'Comece por aqui') : id === 'desafio' ? 'Teste o que aprendeu' : 'Ainda não visitada';
  }
  const path = map.querySelector<SVGPathElement>('[data-course-progress]');
  if (path) {
    // fração do traçado até a última estrela acesa (as estrelas ficam sobre a curva)
    const xs = [150, 516, 900, 1104];
    let frac = 0;
    if (lit > 0) {
      const target = xs[Math.min(lit, 3)], total = path.getTotalLength();
      let best = 0, err = Infinity;
      for (let k = 0; k <= 200; k++) { const d = (total * k) / 200, e = Math.abs(path.getPointAtLength(d).x - target); if (e < err) { err = e; best = d; } }
      frac = best / total;
    }
    path.style.strokeDashoffset = String(1 - frac);
  }
}
