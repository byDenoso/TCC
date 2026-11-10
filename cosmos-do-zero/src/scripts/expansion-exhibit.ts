import {
  EXPANSION_CHARTS, EXPANSION_DEFAULT_Z, EXPANSION_FIELDS, EXPANSION_PRESETS, EXPANSION_READINGS,
  expansionCurvature, expansionHistory, expansionNumber, expansionPlotPath, expansionPlotPoint, expansionPoint,
  type ExpansionModel,
} from '../lib/expansion-exhibit';

const reference = EXPANSION_PRESETS.planck;

export function initExpansionExhibit(): void {
  for (const root of document.querySelectorAll<HTMLElement>('[data-expansion-exhibit]')) {
    if (root.dataset.expansionReady) continue;
    const controls = root.querySelector<HTMLElement>('[data-expansion-controls]');
    const zInput = root.querySelector<HTMLInputElement>('[data-expansion-input="z"]');
    if (!controls || !zInput) continue;
    root.dataset.expansionReady = 'true';

    const inputs = EXPANSION_FIELDS.map((field) => ({
      ...field,
      input: root.querySelector<HTMLInputElement>(`[data-expansion-input="${field.key}"]`),
    }));
    const plots = Object.entries(EXPANSION_CHARTS).map(([key, chart]) => ({
      chart, node: root.querySelector(`[data-expansion-plot="${key}"]`),
    }));
    const presets = root.querySelectorAll<HTMLButtonElement>('[data-expansion-preset]');
    const status = root.querySelector<HTMLElement>('[data-expansion-status]');
    let model: ExpansionModel = { ...reference };

    const setText = (selector: string, value: string) => {
      const node = root.querySelector<HTMLElement>(selector);
      if (node) node.textContent = value;
    };

    const render = (announce = false): void => {
      const z = zInput.valueAsNumber;
      const point = expansionPoint(z, model);
      const ref = expansionPoint(z, reference);
      const zText = expansionNumber(z, 2);
      setText('[data-expansion-value="z"]', `z = ${zText}`);
      zInput.setAttribute('aria-valuetext', zText);
      setText('[data-expansion-epoch]', `Em z = ${zText}, a = ${expansionNumber(point.a, 3)} nos dois modelos.`);
      for (const { key, digits } of EXPANSION_READINGS) {
        setText(`[data-expansion-reading="${key}"]`, expansionNumber(point[key], digits));
        setText(`[data-expansion-reference="${key}"]`, expansionNumber(ref[key], digits));
      }
      for (const { chart, node } of plots) {
        if (!node) continue;
        const [x, y] = expansionPlotPoint(chart, point);
        const [rx, ry] = expansionPlotPoint(chart, ref);
        for (const [key, cx, cy] of [['active', x, y], ['reference', rx, ry]] as const) {
          const dot = node.querySelector(`[data-expansion-dot="${key}"]`);
          dot?.setAttribute('cx', String(cx));
          dot?.setAttribute('cy', String(cy));
        }
        const guide = node.querySelector('[data-expansion-guide]');
        guide?.setAttribute('x1', String(x));
        guide?.setAttribute('x2', String(x));
        guide?.setAttribute('y1', String(y));
      }
      if (announce && status) {
        status.textContent = `Seu modelo em z = ${zText}. Taxa de expansão ${expansionNumber(point.h, 1)} quilômetros por segundo por megaparsec. Tempo de viagem ${expansionNumber(point.lookback, 2)} bilhões de anos. Distância de luminosidade ${expansionNumber(point.luminosity, 0)} megaparsecs.`;
      }
    };

    function renderModel(announce = false): void {
      const history = expansionHistory(model);
      for (const { chart, node } of plots) {
        node?.querySelector('[data-expansion-curve]')?.setAttribute('d', expansionPlotPath(chart, history));
      }
      const k = expansionCurvature(model);
      const geometry = Math.abs(k) < 1e-10 ? 'plana' : k > 0 ? 'aberta' : 'fechada';
      const curvature = geometry !== 'plana' && Math.abs(k) < 0.0005 ? '|Ωₖ| < 0,001' : `Ωₖ = ${expansionNumber(k, 3)}`;
      setText('[data-expansion-geometry]', `${curvature} · geometria ${geometry}`);
      for (const { key, input, digits } of inputs) {
        const value = expansionNumber(model[key], digits);
        setText(`[data-expansion-value="${key}"]`, value);
        input?.setAttribute('aria-valuetext', value);
      }
      for (const button of presets) {
        const preset = EXPANSION_PRESETS[button.dataset.expansionPreset as keyof typeof EXPANSION_PRESETS];
        button.setAttribute('aria-pressed', String(inputs.every(({ key }) => model[key] === preset[key])));
      }
      render(announce);
    }

    function applyPreset(preset: ExpansionModel): void {
      model = { ...preset };
      for (const { key, input } of inputs) {
        if (input) input.value = String(model[key]);
      }
      renderModel(true);
    }

    for (const { key, input } of inputs) {
      input?.addEventListener('input', () => {
        model[key] = input.valueAsNumber;
        renderModel();
      });
      input?.addEventListener('change', () => render(true));
    }
    zInput.addEventListener('input', () => render());
    zInput.addEventListener('change', () => render(true));
    for (const button of presets) {
      const preset = EXPANSION_PRESETS[button.dataset.expansionPreset as keyof typeof EXPANSION_PRESETS];
      button.addEventListener('click', () => applyPreset(preset));
    }
    root.querySelector('[data-expansion-reset]')?.addEventListener('click', () => {
      zInput.value = String(EXPANSION_DEFAULT_Z);
      applyPreset(reference);
    });

    controls.hidden = false;
  }
}
