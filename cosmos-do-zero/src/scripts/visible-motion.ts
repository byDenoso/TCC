import { motionPreference } from './motion-preference';
/** Automatic motion follows the visible scene and never overrides a manual pause. */
export function visibleMotion(stage: Element, controls: {
  start(resume: boolean): void;
  stop(): void;
  running(): boolean;
  ready?(): boolean;
  visibility?(visible: boolean): void;
  pauseTarget?: Element;
}): { manual(): void; refresh(): void; dispose(): void } {
  const reduced = motionPreference;
  let visible = false, started = false, suspended = false, manual = false;

  const start = () => {
    if (!visible || document.hidden || reduced.matches || manual || (started && !suspended) || controls.ready?.() === false) return;
    const resume = suspended;
    controls.start(resume);
    if (controls.running()) { started = true; suspended = false; }
  };
  const suspend = () => {
    if (!controls.running()) return;
    suspended = !manual;
    controls.stop();
  };
  const observer = 'IntersectionObserver' in window ? new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    controls.visibility?.(visible);
    if (visible) start(); else suspend();
  }, { threshold: 0.15 }) : null;
  if (observer) observer.observe(stage);
  else { visible = true; controls.visibility?.(true); }
  const change = () => { if (document.hidden || reduced.matches) suspend(); else start(); };
  const externalPause = () => { if (started && !manual) suspended = true; };
  controls.pauseTarget?.addEventListener('cosmos:autopause', externalPause);
  document.addEventListener('visibilitychange', change);
  reduced.addEventListener('change', change);
  return {
    manual() { manual = true; suspended = false; },
    refresh: start,
    dispose() { observer?.disconnect(); controls.pauseTarget?.removeEventListener('cosmos:autopause', externalPause); document.removeEventListener('visibilitychange', change); reduced.removeEventListener('change', change); }
  };
}
