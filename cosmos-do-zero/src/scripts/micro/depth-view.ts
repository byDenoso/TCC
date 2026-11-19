import { createStageSurface, type StagePaint } from '../stage-surface';
import { motionPreference } from '../motion-preference';

type Painter = (surface: StagePaint, id: string, value: number, phase: number) => boolean;
const painters = import.meta.glob<{ paint: Painter }>('./*-plates.ts');

function group(id: string, chapter: string) {
  if (id === 'sistema-solar-disco') return 'formation';
  if (chapter === 'terra-e-atmosfera' || chapter === 'sistema-solar') return 'planetary';
  if (chapter === 'galaxias-e-nebulosas' || chapter === 'origem-do-universo') return 'deep-sky';
  return 'stellar';
}

export function mountDepthView(root: HTMLElement) {
  const canvas = root.querySelector<HTMLCanvasElement>('[data-mx-depth]')!;
  const svg = root.querySelector<SVGSVGElement>('[data-mx-svg]')!;
  const toggle = root.querySelector<HTMLButtonElement>('[data-mx-diagram]')!;
  const id = root.dataset.mx!;
  const load = painters[`./${group(id, root.dataset.mxChapter!)}-plates.ts`];
  if (!load || new URLSearchParams(location.search).get('visual') === 'diagram') return;
  let painter: Painter | undefined, value = 0, phase = 1, preferDiagram = false, disposed = false;
  let currentMode: boolean | undefined;
  let lastFrame: HTMLCanvasElement | undefined, dissolve: Animation | undefined;
  let releaseTimer = 0;
  function clearFrame() {
    window.clearTimeout(releaseTimer);
    dissolve?.cancel(); dissolve = undefined;
    lastFrame?.remove(); lastFrame = undefined;
  }
  function saveFrame() {
    clearFrame();
    if (!currentMode || motionPreference.matches || !canvas.animate) return;
    const still = document.createElement('canvas');
    still.width = canvas.width; still.height = canvas.height;
    const copy = still.getContext('2d');
    if (!copy) return;
    copy.drawImage(canvas,0,0);
    still.setAttribute('aria-hidden','true');
    still.style.cssText='position:absolute;inset:0;width:100%;height:100%;pointer-events:none';
    canvas.after(still); lastFrame = still;
    releaseTimer = window.setTimeout(() => { clearFrame(); redraw(); }, 650);
  }
  function show(depth: boolean) {
    if (currentMode === depth) return;
    currentMode = depth;
    canvas.hidden = !depth;
    if (depth) svg.setAttribute('aria-hidden','true'); else svg.removeAttribute('aria-hidden');
    toggle.textContent = depth ? 'Ver diagrama' : 'Ver cena';
    root.dataset.mxView = depth ? 'depth' : 'diagram';
  }
  const surface = createStageSurface(canvas, redraw);
  if (!surface) return;
  function redraw() {
    if (!painter || disposed || !surface || preferDiagram) return;
    const rendered = surface.draw(s => painter!(s, id, value, phase));
    if (lastFrame && surface.loading) return;
    if (lastFrame && !dissolve) {
      if (rendered && !motionPreference.matches) {
        const animation = lastFrame.animate([{opacity:1},{opacity:0}], {duration:230,easing:'ease-out'});
        dissolve = animation;
        animation.onfinish = () => { if (dissolve === animation) clearFrame(); };
      } else clearFrame();
    }
    show(rendered);
    toggle.hidden = !rendered;
  }
  const switchView = () => {
    clearFrame();
    preferDiagram = !preferDiagram;
    if (preferDiagram) show(false); else redraw();
  };
  toggle.addEventListener('click', switchView);
  load().then(module => {
    if (!disposed) { painter = module.paint; redraw(); }
  }).catch(() => { if (!disposed) show(false); });
  return {
    draw(v: number, t: number) {
      if (v === value && t === phase) return;
      if (v !== value && root.dataset.mxKind !== 'range') saveFrame();
      value = v; phase = t; redraw();
    },
    dispose() { disposed = true; clearFrame(); surface.dispose(); toggle.removeEventListener('click',switchView); }
  };
}

