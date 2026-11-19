import { scaleLogs, scaleStations } from '../data/scale-stations';
import { journeyLayers, journeyLog, journeyPosition, journeyVideoTime } from '../lib/scale-journey';
import { motionPreference } from './motion-preference';
const fullMotion = () => !motionPreference.matches && document.documentElement.dataset.motion === 'full';
const lastStage = scaleStations.length - 1;
const firstVideoStage = scaleStations.findIndex(station => station.id === 'terra');
const finalVideoStage = scaleStations.findIndex(station => station.id === 'teia-cosmica');
const logSpan = scaleLogs[lastStage] - scaleLogs[0];
const sliderSteps = 10000;
type Mode = 'video' | 'posters';

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
  let visible = false, disposed = false;
  let mode: Mode = 'video', videoFailed = false;
  let frame = 0, previous = -1, currentStation = -1;
  let offsets: number[] = [];
  const canDraw = () => visible && fullMotion() && !document.hidden && !disposed;

  function queue() {
    if (canDraw() && !frame) frame = requestAnimationFrame(draw);
  }

  function release() {
    cancelAnimationFrame(frame);
    frame = 0;
    previous = -1;
    visual.dataset.media = 'posters';
  }

  function setMode(next: Mode) {
    release();
    mode = next;
    light.setAttribute('aria-pressed', String(mode === 'posters'));
    queue();
  }

  function syncVideo(value: number): boolean {
    if (mode !== 'video' || videoFailed || value < firstVideoStage || value > finalVideoStage) return false;
    if (!video.getAttribute('src')) {
      video.preload = 'auto';
      video.src = canvas.clientWidth * devicePixelRatio <= 900 ? video.dataset.compact! : video.dataset.scaleVideo!;
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
      if (opacity && !img.getAttribute('src')) {
        img.srcset = img.dataset.srcset!;
        img.src = img.dataset.src!;
      }
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

  function draw() {
    frame = 0;
    if (!canDraw()) return;
    // Scrolling to an anchor rounds to a CSS pixel, including on fractional-DPR phones.
    const distance = stationOffsets();
    const stop = offsets.findIndex(offset => Math.abs(offset - distance) <= 1);
    const value = stop < 0 ? journeyPosition(distance, offsets) : stop;
    const index = Math.round(value);
    if (index !== currentStation) selectStation(index);
    if (value !== previous) {
      const progress = (journeyLog(value, scaleLogs) - scaleLogs[0]) / logSpan;
      input.value = String(Math.round(sliderSteps * progress));
      root.style.setProperty('--scale-travel', `${progress * 100}%`);
      visual.dataset.scalePosition = value.toFixed(4);
      syncPosters(value);
      previous = value;
    }
    visual.dataset.media = syncVideo(value) ? 'video' : 'posters';
  }

  const refresh = () => {
    offsets = [];
    queue();
  };
  const onVideoError = () => {
    videoFailed = true;
    visual.dataset.media = 'posters';
    previous = -1;
    queue();
  };
  const syncVisibility = () => {
    if (canDraw()) queue();
    else release();
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
  light.addEventListener('click', () => setMode(mode === 'video' ? 'posters' : 'video'));
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
