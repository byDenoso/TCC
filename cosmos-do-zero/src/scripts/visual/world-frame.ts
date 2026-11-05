import { Matrix4, type Object3D } from 'three';

// Cells are exact integer metres; the bounded offset keeps local fractions in
// floating point without first rounding the large absolute position.
const CELL_METERS = 2 ** 20;
const CELL_METERS_INT = 2n ** 20n;
const HALF_CELL = CELL_METERS / 2;

export interface WorldAxis { readonly cell: bigint; readonly offsetMeters: number }
export type WorldPosition = readonly [WorldAxis, WorldAxis, WorldAxis];
export interface WorldAnchor { readonly object: Object3D; readonly position: WorldPosition }

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

/**
 * Place camera and scene anchors relative to a common origin. The caller owns
 * the physical positions and chooses scene units per metre; no existing
 * illustration is implicitly assigned physical coordinates. Anchors must have
 * no parent or an identity-transformed parent outside the set being rebased.
 */
export function rebaseWorld(origin: WorldPosition, anchors: readonly WorldAnchor[], sceneUnitsPerMeter = 1): void {
  if(!Number.isFinite(sceneUnitsPerMeter)||sceneUnitsPerMeter<=0)throw new RangeError('escala da cena inválida');
  const objects=new Set(anchors.map(anchor=>anchor.object)),identity=new Matrix4();
  for(const {object} of anchors){
    const parent=object.parent;if(!parent)continue;
    parent.updateWorldMatrix(true,false);
    if(objects.has(parent)||!parent.matrixWorld.equals(identity))throw new RangeError('âncoras exigem pai sem transformação');
  }
  const positions=anchors.map(anchor=>relativePositionMeters(anchor.position,origin).map(value=>value*sceneUnitsPerMeter));
  if(positions.some(point=>point.some(value=>!Number.isFinite(value))))throw new RangeError('posição da cena fora do intervalo numérico');
  anchors.forEach((anchor,i)=>anchor.object.position.set(positions[i][0],positions[i][1],positions[i][2]));
}
