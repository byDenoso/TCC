import { journeyLayers, journeyPosition, journeyVideoTime } from '../lib/scale-journey';
import { motionPreference } from './motion-preference';
import type { FrameBudget } from './visual/render-policy';
import type { MountedScene } from './visual/runtime';

const mobile = matchMedia('(max-width: 900px) and (pointer: coarse)');
const fullMotion = () => !motionPreference.matches && document.documentElement.dataset.motion === 'full';
const sampleCount = 45;
const budgetMs = 1000 / 50;

function mountJourney(root: HTMLElement): void {
  const visual = root.querySelector<HTMLElement>('[data-scale-visual-stage]')!;
  const canvas = root.querySelector<HTMLElement>('[data-scale-canvas]')!;
  const video = root.querySelector<HTMLVideoElement>('[data-scale-video]')!;
  const posters = [...root.querySelectorAll<HTMLImageElement>('.scale-journey-posters img')];
  const stations = [...root.querySelectorAll<HTMLElement>('[data-scale-station]')];
  const links = [...root.querySelectorAll<HTMLAnchorElement>('.cosmic-exhibit-nav a')];
  const count = root.querySelector<HTMLElement>('[data-scale-count]')!;
  const name = root.querySelector<HTMLElement>('[data-scale-name]')!;
  let visible = false, disposed = false, pending = false, generation = 0;
  let view: MountedScene | null = null, budget: FrameBudget | null = null;
  let videoPreferred = false, videoFailed = false, webglFailed = false;
  let frame = 0, sampleFrame = 0, warmup = 0, previous = -1, currentStation = -1;
  let offsets: number[] = [];
  const canDraw = () => visible && fullMotion() && !document.hidden && !disposed;

  function queue() {
    if (canDraw() && !frame) frame = requestAnimationFrame(draw);
  }

  function release() {
    cancelAnimationFrame(frame);
    cancelAnimationFrame(sampleFrame);
    frame = 0;
    sampleFrame = 0;
    previous = -1;
    warmup = 0;
    budget?.reset();
    generation++;
    pending = false;
    view?.dispose();
    view = null;
    visual.dataset.media = 'posters';
  }

  function fallback(useVideo: boolean) {
    release();
    videoPreferred = useVideo;
    if (useVideo && !video.src) {
      video.preload = 'auto';
      video.src = video.dataset.scaleVideo!;
    }
    queue();
  }

  function syncVideo(value: number) {
    if (video.readyState < HTMLMediaElement.HAVE_METADATA || !Number.isFinite(video.duration)) return;
    const wantedVideoTime = journeyVideoTime(value, video.duration);
    if (!video.seeking && Math.abs(video.currentTime - wantedVideoTime) > 1 / 120) {
      video.currentTime = wantedVideoTime;
    } else if (!video.seeking && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      visual.dataset.media = 'video';
    }
  }

  function draw(now: number) {
    frame = 0;
    if (!canDraw()) return;
    const first = stations[0].getBoundingClientRect().top;
    if (!offsets.length) offsets = stations.map(station => station.getBoundingClientRect().top - first);
    const value = journeyPosition(-first, offsets);
    const index = Math.round(value);
    if (index !== currentStation) {
      currentStation = index;
      count.textContent = `0${index + 1} / 0${stations.length}`;
      name.textContent = stations[index].dataset.scaleStation!;
      links.forEach((link, i) => i === index ? link.setAttribute('aria-current', 'step') : link.removeAttribute('aria-current'));
    }
    if (value !== previous) {
      root.style.setProperty('--scale-travel', String(value / (stations.length - 1)));
      visual.dataset.scalePosition = value.toFixed(4);
      if (canvas.dataset.renderer) {
        view?.state({ value });
        if (mobile.matches && budget && ++warmup > 12 && !sampleFrame) {
          // Measure the frame after this draw. Idle time between scroll gestures is excluded.
          sampleFrame = requestAnimationFrame(next => {
            sampleFrame = 0;
            if (!canDraw() || !canvas.dataset.renderer || !budget) return;
            budget.record(next - now);
            const profile = budget.decide(sampleCount, budgetMs);
            if (!profile) return;
            visual.dataset.scaleP90 = budget.p90!.toFixed(1);
            budget.reset();
            if (profile === 'low') fallback(true);
          });
        }
      } else if (visual.dataset.media !== 'video') {
        const { from, to, blend } = journeyLayers(value);
        posters.forEach((poster, i) => {
          poster.style.setProperty('--scale-opacity', String(i === from ? 1 - blend : i === to ? blend : 0));
          poster.style.setProperty('--scale-size', String(i === from ? .08 ** blend : i === to ? 3.2 ** (1 - blend) : 1));
        });
      }
      previous = value;
    }
    if (videoPreferred && !videoFailed) syncVideo(value);
  }

  async function start() {
    if (!canDraw() || view || pending || videoPreferred || webglFailed) return;
    pending = true;
    const ticket = ++generation;
    const valid = () => ticket === generation && canDraw();
    try {
      const [assets, maps, exhibits, runtime, policy] = await Promise.all([
        import('./visual/assets'), import('./visual/galaxy-emission'), import('./visual/exhibits'),
        import('./visual/runtime'), import('./visual/render-policy')
      ]);
      if (!valid()) return;
      const size = maps.emissionSize(canvas.clientWidth);
      await Promise.all([assets.prepareWorlds(), maps.prepareEmissionGalaxies(size)]);
      if (!valid()) return;
      budget = new policy.FrameBudget();
      view = runtime.observeScene(canvas, () => exhibits.address(size, true));
      if (previous >= 0) view.state({ value: previous });
    } catch {
      if (valid()) failWebgl();
    } finally {
      if (ticket === generation) pending = false;
    }
  }

  function failWebgl() {
    webglFailed = true;
    fallback(mobile.matches);
  }

  const refresh = () => {
    offsets = [];
    queue();
  };
  const ready = () => {
    if (!canDraw()) return;
    visual.dataset.media = 'webgl';
    previous = -1;
    queue();
  };
  const onVideoError = () => {
    videoFailed = true;
    visual.dataset.media = 'posters';
    previous = -1;
    queue();
  };
  const onVideoFrame = () => {
    if (!canDraw() || !videoPreferred || videoFailed) return;
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
  }, { threshold: .01 });
  observer.observe(canvas);
  canvas.addEventListener('cosmos:ready', ready);
  canvas.addEventListener('cosmos:contextlost', failWebgl);
  canvas.addEventListener('cosmos:unavailable', failWebgl);
  video.addEventListener('loadedmetadata', onVideoFrame);
  video.addEventListener('loadeddata', onVideoFrame);
  video.addEventListener('seeked', onVideoFrame);
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
