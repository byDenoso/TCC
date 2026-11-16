import { scaleLogs, scaleStations } from '../data/scale-stations';
import { journeyLayers, journeyLog, journeyPosition, journeyVideoTime } from '../lib/scale-journey';
import { motionPreference } from './motion-preference';
import type { FrameBudget } from './visual/render-policy';
import type { MountedScene } from './visual/runtime';

const phone = matchMedia('(max-width: 760px) and (pointer: coarse)');
const fullMotion = () => !motionPreference.matches && document.documentElement.dataset.motion === 'full';
const lastStage = scaleStations.length - 1;
const firstVideoStage = scaleStations.findIndex(station => station.id === 'terra');
const finalVideoStage = scaleStations.findIndex(station => station.id === 'teia-cosmica');
const logSpan = scaleLogs[lastStage] - scaleLogs[0];
const sliderSteps = 10000;
type Mode = '3d' | 'video' | 'posters';

function mountJourney(root: HTMLElement): void {
  const visual = root.querySelector<HTMLElement>('[data-scale-visual-stage]')!;
  const canvas = root.querySelector<HTMLElement>('[data-scale-canvas]')!;
  const video = root.querySelector<HTMLVideoElement>('[data-scale-video]')!;
  const posters = [...root.querySelectorAll<HTMLImageElement>('.scale-journey-posters img')];
  const stations = [...root.querySelectorAll<HTMLElement>('[data-scale-station]')];
  const links = [...root.querySelectorAll<HTMLAnchorElement>('.cosmic-exhibit-nav a')];
  const count = root.querySelector<HTMLElement>('[data-scale-count]')!;
  const active = root.querySelector<HTMLElement>('[data-scale-active]')!;
  const input = root.querySelector<HTMLInputElement>('[data-scale-input]')!;
  const jump = root.querySelector<HTMLSelectElement>('[data-scale-jump]')!;
  const light = root.querySelector<HTMLButtonElement>('[data-scale-light]')!;
  let visible = false, disposed = false, pending = false, generation = 0;
  let view: MountedScene | null = null, budget: FrameBudget | null = null;
  let mode: Mode = '3d', videoFailed = false, webglFailed = false;
  let frame = 0, sampleFrame = 0, warmup = 0, previous = -1, currentStation = -1;
  let offsets: number[] = [];
  const canDraw = () => visible && fullMotion() && !document.hidden && !disposed;

  function queue() {
    if (canDraw() && !frame) frame = requestAnimationFrame(draw);
  }

  function release() {
    cancelAnimationFrame(frame);
    cancelAnimationFrame(sampleFrame);
    frame = sampleFrame = 0;
    previous = -1;
    warmup = 0;
    budget?.reset();
    generation++;
    pending = false;
    view?.dispose();
    view = null;
    visual.dataset.media = 'posters';
  }

  function setMode(next: Mode) {
    release();
    mode = next;
    light.setAttribute('aria-pressed', String(mode !== '3d'));
    void start();
    queue();
  }

  function syncVideo(value: number): boolean {
    if (mode !== 'video' || videoFailed || value < firstVideoStage || value > finalVideoStage) return false;
    if (!video.getAttribute('src')) {
      video.preload = 'auto';
      video.src = video.dataset.scaleVideo!;
    }
    if (video.readyState < HTMLMediaElement.HAVE_METADATA || !Number.isFinite(video.duration)) return false;
    const wantedTime = journeyVideoTime(value - firstVideoStage, video.duration);
    if (!video.seeking && Math.abs(video.currentTime - wantedTime) > 1 / 120) video.currentTime = wantedTime;
    return !video.seeking && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA;
  }

  function syncPosters(value: number) {
    const { from, to, blend } = journeyLayers(value, lastStage);
    posters.forEach((img, i) => {
      const opacity = i === from ? 1 - blend : i === to ? blend : 0;
      if (opacity && !img.getAttribute('src')) img.src = img.dataset.src!;
      img.style.setProperty('--scale-opacity', String(opacity));
      img.style.setProperty('--scale-size', String(i === from ? .08 ** blend : i === to ? 3.2 ** (1 - blend) : 1));
    });
  }

  function selectStation(index: number) {
    currentStation = index;
    const station = scaleStations[index];
    count.textContent = `${String(index + 1).padStart(2, '0')} / ${stations.length}`;
    jump.value = String(index);
    input.setAttribute('aria-valuetext', `${station.name} · ${station.extent}`);
    active.replaceChildren(stations[index].querySelector('.cosmic-exhibit-copy')!.cloneNode(true));
    active.scrollTop = 0;
    links.forEach((link, i) => i === index ? link.setAttribute('aria-current', 'step') : link.removeAttribute('aria-current'));
  }

  function stationOffsets() {
    const first = stations[0].getBoundingClientRect().top;
    if (!offsets.length) offsets = stations.map(station => station.getBoundingClientRect().top - first);
    return -first;
  }

  function seek(value: number) {
    if (!fullMotion()) return;
    const displacement = stationOffsets();
    const a = Math.min(lastStage - 1, Math.floor(value));
    const position = offsets[a] + (offsets[a + 1] - offsets[a]) * (value - a);
    window.scrollTo({ top: window.scrollY + position - displacement, behavior: 'instant' });
    queue();
  }

  function draw(now: number) {
    frame = 0;
    if (!canDraw()) return;
    const value = journeyPosition(stationOffsets(), offsets);
    const index = Math.round(value);
    if (index !== currentStation) selectStation(index);
    if (value !== previous) {
      const progress = (journeyLog(value, scaleLogs) - scaleLogs[0]) / logSpan;
      input.value = String(Math.round(sliderSteps * progress));
      root.style.setProperty('--scale-travel', `${progress * 100}%`);
      visual.dataset.scalePosition = value.toFixed(4);
      if (canvas.dataset.renderer) {
        view?.state({ value });
        if (phone.matches && budget && ++warmup > 12 && !sampleFrame) {
          // Measure the frame after actual scroll work, excluding time between gestures.
          sampleFrame = requestAnimationFrame(next => {
            sampleFrame = 0;
            if (!canDraw() || !canvas.dataset.renderer || !budget) return;
            budget.record(next - now);
            const profile = budget.decide(45, 1000 / 50);
            if (!profile) return;
            visual.dataset.scaleP90 = budget.p90!.toFixed(1);
            budget.reset();
            if (profile === 'low') setMode('video');
          });
        }
      } else syncPosters(value);
      previous = value;
    }
    if (!canvas.dataset.renderer) visual.dataset.media = syncVideo(value) ? 'video' : 'posters';
  }

  async function start() {
    if (!canDraw() || view || pending || mode !== '3d' || webglFailed) return;
    pending = true;
    const ticket = ++generation;
    const valid = () => ticket === generation && canDraw();
    try {
      const [scene, runtime, policy] = await Promise.all([
        import('./visual/scale-exhibit'), import('./visual/runtime'), import('./visual/render-policy'),
      ]);
      if (!valid()) return;
      budget = new policy.FrameBudget();
      view = runtime.observeScene(canvas, () => scene.scaleExhibit(canvas.clientWidth < 600, () => {
        if (canDraw() && previous >= 0) view?.state({ value: previous });
      }));
      if (previous >= 0) view.state({ value: previous });
    } catch {
      if (valid()) failWebgl();
    } finally {
      if (ticket === generation) pending = false;
    }
  }

  function failWebgl() {
    webglFailed = true;
    setMode(phone.matches ? 'video' : 'posters');
    light.disabled = true;
  }

  const refresh = () => {
    offsets = [];
    queue();
  };
  const ready = () => {
    if (!canDraw()) return;
    visual.dataset.media = canvas.dataset.renderer === 'webgpu' ? 'webgpu' : 'webgl';
    const options = canvas.parentElement?.querySelector('.cosmos-view-options > summary');
    if (options) options.textContent = 'Câmera 3D';
    previous = -1;
    queue();
  };
  const onVideoError = () => {
    videoFailed = true;
    visual.dataset.media = 'posters';
    previous = -1;
    queue();
  };
  const syncVisibility = () => {
    if (canDraw()) {
      void start();
      queue();
    } else release();
  };
  const applyMotion = () => {
    const enabled = fullMotion();
    if (enabled === root.hasAttribute('data-scale-enhanced')) return;
    root.toggleAttribute('data-scale-enhanced', enabled);
    if (enabled && currentStation < 0) selectStation(0);
    if (!enabled) links.forEach(link => link.removeAttribute('aria-current'));
    currentStation = -1;
    refresh();
    syncVisibility();
  };

  const resize = new ResizeObserver(refresh);
  resize.observe(root);
  const observer = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    syncVisibility();
  }, { threshold: .06 });
  observer.observe(canvas);
  input.addEventListener('input', () => seek(journeyPosition(scaleLogs[0] + logSpan * Number(input.value) / sliderSteps, scaleLogs)));
  jump.addEventListener('change', () => {
    const i = Number(jump.value);
    history.replaceState(history.state, '', `#${stations[i].id}`);
    seek(i);
  });
  light.addEventListener('click', () => setMode(mode === '3d' ? 'posters' : '3d'));
  canvas.addEventListener('cosmos:ready', ready);
  canvas.addEventListener('cosmos:contextlost', failWebgl);
  canvas.addEventListener('cosmos:unavailable', failWebgl);
  canvas.addEventListener('cosmos:gpulost', () => {
    visual.dataset.media = 'posters';
    previous = -1;
    queue();
  });
  video.addEventListener('loadedmetadata', queue);
  video.addEventListener('loadeddata', queue);
  video.addEventListener('seeked', queue);
  video.addEventListener('error', onVideoError);
  window.addEventListener('scroll', queue, { passive: true });
  document.addEventListener('visibilitychange', syncVisibility);
  motionPreference.addEventListener('change', applyMotion);
  window.addEventListener('pagehide', event => {
    release();
    if (event.persisted) return;
    disposed = true;
    observer.disconnect();
    resize.disconnect();
    window.removeEventListener('scroll', queue);
    document.removeEventListener('visibilitychange', syncVisibility);
    motionPreference.removeEventListener('change', applyMotion);
  });
  window.addEventListener('pageshow', syncVisibility);
  applyMotion();
}

export function initScaleJourneys(): void {
  if (!('IntersectionObserver' in window) || !('ResizeObserver' in window)) return;
  document.querySelectorAll<HTMLElement>('[data-scale-journey]').forEach(mountJourney);
}
