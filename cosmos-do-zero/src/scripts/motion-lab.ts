import { motionPreference, motionFactor } from './motion-preference';
/**
 * Painel "Ciência em movimento": abas, controles e laço de animação das cinco cenas.
 * Regras: só a aba aberta anima; tudo para fora da tela ou com a aba do navegador escondida;
 * com movimento reduzido nada se move sozinho ("Avançar" mostra o próximo estado);
 * nenhum WebGL, então não disputa o contexto único das cenas em 3D.
 */
import { SCI_SCENES, type SciFrame, type SciScene } from './motion-lab-scenes';
import { clamp, ease } from './micro/draw';

const reducedQuery = motionPreference;

class SciPanel {
  readonly id: string;
  private scene: SciScene | null = null;
  private p: number;
  private time = 0;
  private sweepT = 0;
  private sweeping = true;
  private playing = false;
  private raf = 0;
  private last = 0;
  private liveTimer = 0;
  private lastRead = '';
  private active = false;
  private visible = false;
  private autoStarted = false;
  private manual = false;
  private readonly stage: HTMLElement;
  private readonly svg: SVGSVGElement;
  private readonly read: HTMLElement;
  private readonly value: HTMLOutputElement;
  private readonly range: HTMLInputElement;
  private readonly play: HTMLButtonElement;
  private readonly playLabel: HTMLElement;
  private readonly reset: HTMLButtonElement;
  private readonly action: HTMLButtonElement | null;
  private readonly live: HTMLElement;
  private readonly sizer: ResizeObserver | null;

  constructor(readonly root: HTMLElement, private readonly make: () => SciScene) {
    this.id = root.dataset.sciPanel!;
    this.stage = root.querySelector<HTMLElement>('[data-sci-stage]')!;
    this.svg = root.querySelector<SVGSVGElement>('[data-sci-svg]')!;
    this.read = root.querySelector<HTMLElement>('[data-sci-read]')!;
    this.value = root.querySelector<HTMLOutputElement>('[data-sci-value]')!;
    this.range = root.querySelector<HTMLInputElement>('[data-sci-range]')!;
    this.play = root.querySelector<HTMLButtonElement>('[data-sci-play]')!;
    this.playLabel = root.querySelector<HTMLElement>('[data-sci-play-label]')!;
    this.reset = root.querySelector<HTMLButtonElement>('[data-sci-reset]')!;
    this.action = root.querySelector<HTMLButtonElement>('[data-sci-action]');
    this.live = root.querySelector<HTMLElement>('[data-sci-live]')!;
    this.p = Number(this.range.value) || 0;
    // Texto dentro do SVG com tamanho real constante (px), qualquer que seja a largura da figura.
    this.sizer = 'ResizeObserver' in window ? new ResizeObserver(() => this.fitText()) : null;
    this.sizer?.observe(this.stage);
    this.fitText();
    this.bind();
    this.syncLabel();
  }

  private fitText(): void {
    const w = this.stage.clientWidth || 340;
    this.svg.style.setProperty('--sci-fs', String(Math.min(26, Math.max(9, (14 * 480) / w)).toFixed(2)));
  }

  /** Cria o desenho na primeira vez que a aba abre. */
  private ensure(): SciScene {
    if (this.scene) return this.scene;
    const scene = this.make();
    scene.mount(this.svg, {
      canAnimate: () => this.active && this.visible && !document.hidden && !reducedQuery.matches,
      redraw: () => this.draw(false)
    });
    this.scene = scene;
    this.p = this.initial(scene);
    this.range.value = String(this.p);
    if (scene.action && this.action) { this.action.hidden = false; this.action.querySelector('[data-sci-action-label]')!.textContent = scene.action.label; }
    this.stage.classList.add('is-ready');
    this.draw(false);
    return scene;
  }

  /** Com movimento reduzido nada se anima sozinho: abre num estado do meio, que já mostra a ideia. */
  private initial(scene: SciScene): number { return reducedQuery.matches ? scene.steps[Math.floor(scene.steps.length / 2)] : scene.start; }

  private bind(): void {
    this.range.addEventListener('input', () => {
      this.manual = true;
      const scene = this.ensure();
      this.p = Number(this.range.value); this.sweeping = false;
      if (!scene.ambient) this.setPlaying(false);
      this.draw(true);
    });
    this.play.addEventListener('click', () => {
      this.manual = true;
      const scene = this.ensure();
      if (reducedQuery.matches) { this.advance(scene); return; }
      if (this.playing) { this.setPlaying(false); this.draw(true); return; }
      if (scene.sweep) { this.sweeping = true; this.sweepT = 0; }
      this.setPlaying(true);
    });
    this.reset.addEventListener('click', () => {
      this.manual = true;
      const scene = this.ensure();
      this.setPlaying(false); this.time = 0; this.sweepT = 0; this.p = this.initial(scene); this.sweeping = true;
      this.range.value = String(this.p); this.draw(true);
    });
    this.action?.addEventListener('click', () => { const scene = this.ensure(); scene.action?.run(); this.announce('Visão trocada para outra galáxia.'); });
    reducedQuery.addEventListener('change', () => { if (reducedQuery.matches) this.setPlaying(false); this.syncLabel(); });
  }

  private advance(scene: SciScene): void {
    const next = scene.steps.find((s) => s > this.p + 1e-6) ?? scene.steps[0];
    this.p = next; this.range.value = String(next); this.sweeping = false; this.draw(true);
  }

  private syncLabel(): void {
    const reduced = reducedQuery.matches;
    this.playLabel.textContent = this.playing ? 'Pausar' : reduced ? 'Avançar' : 'Reproduzir';
    this.play.setAttribute('aria-pressed', String(this.playing));
    this.play.querySelector('[data-sci-ico]')!.textContent = this.playing ? '❚❚' : reduced ? '⏭' : '▶';
    this.root.classList.toggle('is-playing', this.playing);
  }

  private setPlaying(on: boolean): void {
    this.playing = on; this.syncLabel(); this.sync();
  }

  /** Liga ou desliga o laço conforme: aba aberta, na tela, aba do navegador visível, "tocando" e sem movimento reduzido. */
  sync(): void {
    const run = this.playing && this.active && this.visible && !document.hidden && !reducedQuery.matches;
    if (run && !this.raf) { this.last = 0; this.raf = requestAnimationFrame(this.tick); }
    else if (!run && this.raf) { cancelAnimationFrame(this.raf); this.raf = 0; }
  }

  private readonly tick = (now: number): void => {
    const dt = this.last ? Math.min(0.064, (now - this.last) / 1000 * motionFactor()) : 0;
    this.last = now; this.time += dt;
    const scene = this.scene!;
    if (scene.sweep && this.sweeping) {
      this.sweepT += dt;
      const { seconds, mode } = scene.sweep;
      if (mode === 'fill') { const cycle = seconds + 2.4; const ph = this.sweepT % cycle; this.p = Math.min(1, ph / seconds); }
      else {
        const hold = 0.9, cycle = 2 * (seconds + hold), ph = this.sweepT % cycle;
        this.p = ph < seconds ? ease(ph / seconds) : ph < seconds + hold ? 1 : ph < 2 * seconds + hold ? 1 - ease((ph - seconds - hold) / seconds) : 0;
      }
      this.range.value = String(this.p);
    }
    this.draw(false);
    this.raf = requestAnimationFrame(this.tick);
  };

  private frame(): SciFrame { return this.scene!.render(this.p, this.time); }

  draw(announce: boolean): void {
    if (!this.scene) return;
    const f = this.frame();
    if (f.read !== this.lastRead) { this.read.textContent = f.read; this.lastRead = f.read; }
    if (this.value.textContent !== f.value) this.value.textContent = f.value;
    this.range.setAttribute('aria-valuetext', f.value);
    if (announce) this.announce(f.aria);
  }

  /** A mesma escala comóvel do controle manual acompanha a passagem da figura pela tela. */
  readScroll(): void {
    if (this.id !== 'expansao' || this.manual || !this.active || !this.visible || document.hidden || reducedQuery.matches) return;
    const { top, bottom } = this.stage.getBoundingClientRect();
    if (bottom <= 0 || top >= innerHeight) return;
    const next = clamp((0.85 - top / innerHeight) / 0.6);
    if (next === this.p) return;
    this.p = next;
    this.range.value = String(next);
    this.draw(false);
  }

  private announce(msg: string): void {
    clearTimeout(this.liveTimer);
    this.liveTimer = window.setTimeout(() => { this.live.textContent = msg; }, 400);
  }

  setActive(on: boolean): void {
    this.active = on;
    this.root.hidden = !on;
    if (on) {
      const scene = this.ensure();
      this.fitText();
      if (this.visible && !this.autoStarted && !reducedQuery.matches) this.autoStart(scene);
      this.draw(false);
    }
    this.sync();
    this.readScroll();
  }

  setVisible(on: boolean): void {
    this.visible = on;
    if (on && this.active && !this.autoStarted && !reducedQuery.matches) this.autoStart(this.ensure());
    this.sync();
    this.readScroll();
  }

  private autoStart(scene: SciScene): void {
    this.autoStarted = true;
    if (this.id === 'expansao') return;
    if (scene.sweep || scene.ambient) this.setPlaying(true);
  }

  halt(): void { cancelAnimationFrame(this.raf); this.raf = 0; }

  dispose(): void {
    cancelAnimationFrame(this.raf); this.raf = 0; clearTimeout(this.liveTimer);
    this.sizer?.disconnect(); this.scene?.dispose?.();
  }
}

export function initSciLab(): void {
  document.querySelectorAll<HTMLElement>('[data-sci-lab]').forEach(setup);
}

function setup(root: HTMLElement): void {
  const tablist = root.querySelector<HTMLElement>('[data-sci-tabs]');
  const tabs = [...root.querySelectorAll<HTMLButtonElement>('[data-sci-tab]')];
  const panels = [...root.querySelectorAll<HTMLElement>('[data-sci-panel]')]
    .map((el) => { const make = SCI_SCENES[el.dataset.sciPanel!]; return make ? new SciPanel(el, make) : null; })
    .filter((p): p is SciPanel => !!p);
  if (!panels.length || !tablist) return;
  tablist.hidden = false;

  let current = -1;
  const select = (index: number, focus = false): void => {
    if (index === current) { if (focus) tabs[index].focus(); return; }
    current = index;
    tabs.forEach((t, i) => { t.setAttribute('aria-selected', String(i === index)); t.tabIndex = i === index ? 0 : -1; });
    panels.forEach((p, i) => p.setActive(i === index));
    if (focus) tabs[index].focus();
  };
  tabs.forEach((tab, i) => {
    tab.addEventListener('click', () => select(i));
    tab.addEventListener('keydown', (e) => {
      const last = tabs.length - 1;
      const to = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? (i === last ? 0 : i + 1) : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? (i === 0 ? last : i - 1) : e.key === 'Home' ? 0 : e.key === 'End' ? last : -1;
      if (to >= 0) { e.preventDefault(); select(to, true); }
    });
  });
  const fromHash = (): number => panels.findIndex((p) => `#movimento-${p.id}` === location.hash);
  const goHash = (): void => { const i = fromHash(); if (i >= 0) { select(i); requestAnimationFrame(() => panels[i].root.scrollIntoView({ block: 'start' })); } };
  select(Math.max(0, fromHash()));
  if (fromHash() >= 0) goHash();
  addEventListener('hashchange', goHash);

  if ('IntersectionObserver' in window) {
    const expansion = panels.find((panel) => panel.id === 'expansao');
    const others = panels.filter((panel) => panel !== expansion);
    new IntersectionObserver(([entry]) => others.forEach((panel) => panel.setVisible(entry.isIntersecting)), { threshold: 0.2 }).observe(root.querySelector('[data-sci-body]') ?? root);
    const expansionStage = expansion?.root.querySelector('[data-sci-stage]');
    if (expansion && expansionStage) {
      let frame = 0;
      const syncScroll = () => {
        if (frame || expansion.root.hidden) return;
        frame = requestAnimationFrame(() => { frame = 0; expansion.readScroll(); });
      };
      new IntersectionObserver(([entry]) => {
        expansion.setVisible(entry.isIntersecting);
        if (entry.isIntersecting) {
          addEventListener('scroll', syncScroll, { passive: true });
          addEventListener('resize', syncScroll);
        } else {
          removeEventListener('scroll', syncScroll);
          removeEventListener('resize', syncScroll);
          cancelAnimationFrame(frame);
          frame = 0;
        }
      }).observe(expansionStage);
    }
  } else panels.forEach((p) => p.setVisible(true));
  root.classList.add('is-ready');
  document.addEventListener('visibilitychange', () => panels.forEach((p) => p.sync()));
  window.addEventListener('pagehide', (event) => { if (event.persisted) panels.forEach((p) => p.halt()); else panels.forEach((p) => p.dispose()); });
  window.addEventListener('pageshow', (event) => { if (event.persisted) panels.forEach((p) => p.sync()); });
}
