export const solarTemperature = 5772;

export const hrDomain = {
  minTemperature: 2500,
  maxTemperature: 30000,
  minLogRadius: -2,
  maxLogRadius: 2,
  minLogLuminosity: -6,
  maxLogLuminosity: 7,
};

export const hrPlot = { left: 53, right: 455, top: 38, bottom: 282 };

export const hrModels = [
  { id: 'sol', label: 'Sol', temperature: solarTemperature, logRadius: 0, dx: 11, dy: 4, color: '#ffd694', insight: 'A referência solar marca uma luminosidade solar. O Sol está na sequência principal.' },
  { id: 'quente', label: 'Estrela quente', temperature: 22000, logRadius: 0.8, dx: 11, dy: 4, color: '#98ccff', insight: 'Este exemplo da sequência principal tem uma superfície quente e uma área emissora maior que a do Sol.' },
  { id: 'gigante', label: 'Gigante vermelha', temperature: 3800, logRadius: 1.8, dx: -11, dy: -11, color: '#ff996e', insight: 'Mesmo mais fria que o Sol, uma gigante vermelha pode emitir mais energia por segundo porque sua área é muito maior.' },
  { id: 'branca', label: 'Anã branca', temperature: 18000, logRadius: -2, dx: 11, dy: 4, color: '#c9d9ff', insight: 'Uma anã branca pode ser mais quente que o Sol e ainda assim emitir menos energia por segundo, pois seu raio é muito pequeno.' },
  { id: 'vermelha', label: 'Anã vermelha', temperature: 3200, logRadius: -0.6, dx: -11, dy: 4, color: '#ffae94', insight: 'Este exemplo da sequência principal tem superfície mais fria e raio menor que os do Sol. Os dois efeitos reduzem a luminosidade.' },
];

export function luminosityInSuns(temperature: number, radius: number): number {
  return radius ** 2 * (temperature / solarTemperature) ** 4;
}

export function projectHR(temperature: number, luminosity: number): { x: number; y: number } {
  const { minTemperature, maxTemperature, minLogLuminosity, maxLogLuminosity } = hrDomain;
  const { left, right, top, bottom } = hrPlot;
  const heat = Math.log10(maxTemperature / temperature) / Math.log10(maxTemperature / minTemperature);
  const light = (maxLogLuminosity - Math.log10(luminosity)) / (maxLogLuminosity - minLogLuminosity);
  return { x: left + heat * (right - left), y: top + light * (bottom - top) };
}

export const formatHR = new Intl.NumberFormat('pt-BR', { maximumSignificantDigits: 3 });
export const formatHRTemperature = new Intl.NumberFormat('pt-BR');
