// Cells are exact integer metres; the bounded offset keeps local fractions in
// floating point without first rounding the large absolute position.
const CELL_METERS = 2 ** 20;
const CELL_METERS_INT = 2n ** 20n;
const HALF_CELL = CELL_METERS / 2;

export interface WorldAxis { readonly cell: bigint; readonly offsetMeters: number }
export type WorldPosition = readonly [WorldAxis, WorldAxis, WorldAxis];

function axis(cell: bigint, offsetMeters: number): WorldAxis {
  if (!Number.isFinite(offsetMeters) || Math.abs(offsetMeters) > Number.MAX_SAFE_INTEGER / 2) throw new RangeError('offset em metros fora do intervalo seguro');
  const shift = Math.floor((offsetMeters + HALF_CELL) / CELL_METERS);
  return {cell:cell + BigInt(shift),offsetMeters:offsetMeters - shift * CELL_METERS};
}

/** Absolute integer metres, optionally followed by a local fractional offset. */
export function worldPositionMeters(x: bigint, y: bigint, z: bigint): WorldPosition {
  return [x,y,z].map(meters=>axis(meters / CELL_METERS_INT,Number(meters % CELL_METERS_INT))) as unknown as WorldPosition;
}

/** Small, local movement in metres; normalises offsets across cell boundaries. */
export function moveWorldPosition(position: WorldPosition, offsetMeters: readonly [number,number,number]): WorldPosition {
  return position.map((point,i)=>axis(point.cell,point.offsetMeters + offsetMeters[i])) as unknown as WorldPosition;
}

/** Subtract cells as integers before converting the camera-relative result. */
export function relativePositionMeters(position: WorldPosition, origin: WorldPosition): [number,number,number] {
  const values=position.map((point,i)=>Number(point.cell-origin[i].cell)*CELL_METERS + (point.offsetMeters-origin[i].offsetMeters));
  if(values.some(value=>!Number.isFinite(value)))throw new RangeError('distância relativa fora do intervalo numérico');
  return values as [number,number,number];
}
