/**
 * Leia a imagem: troca de imagem, pontos explicativos, zoom e arraste.
 * Nada se move sozinho: toda mudança de enquadramento responde a um toque, clique ou tecla.
 * O arraste horizontal move a imagem; o vertical continua rolando a página no toque (touch-action: pan-y).
 */
import { clampView, coverSize, focusOn, zoomAbout, type ViewBox, type ViewState } from '../lib/photo-view';
import { motionPreference } from './motion-preference';

interface Panel {
  root: HTMLElement; view: HTMLElement; canvas: HTMLElement; ratio: number;
  spots: HTMLButtonElement[]; annotations: SVGPathElement[]; texts: { title: string; text: string }[];
  box: ViewBox; state: ViewState; active: number;
  count: HTMLElement | null; title: HTMLElement | null; text: HTMLElement | null;
}

export function initPhotoExplorer(): void {
  const root = document.querySelector<HTMLElement>('[data-px]');
  if (!root) return;
  const tabs = [...root.querySelectorAll<HTMLButtonElement>('[data-px-tab]')];
  const panels: Panel[] = [...root.querySelectorAll<HTMLElement>('[data-px-panel]')].flatMap((el) => {
    const view = el.querySelector<HTMLElement>('[data-px-view]'), canvas = el.querySelector<HTMLElement>('[data-px-canvas]');
    if (!view || !canvas) return [];
    const items = [...el.querySelectorAll<HTMLLIElement>('[data-px-list] li')];
    return [{
      root: el, view, canvas, ratio: Number(el.dataset.pxRatio) || 1.5,
      spots: [...el.querySelectorAll<HTMLButtonElement>('[data-px-spot]')],
      annotations: [...el.querySelectorAll<SVGPathElement>('[data-px-annotation]')],
      texts: items.map((li) => { const strong = li.querySelector('strong')?.textContent ?? ''; return { title: strong.replace(/\.$/, ''), text: (li.textContent ?? '').slice(strong.length).trim() }; }),
      box: { vw: 0, vh: 0, cw: 0, ch: 0 }, state: { z: 1, tx: 0, ty: 0 }, active: 0,
      count: el.querySelector('[data-px-reading-count]'), title: el.querySelector('[data-px-reading-title]'), text: el.querySelector('[data-px-reading-text]')
    }];
  });
  if (panels.length === 0) return;

  const canAnimate = (p: Panel) => p.view.hasAttribute('data-px-in-view') && !document.hidden && !motionPreference.matches;
  const stopMotion = (p: Panel) => {
    p.canvas.classList.remove('is-gliding');
    p.annotations[p.active]?.removeAttribute('data-px-draw');
  };
  const apply = (p: Panel, animate: boolean) => {
    p.canvas.classList.toggle('is-gliding', animate && canAnimate(p));
    p.canvas.style.width = `${p.box.cw}px`; p.canvas.style.height = `${p.box.ch}px`;
    p.canvas.style.transform = `translate3d(${p.state.tx.toFixed(1)}px, ${p.state.ty.toFixed(1)}px, 0) scale(${p.state.z.toFixed(4)})`;
    p.canvas.style.setProperty('--px-z', p.state.z.toFixed(4));
    p.view.dataset.pxZoomed = String(p.state.z > 1.01);
  };
  const measure = (p: Panel) => {
    const vw = p.view.clientWidth, vh = p.view.clientHeight;
    if (vw === 0 || vh === 0) return false;
    p.box = { vw, vh, ...coverSize(vw, vh, p.ratio) };
    return true;
  };
  const focus = (p: Panel, animate: boolean) => {
    const spot = p.spots[p.active];
    const x = spot ? parseFloat(spot.style.left) : 50, y = spot ? parseFloat(spot.style.top) : 50;
    p.state = focusOn(x, y, p.state.z, p.box);
    apply(p, animate);
  };
  const select = (p: Panel, index: number, zoom: boolean, animate = true) => {
    const next = (index + p.spots.length) % p.spots.length;
    const draw = animate && next !== p.active && canAnimate(p);
    p.active = next;
    p.spots.forEach((s, k) => { s.setAttribute('aria-pressed', String(k === p.active)); s.classList.toggle('is-active', k === p.active); });
    p.annotations.forEach((annotation, k) => {
      annotation.toggleAttribute('hidden', k !== p.active);
      annotation.toggleAttribute('data-px-draw', draw && k === p.active);
    });
    const item = p.texts[p.active];
    if (p.count) p.count.textContent = `Ponto ${p.active + 1} de ${p.spots.length}`;
    if (p.title) p.title.textContent = item?.title ?? '';
    if (p.text) p.text.textContent = item?.text ?? '';
    if (zoom) p.state = { ...p.state, z: Math.max(p.state.z, 1.8) };
    focus(p, animate);
  };

  const show = (key: string) => {
    tabs.forEach((t) => t.setAttribute('aria-pressed', String(t.dataset.pxTab === key)));
    for (const p of panels) {
      const on = p.root.dataset.pxPanel === key;
      p.root.hidden = !on;
      if (on && measure(p)) select(p, p.active, false, false);
      if (!on) stopMotion(p);
    }
  };

  for (const p of panels) {
    p.root.querySelector<HTMLElement>('[data-px-tools]')?.removeAttribute('hidden');
    p.root.querySelector<HTMLElement>('[data-px-reading]')?.removeAttribute('hidden');
    p.root.querySelector<HTMLElement>('[data-px-list]')?.setAttribute('hidden', '');
    p.view.tabIndex = 0;
    p.view.setAttribute('role', 'group');
    p.view.setAttribute('aria-label', 'Imagem ampliável. Use os pontos numerados, os botões de zoom ou as setas do teclado.');
    p.spots.forEach((spot, k) => {
      spot.disabled = false;
      spot.addEventListener('click', () => select(p, k, true));
    });
    p.root.querySelectorAll<HTMLButtonElement>('[data-px-step]').forEach((b) => b.addEventListener('click', () => select(p, p.active + Number(b.dataset.pxStep), true)));
    p.root.querySelectorAll<HTMLButtonElement>('[data-px-zoom]').forEach((b) => b.addEventListener('click', () => {
      const kind = b.dataset.pxZoom;
      if (kind === 'reset') { p.state = clampView({ z: 1, tx: (p.box.vw - p.box.cw) / 2, ty: (p.box.vh - p.box.ch) / 2 }, p.box); apply(p, true); return; }
      p.state = zoomAbout(p.state, p.state.z * (kind === 'in' ? 1.5 : 1 / 1.5), p.box.vw / 2, p.box.vh / 2, p.box);
      apply(p, true);
    }));
    p.view.addEventListener('keydown', (event) => {
      const step = 70;
      const moves: Record<string, [number, number]> = { ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
      if (moves[event.key]) { p.state = clampView({ ...p.state, tx: p.state.tx + moves[event.key][0], ty: p.state.ty + moves[event.key][1] }, p.box); apply(p, false); event.preventDefault(); }
      else if (event.key === '+' || event.key === '=') { p.state = zoomAbout(p.state, p.state.z * 1.5, p.box.vw / 2, p.box.vh / 2, p.box); apply(p, true); event.preventDefault(); }
      else if (event.key === '-') { p.state = zoomAbout(p.state, p.state.z / 1.5, p.box.vw / 2, p.box.vh / 2, p.box); apply(p, true); event.preventDefault(); }
    });
    let drag: { id: number; x: number; y: number; tx: number; ty: number } | null = null;
    p.view.addEventListener('pointerdown', (event) => {
      if ((event.target as HTMLElement).closest('[data-px-spot]') || (event.pointerType === 'mouse' && event.button !== 0)) return;
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY, tx: p.state.tx, ty: p.state.ty };
      p.view.setPointerCapture(event.pointerId); p.view.classList.add('is-dragging');
    });
    p.view.addEventListener('pointermove', (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      p.state = clampView({ z: p.state.z, tx: drag.tx + event.clientX - drag.x, ty: drag.ty + event.clientY - drag.y }, p.box);
      apply(p, false);
    });
    const end = (event: PointerEvent) => { if (drag && event.pointerId === drag.id) { drag = null; p.view.classList.remove('is-dragging'); } };
    p.view.addEventListener('pointerup', end); p.view.addEventListener('pointercancel', end);
    if ('ResizeObserver' in window) new ResizeObserver(() => { if (!p.root.hidden && measure(p)) focus(p, false); }).observe(p.view);
    if ('IntersectionObserver' in window) new IntersectionObserver(([entry]) => {
      p.view.toggleAttribute('data-px-in-view', entry.isIntersecting);
      if (!entry.isIntersecting) stopMotion(p);
    }).observe(p.view);
  }

  document.addEventListener('visibilitychange', () => { if (document.hidden) panels.forEach(stopMotion); });
  motionPreference.addEventListener('change', () => { if (motionPreference.matches) panels.forEach(stopMotion); });
  tabs.forEach((tab) => tab.addEventListener('click', () => show(tab.dataset.pxTab ?? '')));
  root.querySelector<HTMLElement>('[data-px-tabs]')?.removeAttribute('hidden');
  root.dataset.pxReady = 'true';
  show(panels[0].root.dataset.pxPanel ?? '');
}
