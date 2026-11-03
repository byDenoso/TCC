import { motionPreference, motionFactor } from '../motion-preference';
import { advanceDemonstration } from '../../lib/demonstration';
/**
 * Motor das microexperiências. Cada cena só é carregada quando chega perto da tela,
 * só uma anima por vez, e tudo para fora da tela ou com a aba escondida.
 * Com movimento reduzido, "Animar" mostra o estado final de cada passo, sem movimento.
 */
export interface Scene {
  /** Desenha as partes fixas. */
  init(svg: SVGSVGElement): void;
  /** Desenha o estado v (valor, passo ou opção) na fase t ∈ [0, 1] da animação; devolve a explicação. */
  draw(v: number, t: number): string;
  /** Texto do valor do controle deslizante. */
  value?(v: number): string;
  /** Duração (ms) de uma fase animada. */
  duration?: number;
  /** Controle deslizante: 'sweep' (padrão) anima o valor; 'time' anima o movimento no valor escolhido. */
  animate?: 'sweep' | 'time';
  /** Sincroniza movimentos auxiliares (como a câmera 3D) com o transporte da cena. */
  setPlaying?(playing: boolean): void;
  dispose?(): void;
}
import { visibleMotion } from '../visible-motion';
export type SceneMap = Record<string, () => Scene>;

const loaders: Record<string, () => Promise<{ scenes: SceneMap }>> = {
  'galaxias-e-nebulosas': () => import('./galaxias'),
  'origem-do-universo': () => import('./origem'),
  'misterios-do-cosmos': () => import('./misterios'),
  'vida-das-estrelas': () => import('./estrelas'),
  'sistema-solar': () => import('./sistema'),
  'terra-e-atmosfera': () => import('./terra')
};

const DONE_KEY = 'cosmos-v6-praticado';
export function practiced(): Set<string> {
  try { return new Set(JSON.parse(localStorage.getItem(DONE_KEY) ?? '[]') as string[]); } catch { return new Set(); }
}
function markPracticed(id: string): void {
  const s = practiced(); s.add(id);
  try { localStorage.setItem(DONE_KEY, JSON.stringify([...s])); } catch { /* sem armazenamento */ }
}

interface Runner { stop(): void; dispose(): void }
let running: Runner | null = null;
const mounted = new Set<Runner>();
const reducedQuery = motionPreference;

export function initMicro(): void {
  const roots = [...document.querySelectorAll<HTMLElement>('[data-mx]')];
  if (!roots.length) return;
  paintToc();
  const boot = (root: HTMLElement) => {
    if (root.dataset.mxBooted) return;
    root.dataset.mxBooted = '1';
    const load = loaders[root.dataset.mxChapter ?? ''];
    if (!load) return;
    load().then((m) => { const make = m.scenes[root.dataset.mx!]; if (make) setup(root, make()); }).catch((err) => console.error('[cosmos] cena', root.dataset.mx, err));
  };
  if (!('IntersectionObserver' in window)) { roots.forEach(boot); return; }
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { io.unobserve(e.target); boot(e.target as HTMLElement); }
  }, { rootMargin: '500px 0px' });
  roots.forEach((r) => io.observe(r));
  window.addEventListener('pagehide', (event) => {
    if (event.persisted) { mounted.forEach((r) => r.stop()); return; }
    mounted.forEach((r) => r.dispose()); mounted.clear(); io.disconnect();
  });
}

/** Marca no índice do capítulo as seções cuja verificação já foi acertada. */
function paintToc(): void {
  const done = practiced();
  document.querySelectorAll<HTMLAnchorElement>('[data-toc] a').forEach((a) => {
    const id = a.hash.slice(1);
    a.dataset.practiced = String(done.has(id));
  });
}

function setup(root: HTMLElement, scene: Scene): void {
  const id = root.dataset.mx!;
  const kind = root.dataset.mxKind as 'range' | 'stages' | 'choice';
  const svg = root.querySelector<SVGSVGElement>('[data-mx-svg]')!;
  const caption = root.querySelector<HTMLElement>('[data-mx-caption]')!;
  const live = root.querySelector<HTMLElement>('[data-mx-live]')!;
  const range = root.querySelector<HTMLInputElement>('[data-mx-range]');
  const out = root.querySelector<HTMLOutputElement>('[data-mx-out]');
  const opts = [...root.querySelectorAll<HTMLButtonElement>('[data-mx-opt]')];
  const play = root.querySelector<HTMLButtonElement>('[data-mx-play]')!;
  const playLabel = root.querySelector<HTMLElement>('[data-mx-play-label]')!;
  const stepBtn = root.querySelector<HTMLButtonElement>('[data-mx-step]')!;
  const reset = root.querySelector<HTMLButtonElement>('[data-mx-reset]')!;
  const min = range ? Number(range.min) : 0;
  const max = range ? Number(range.max) : opts.length - 1;
  const initial = range ? Number(range.value) : 0;
  const dur = scene.duration ?? (kind === 'stages' ? 1400 : 2600);
  const sweep = kind === 'range' && scene.animate !== 'time';

  let v = initial, t = 1, playing = false, frame = 0, last = 0, interacted = false, visible = true;
  let guided = true, hold = 0;
  root.dataset.guide = 'automatic';
  scene.init(svg);
  let volume: import('../visual/runtime').MountedScene | null = null;
  let visualStage = svg.parentElement!;
  const visualNotice = root.querySelector<HTMLElement>('[data-mx-visual-state]')!;
  const showVisualFallback = () => {
    visualNotice.textContent = 'Cena 3D indisponível neste navegador. Continue usando o diagrama e os controles abaixo.';
    visualNotice.hidden = false;
  };
  let alive = true;
  import('../visual/exhibits').then(async ({ visualCatalog }) => {
    const spec = visualCatalog[id]; if (!spec || !alive) return;
    if(spec.legend&&!root.querySelector('[data-visual-legend]')){const note=document.createElement('p');note.dataset.visualLegend='true';note.className='mx-caption';note.textContent=spec.legend;root.querySelector('.mx-caption')!.before(note);}
    if (spec.assets) await (await import('../visual/assets')).prepareWorlds();
    if(spec.galaxies){const {prepareEmissionGalaxies,prepareStarsOnly,emissionSize}=await import('../visual/galaxy-emission');const size=emissionSize(visualStage.clientWidth,visualStage.dataset.cosmosQuality==='low'?'low':'auto');await Promise.all([prepareEmissionGalaxies(size),...(spec.galaxyStars?[prepareStarsOnly(size)]:[])]);visualStage.dataset.galaxySeedSize=String(size);}
    if(spec.stellar)await(await import('../visual/stellar-materials')).prepareStellarMaterials(spec.stellar);
    if (!alive) return;
    if (spec.preserveSvg) {
      const preparedStage = visualStage;
      visualStage = document.createElement('div'); visualStage.className = 'mx-stage mx-volume-stage';
      if(preparedStage.dataset.galaxySeedSize)visualStage.dataset.galaxySeedSize=preparedStage.dataset.galaxySeedSize;
      if(preparedStage.dataset.cosmosQuality)visualStage.dataset.cosmosQuality=preparedStage.dataset.cosmosQuality;
      svg.parentElement!.before(visualStage);
      const useFlat=()=>{visualStage.hidden=true;visualStage.style.display='none';};visualStage.addEventListener('cosmos:contextlost',useFlat);visualStage.addEventListener('cosmos:unavailable',useFlat);
    }
    visualStage.addEventListener('cosmos:unavailable', showVisualFallback);
    visualStage.addEventListener('cosmos:contextlost', showVisualFallback);
    const { observeScene } = await import('../visual/runtime');
    volume = observeScene(visualStage, ()=>spec.make(visualStage)); volume.state({ value:v, phase:t });
  }).catch(() => { root.dataset.visualFallback='true'; if (alive) showVisualFallback(); });

  let liveTimer = 0;
  const render = (announce = true) => {
    const text = scene.draw(v, t);
    volume?.state({ value:v, phase:t });
    caption.textContent = text;
    if (range) { range.value = String(v); const val = scene.value?.(v) ?? String(v); if (out) out.textContent = val; range.setAttribute('aria-valuetext', val); }
    opts.forEach((b, i) => b.setAttribute('aria-pressed', String(i === Math.round(v))));
    if (announce && !playing) { clearTimeout(liveTimer); liveTimer = window.setTimeout(() => { live.textContent = text; }, 350); }
  };
  const setPlaying = (on: boolean) => {
    playing = on;
    play.setAttribute('aria-pressed', String(on));
    playLabel.textContent = on ? 'Pausar' : reducedQuery.matches ? 'Avançar' : 'Animar';
    play.querySelector('.mx-ico')!.textContent = on ? '❚❚' : '▶';
    root.classList.toggle('is-playing', on);
    scene.setPlaying?.(on);
  };
  const stop = () => { if (!playing) return; cancelAnimationFrame(frame); setPlaying(false); if (running === runner) running = null; render(interacted); };
  let automatic: ReturnType<typeof visibleMotion> | null = null;
  const reducedChange = () => { if (reducedQuery.matches) { stop(); t = 1; render(); } setPlaying(playing); };
  const runner: Runner = { stop, dispose() { if (!alive) return; alive=false; stop(); cancelAnimationFrame(frame); clearTimeout(liveTimer); automatic?.dispose(); reducedQuery.removeEventListener('change',reducedChange); volume?.dispose(); scene.dispose?.(); } };
  mounted.add(runner);

  const touched = () => {
    if (interacted) return;
    interacted = true;
    revealGuess();
  };

  const tick = (now: number) => {
    if (!playing) return;
    const dt = (last ? Math.min(now - last, 64) : 16) * motionFactor(); last = now;
    if (guided) {
      const next = advanceDemonstration({ value: v, phase: t, hold }, dt, {
        kind: sweep ? 'sweep' : kind === 'range' ? 'time' : kind,
        min, max, duration: sweep ? Math.max(dur * 2.2, 8000) : Math.max(dur, 2200), hold: 1800
      });
      v = next.value; t = next.phase; hold = next.hold;
    } else if (sweep) {
      v = Math.min(max, v + ((max - min) * dt) / (dur * 2.2));
      if (v >= max) { v = max; render(false); stop(); return; }
    } else {
      t = Math.min(1, t + dt / dur);
      if (t >= 1) {
        if (kind === 'stages' && v < max) { v += 1; t = 0; if (interacted) live.textContent = opts[v]?.textContent?.replace(/^\d/, '') ?? ''; }
        else { render(false); stop(); return; }
      }
    }
    render(false);
    frame = requestAnimationFrame(tick);
  };
  const start = (resume = false) => {
    if (!visible) return;
    running?.stop();
    if (reducedQuery.matches) { step(); return; }
    if (!resume && sweep && v >= max) v = min;
    if (!resume && kind === 'stages' && v >= max && t >= 1) v = 0;
    if (!resume) { if (!sweep || guided) t = 0; hold = 0; }
    running = runner; last = 0; setPlaying(true);
    frame = requestAnimationFrame(tick);
  };
  const step = () => {
    stop();
    if (kind === 'range') v = v >= max ? min : Math.min(max, +(v + (max - min) / 8).toFixed(4));
    else if (kind === 'stages') v = v >= max ? 0 : v + 1;
    else v = v >= max ? 0 : v + 1;
    t = 1; touched(); render();
  };

  const takeControl = () => { automatic?.manual(); guided = false; root.dataset.guide = 'manual'; };
  play.addEventListener('click', () => { takeControl(); touched(); if (playing) stop(); else start(); });
  stepBtn.addEventListener('click', () => { takeControl(); step(); });
  reset.addEventListener('click', () => { takeControl(); stop(); v = initial; t = 1; render(); });
  root.querySelector('[data-mx-auto]')?.addEventListener('click', () => {
    stop(); v = initial; t = reducedQuery.matches ? 1 : 0; hold = 0; guided = true; root.dataset.guide = 'automatic'; render(false); automatic?.automatic();
  });
  range?.addEventListener('input', () => { const next = Number(range.value); takeControl(); stop(); v = next; t = 1; touched(); render(); });
  opts.forEach((b, i) => b.addEventListener('click', () => {
    takeControl();
    stop(); v = i; touched();
    // escolher uma opção numa cena com movimento já toca o movimento dela (exceto com movimento reduzido)
    if (kind === 'choice' && !reducedQuery.matches) { t = 0; running = runner; last = 0; setPlaying(true); frame = requestAnimationFrame(tick); render(false); }
    else { t = 1; render(); }
  }));
  reducedQuery.addEventListener('change', reducedChange);

  // ── palpite ──
  const gBox = root.querySelector<HTMLElement>('[data-mx-guess-box]')!;
  const gBtns = [...gBox.querySelectorAll<HTMLButtonElement>('[data-mx-guess]')];
  const gRight = Number(gBox.dataset.right);
  let guess: number | null = null;
  function revealGuess(): void {
    if (guess === null) return;
    gBox.querySelector<HTMLElement>('[data-mx-guess-hint]')!.hidden = true;
    const ok = guess === gRight;
    gBtns.forEach((b, i) => { b.dataset.state = i === gRight ? 'right' : i === guess ? 'wrong' : 'idle'; });
    gBox.querySelector<HTMLElement>('[data-mx-verdict-label]')!.textContent = ok ? 'Seu palpite bateu.' : 'O que sabemos:';
    const verdict = gBox.querySelector<HTMLElement>('[data-mx-verdict]')!;
    verdict.hidden = false;
    const feedback = root.querySelector<HTMLElement>('[data-mx-inline-feedback]')!;
    feedback.textContent = verdict.textContent?.trim() ?? '';
    feedback.hidden = false;
    root.dispatchEvent(new CustomEvent('cosmos:guess', { bubbles: true, detail: { station: id, ok } }));
  }
  gBtns.forEach((b, i) => b.addEventListener('click', () => {
    if (guess !== null) return;
    guess = i;
    gBtns.forEach((x) => { x.disabled = true; x.dataset.state = x === b ? 'chosen' : 'idle'; });
    if (interacted) revealGuess();
    else {
      gBox.querySelector<HTMLElement>('[data-mx-guess-hint]')!.hidden = false;
      const next = root.querySelector<HTMLElement>('[data-mx-range], [data-mx-opt="1"], [data-mx-play]');
      next?.focus({ preventScroll: true });
      next?.scrollIntoView({ behavior: 'auto', block: 'center' });
    }
  }));

  // ── verificação ──
  const cBox = root.querySelector<HTMLElement>('[data-mx-check-box]')!;
  const cBtns = [...cBox.querySelectorAll<HTMLButtonElement>('[data-mx-check]')];
  const cRight = Number(cBox.dataset.right);
  const section = root.closest<HTMLElement>('.lesson-section')?.id ?? id;
  const history = root.querySelector<HTMLElement>('[data-mx-history]')!;
  cBtns.forEach((b, i) => b.addEventListener('click', () => {
    const ok = i === cRight;
    cBtns.forEach((x, j) => { x.dataset.state = j === cRight && ok ? 'right' : x === b ? (ok ? 'right' : 'wrong') : 'idle'; x.disabled = ok; });
    cBox.querySelector<HTMLElement>('[data-mx-check-label]')!.textContent = ok ? 'Isso.' : 'Ainda não. Releia a cena e tente outra.';
    const outBox = cBox.querySelector<HTMLElement>('[data-mx-check-out]')!;
    outBox.hidden = false;
    outBox.querySelector('p')!.lastChild!.textContent = ok ? ` ${outBox.dataset.why ?? ''}` : '';
    live.textContent = ok ? `Correto. ${outBox.dataset.why ?? ''}` : 'Ainda não. Tente outra resposta.';
    if (ok) {
      markPracticed(section); paintToc(); root.dataset.practiced = 'true';
      history.hidden = false;
      history.textContent = 'Você acertou esta verificação nesta visita. Continue explorando a ideia em outras situações.';
      root.dispatchEvent(new CustomEvent('cosmos:micro', { bubbles: true, detail: { id: section } }));
    }
  }));
  const outBox = cBox.querySelector<HTMLElement>('[data-mx-check-out]')!;
  outBox.dataset.why = outBox.querySelector('p')!.lastChild!.textContent?.trim() ?? '';
  if (practiced().has(section)) {
    root.dataset.practiced = 'true';
    history.hidden = false;
    history.textContent = 'Você acertou esta verificação em uma visita anterior. Os controles e respostas desta visita começam de novo.';
  }

  root.classList.add('is-ready');
  setPlaying(false);
  render(false);
  automatic = visibleMotion(root.querySelector('[data-mx-visuals]')!, { start, stop, running: () => playing, visibility: (on) => { visible = on; } });
}
