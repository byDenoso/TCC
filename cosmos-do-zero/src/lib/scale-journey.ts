const lastStage = 4;
const clamp = (value: number, max: number) => Math.min(max, Math.max(0, value));

/** Translate document distance into scene coordinates, including uneven station heights. */
export function journeyPosition(scroll: number, stations: readonly number[]): number {
  const next = stations.findIndex(offset => offset > scroll);
  if (next < 0) return stations.length - 1;
  if (next === 0) return 0;
  return next - 1 + (scroll - stations[next - 1]) / (stations[next] - stations[next - 1]);
}

export function journeyLayers(value: number, end = lastStage) {
  const position = clamp(value, end);
  const from = Math.min(end - 1, Math.floor(position));
  const phase = position - from;
  return { from, to: from + 1, blend: phase * phase * (3 - 2 * phase) };
}

/** Monotonic interpolation from equal-spaced stops to powers of ten in metres. */
export function journeyLog(position: number, stops: readonly number[]): number {
  const bounded = clamp(position, stops.length - 1);
  const start = Math.min(stops.length - 2, Math.floor(bounded));
  return stops[start] + (stops[start + 1] - stops[start]) * (bounded - start);
}

/** One second per transition. The final keyframe has an encoded frame of its own. */
export function journeyVideoTime(value: number, duration: number): number {
  return clamp(value, Math.min(lastStage, duration - .001));
}
