/** Photographic controls: f-number, shutter in seconds, and ISO sensitivity. */
export interface CameraExposure { readonly fNumber:number; readonly shutterSeconds:number; readonly iso:number }

/**
 * ISO-100 exposure value and saturation-based normalization, following the
 * Filament camera model: https://google.github.io/filament/main/filament.html
 * The result is physically interpretable only when source luminance is calibrated.
 */
export function photographicExposure(camera:CameraExposure): {ev100:number;normalization:number} {
  const {fNumber,shutterSeconds,iso}=camera;
  if([fNumber,shutterSeconds,iso].some(value=>!Number.isFinite(value)||value<=0))throw new RangeError('parâmetros de exposição inválidos');
  const ev100=2*Math.log2(fNumber)-Math.log2(shutterSeconds)+Math.log2(100)-Math.log2(iso);
  const normalization=2**(-ev100)/1.2;
  if(!Number.isFinite(normalization)||normalization<=0)throw new RangeError('exposição fora do intervalo numérico');
  return {ev100,normalization};
}
