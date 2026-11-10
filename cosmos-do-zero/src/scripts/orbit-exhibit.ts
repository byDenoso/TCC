import { JUPITER_IN_SOLAR_MASSES, ORBIT_VIEW, orbitPeriod, orbitPoint, orbitSectorPath, orbitState, TAU } from '../lib/kepler';
import { motionPreference, motionFactor } from './motion-preference';

const decimal = (digits: number) => new Intl.NumberFormat('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
const whole = decimal(0);
const single = decimal(1);
const two = decimal(2);
const { cx, pixelsPerAu: pixels } = ORBIT_VIEW;

export function initOrbitExhibit(): void {
  const exhibit = document.querySelector<HTMLElement>('[data-orbit-exhibit]');
  if (!exhibit) return;
  const input = (key: string) => exhibit.querySelector<HTMLInputElement>(`[data-orbit-input="${key}"]`)!;
  const field = (key: string) => exhibit.querySelector<HTMLElement>(`[data-orbit-${key}]`)!;
  const eccentricity = input('ecc');
  const axis = input('axis');
  const phase = input('phase');
  const mass = input('mass');
  const companion = input('companion');
  const controls = [eccentricity, axis, mass, companion, phase];
  const totalMass = () => mass.valueAsNumber + companion.valueAsNumber * JUPITER_IN_SOLAR_MASSES;
  const play = exhibit.querySelector<HTMLButtonElement>('[data-orbit-play]')!;
  const ellipse = exhibit.querySelector<SVGEllipseElement>('[data-orbit-path]')!;
  const planet = exhibit.querySelector<SVGCircleElement>('[data-orbit-planet]')!;
  const radius = exhibit.querySelector<SVGLineElement>('[data-orbit-radius]')!;
  const wedges = [...exhibit.querySelectorAll<SVGPathElement>('[data-orbit-wedges] path')];
  const outputs = ['ecc', 'axis', 'phase', 'mass', 'companion'].map((key) => exhibit.querySelector<HTMLOutputElement>(`[data-orbit-value="${key}"]`)!);
  const [distance, speed, period, energy] = ['distance', 'speed', 'period', 'energy'].map(field);
  let playing = false;
  let frame = 0;
  let previous = 0;
  let position = phase.valueAsNumber;
  let duration = orbitPeriod(axis.valueAsNumber);

  function updatePosition() {
    const state = orbitState(axis.valueAsNumber, eccentricity.valueAsNumber, TAU * position / 100, totalMass());
    const [x, y] = orbitPoint(state.x, state.y);
    planet.setAttribute('cx', String(x));
    planet.setAttribute('cy', String(y));
    radius.setAttribute('x2', String(x));
    radius.setAttribute('y2', String(y));
    distance.textContent = `${two.format(state.radius)} UA`;
    energy.textContent = `${single.format(state.specificEnergy).replace('-', '−')} km²/s²`;
    speed.textContent = `${single.format(state.speed)} km/s`;
    const percent = whole.format(position);
    outputs[2].value = `${percent}%`;
    phase.setAttribute('aria-valuetext', `${percent} por cento da órbita`);
  }

  function updateOrbit() {
    const a = axis.valueAsNumber;
    const e = eccentricity.valueAsNumber;
    duration = orbitPeriod(a, totalMass());
    ellipse.setAttribute('cx', String(cx - a * e * pixels));
    ellipse.setAttribute('rx', String(a * pixels));
    ellipse.setAttribute('ry', String(a * Math.sqrt(1 - e * e) * pixels));
    wedges.forEach((wedge, i) => wedge.setAttribute('d', orbitSectorPath(a, e, i * Math.PI)));
    outputs[0].value = two.format(e);
    outputs[1].value = `${two.format(a)} UA`;
    eccentricity.setAttribute('aria-valuetext', outputs[0].value);
    outputs[3].value = `${two.format(mass.valueAsNumber)} M☉`;
    outputs[4].value = `${single.format(companion.valueAsNumber)} M♃`;
    mass.setAttribute('aria-valuetext', `${two.format(mass.valueAsNumber)} massas solares`);
    companion.setAttribute('aria-valuetext', `${single.format(companion.valueAsNumber)} massas de Júpiter`);
    axis.setAttribute('aria-valuetext', outputs[1].value);
    period.textContent = `${whole.format(duration)} dias`;
    updatePosition();
  }

  function animate(now: number) {
    if (previous) position = (position + Math.min(50, now - previous) * 4 * motionFactor() / duration) % 100;
    previous = now;
    phase.value = String(position);
    updatePosition();
    frame = requestAnimationFrame(animate);
  }

  function setPlaying(active: boolean) {
    cancelAnimationFrame(frame);
    playing = active;
    previous = 0;
    play.setAttribute('aria-pressed', String(active));
    play.textContent = motionPreference.matches ? 'Avançar ⅛ de volta' : active ? 'Pausar órbita' : 'Animar órbita';
    if (active) frame = requestAnimationFrame(animate);
  }

  play.addEventListener('click', () => {
    if (motionPreference.matches) {
      position = (position + 12.5) % 100;
      phase.value = String(position);
      updatePosition();
    } else setPlaying(!playing);
  });
  phase.addEventListener('input', () => { setPlaying(false); position = phase.valueAsNumber; updatePosition(); });
  for (const control of controls.slice(0, -1)) control.addEventListener('input', updateOrbit);
  field('reset').addEventListener('click', () => {
    setPlaying(false);
    for (const control of controls) control.value = control.defaultValue;
    position = phase.valueAsNumber;
    updateOrbit();
  });
  const presets: Record<string, number[]> = {
    circle: [0, 1, 1, 0, 0],
    eccentric: [0.72, 1.15, 1, 0, 0],
    heavy: [0.35, 1, 2, 10, 0]
  };
  exhibit.querySelectorAll<HTMLButtonElement>('[data-orbit-preset]').forEach((button) => {
    button.addEventListener('click', () => {
      setPlaying(false);
      controls.forEach((control, i) => { control.value = String(presets[button.dataset.orbitPreset!][i]); });
      position = phase.valueAsNumber;
      updateOrbit();
    });
  });
  motionPreference.addEventListener('change', () => setPlaying(false));
  document.addEventListener('visibilitychange', () => { if (document.hidden) setPlaying(false); });
  window.addEventListener('pagehide', () => setPlaying(false));
  new IntersectionObserver(([entry]) => { if (!entry.isIntersecting) setPlaying(false); }).observe(exhibit);
  field('fields').hidden = false;
  updateOrbit();
  setPlaying(false);
}
