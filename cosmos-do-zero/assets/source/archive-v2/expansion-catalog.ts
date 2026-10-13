/** Coordenadas comóveis ilustrativas, em passos de distância arbitrários. */
export const expansionPositions: [number, number, number][] = [
  [0,0,0], [-1.6,0.3,0.5], [1.65,-0.1,0.2], [-0.6,0.8,-1.7], [0.8,-0.4,1.7],
  [-2.9,-0.5,-1.2], [3.1,0.6,-1.3], [-2.1,0.8,2.3], [2.5,-0.6,2.8], [0.3,0.2,-3.2],
  [-3.7,0.6,1], [3.6,-0.2,1.2], [1.9,1,-3.6], [-2.6,-0.4,-3.4]
];
export function separation(i: number, observer: number): number {
  const p = expansionPositions[i], o = expansionPositions[observer];
  return Math.hypot(p[0]-o[0],p[1]-o[1],p[2]-o[2]);
}
export function expandedPosition(i: number, observer: number, scale: number): [number,number,number] {
  return expansionPositions[i].map((v,k)=>(v-expansionPositions[observer][k])*scale) as [number,number,number];
}
