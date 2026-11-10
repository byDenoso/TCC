import {
  TRANSIT_KIND_LABELS, TRANSIT_PRESETS, TRANSIT_VIEW,
  transitPercent, transitPlot, transitPlotPoint, transitSnapshot,
  type TransitModel,
} from '../lib/transit';

const formatDecimal = (minimumFractionDigits: number, maximumFractionDigits = minimumFractionDigits) =>
  new Intl.NumberFormat('pt-BR', { minimumFractionDigits, maximumFractionDigits });
const planetFormat = formatDecimal(0, 1);
const inclinationFormat = formatDecimal(1);
const twoDecimals = formatDecimal(2);
const impactFormat = formatDecimal(3);
const parameters = ['planet', 'star', 'inclination', 'phase'] as const;

export function initTransitExhibit(): void {
  const exhibit = document.querySelector<HTMLElement>('[data-transit-exhibit]');
  if (!exhibit || exhibit.dataset.transitReady) return;
  const find = <T extends Element>(selector: string) => exhibit.querySelector<T>(selector)!;
  const fields = find<HTMLElement>('[data-transit-controls]');
  const [planet, star, inclination, phase] = parameters.map((key) => find<HTMLInputElement>(`[data-transit-input="${key}"]`));
  const outputs = parameters.map((key) => find<HTMLOutputElement>(`[data-transit-value="${key}"]`));
  const buttons = [...exhibit.querySelectorAll<HTMLButtonElement>('[data-transit-preset]')];
  const [disk, silhouette, ring, marker] = ['star', 'planet', 'ring', 'dot'].map((key) => find<SVGCircleElement>(`[data-transit-${key}]`));
  const track = find<SVGPathElement>('[data-transit-track]');
  const curve = find<SVGPathElement>('[data-transit-curve]');
  const chart = find<SVGSVGElement>('[data-transit-chart]');
  const sky = find<SVGSVGElement>('[data-transit-sky]');
  const cursor = find<SVGLineElement>('[data-transit-cursor]');
  const ticks = [0, 1, 2].map((index) => find<SVGTextElement>(`[data-transit-tick="${index}"]`));
  const [kind, depth, flux, impact, status] = ['kind', 'depth', 'flux', 'impact', 'status'].map((key) => find<HTMLElement>(`[data-transit-${key}]`));
  const { x, y, solarRadius } = TRANSIT_VIEW.geometry;
  let scale: number;

  function readModel(): TransitModel {
    return { planet: planet.valueAsNumber, star: star.valueAsNumber, inclination: inclination.valueAsNumber };
  }

  function position(circle: SVGCircleElement, cx: number, cy: number) {
    circle.setAttribute('cx', String(cx));
    circle.setAttribute('cy', String(cy));
  }

  function updatePhase() {
    const offset = phase.valueAsNumber;
    const current = transitSnapshot(readModel(), offset);
    const [px, py] = transitPlotPoint(offset, current.loss, scale);
    const cx = x + current.x * solarRadius;
    const cy = y + current.y * solarRadius;
    position(silhouette, cx, cy);
    position(ring, cx, cy);
    position(marker, px, py);
    cursor.setAttribute('x1', String(px));
    cursor.setAttribute('x2', String(px));
    flux.textContent = transitPercent(current.flux);
    const value = `${offset > 0 ? '+' : ''}${twoDecimals.format(offset)}`;
    outputs[3].value = `${value}%`;
    phase.setAttribute('aria-valuetext', `${value} por cento do período orbital`);
    sky.setAttribute('aria-label', `Projeção no céu. ${current.loss > 0 ? 'O planeta cobre parte da estrela.' : 'Os discos não se sobrepõem.'} O traçado pontilhado marca o caminho do planeta.`);
  }

  function updateModel() {
    const model = readModel();
    const plot = transitPlot(model);
    scale = plot.scale;
    const radius = plot.center.radius * solarRadius;
    disk.setAttribute('r', String(model.star * solarRadius));
    silhouette.setAttribute('r', String(radius));
    ring.setAttribute('r', String(Math.max(5.5, radius + 4)));
    track.setAttribute('d', plot.track);
    curve.setAttribute('d', plot.curve);
    ticks.forEach((tick, index) => { tick.textContent = transitPercent(1 - scale * index / 2); });
    const planetValue = planetFormat.format(model.planet);
    const starValue = twoDecimals.format(model.star);
    const inclinationValue = inclinationFormat.format(model.inclination);
    outputs[0].value = `${planetValue} R⊕`;
    outputs[1].value = `${starValue} R☉`;
    outputs[2].value = `${inclinationValue}°`;
    planet.setAttribute('aria-valuetext', `${planetValue} ${model.planet === 1 ? 'raio terrestre' : 'raios terrestres'}`);
    star.setAttribute('aria-valuetext', `${starValue} ${model.star === 1 ? 'raio solar' : 'raios solares'}`);
    inclination.setAttribute('aria-valuetext', `${inclinationValue} graus`);
    kind.textContent = TRANSIT_KIND_LABELS[plot.center.kind];
    depth.textContent = transitPercent(plot.center.loss);
    impact.textContent = impactFormat.format(plot.center.impact);
    chart.setAttribute('aria-label', `Curva de luz simulada. ${kind.textContent}. Queda máxima de ${depth.textContent}. O eixo horizontal vai de menos três a mais três por cento do período orbital.`);
    for (const button of buttons) {
      const preset = TRANSIT_PRESETS[button.dataset.transitPreset as keyof typeof TRANSIT_PRESETS];
      button.setAttribute('aria-pressed', String(preset.planet === model.planet && preset.star === model.star && preset.inclination === model.inclination));
    }
    updatePhase();
  }

  function announce() {
    status.textContent = `${kind.textContent}. Queda máxima de ${depth.textContent}. Fluxo na fase de ${flux.textContent}.`;
  }

  function applyPreset(preset: TransitModel) {
    planet.value = String(preset.planet);
    star.value = String(preset.star);
    inclination.value = String(preset.inclination);
    phase.value = phase.defaultValue;
    updateModel();
    announce();
  }

  for (const control of [planet, star, inclination]) control.addEventListener('input', updateModel);
  phase.addEventListener('input', updatePhase);
  for (const control of [planet, star, inclination, phase]) control.addEventListener('change', announce);
  for (const button of buttons) button.addEventListener('click', () => applyPreset(TRANSIT_PRESETS[button.dataset.transitPreset as keyof typeof TRANSIT_PRESETS]));
  find<HTMLButtonElement>('[data-transit-reset]').addEventListener('click', () => applyPreset(TRANSIT_PRESETS.giant));
  updateModel();
  exhibit.dataset.transitReady = 'true';
  fields.hidden = false;
}
