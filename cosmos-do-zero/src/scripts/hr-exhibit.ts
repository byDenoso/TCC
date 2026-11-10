import { formatHR, formatHRTemperature, hrModels, hrPlot, luminosityInSuns, projectHR } from '../lib/hr';

export function initHRExhibit(): void {
  document.querySelectorAll<HTMLElement>('[data-hr-exhibit]').forEach((root) => {
    const fields = root.querySelector<HTMLElement>('[data-hr-fields]');
    const temperatureInput = root.querySelector<HTMLInputElement>('[data-hr-input="temperature"]');
    const radiusInput = root.querySelector<HTMLInputElement>('[data-hr-input="radius"]');
    const temperatureReading = root.querySelector('[data-hr-reading="temperature"]');
    const radiusReading = root.querySelector('[data-hr-reading="radius"]');
    const luminosityReading = root.querySelector('[data-hr-reading="luminosity"]');
    const insight = root.querySelector('[data-hr-insight]');
    const status = root.querySelector('[data-hr-status]');
    const marker = root.querySelector('[data-hr-marker]');
    const crosshair = root.querySelector('[data-hr-crosshair]');
    const presets = root.querySelectorAll<HTMLButtonElement>('[data-hr-preset]');
    if (!fields || !temperatureInput || !radiusInput || !temperatureReading || !radiusReading || !luminosityReading || !insight || !status || !marker || !crosshair) return;

    const update = (announce = false) => {
      const temperature = temperatureInput.valueAsNumber;
      const logRadius = radiusInput.valueAsNumber;
      const radius = 10 ** logRadius;
      const luminosity = luminosityInSuns(temperature, radius);
      const model = hrModels.find((item) => item.temperature === temperature && item.logRadius === logRadius);
      const point = projectHR(temperature, luminosity);
      const temperatureText = formatHRTemperature.format(temperature);
      const radiusText = formatHR.format(radius);
      const luminosityText = formatHR.format(luminosity);

      marker.setAttribute('transform', `translate(${point.x} ${point.y})`);
      crosshair.setAttribute('d', `M${hrPlot.left} ${point.y}H${point.x}V${hrPlot.bottom}`);
      temperatureInput.setAttribute('aria-valuetext', `${temperatureText} kelvin`);
      radiusInput.setAttribute('aria-valuetext', `${radiusText} raios solares`);
      temperatureReading.textContent = `${temperatureText} K`;
      radiusReading.textContent = `${radiusText} R☉`;
      luminosityReading.textContent = `${luminosityText} L☉`;
      insight.textContent = model?.insight ?? 'No modelo livre, a temperatura desloca o ponto na horizontal e também muda a luminosidade. Alterar só o raio desloca o ponto na vertical.';
      presets.forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.hrPreset === model?.id)));
      if (announce) status.textContent = `${model ? `${model.label}. ` : ''}${temperatureText} kelvin. Raio de ${radiusText} raios solares. Luminosidade de ${luminosityText} luminosidades solares.`;
    };

    presets.forEach((button) => button.addEventListener('click', () => {
      const model = hrModels.find((item) => item.id === button.dataset.hrPreset);
      if (!model) return;
      temperatureInput.valueAsNumber = model.temperature;
      radiusInput.valueAsNumber = model.logRadius;
      update(true);
    }));
    [temperatureInput, radiusInput].forEach((input) => {
      input.addEventListener('input', () => update());
      input.addEventListener('change', () => update(true));
    });
    update();
    fields.hidden = false;
  });
}
