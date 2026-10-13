/** Coordenadas comóveis ilustrativas, em passos de distância arbitrários. */
export const expansionPositions: [number, number, number][] = [
  [0,0,0], [-1.9,.75,1.05], [1.9,-.65,-1.6], [-1.3,1.7,-3.2], [.4,-2.1,1.9],
  [-3.4,-1.3,-2.5], [3.4,1.7,-2.4], [-2.8,2.2,1], [3,-1.8,2.5], [.9,2.5,-5],
  [-4.2,1.2,-1], [4.5,-.2,.3], [2.4,-1.5,-5], [-2.5,-3.3,-4]
];
export function separation(i: number, observer: number): number {
  const p = expansionPositions[i], o = expansionPositions[observer];
  return Math.hypot(p[0]-o[0],p[1]-o[1],p[2]-o[2]);
}
export function expandedPosition(i: number, observer: number, scale: number): [number,number,number] {
  return expansionPositions[i].map((v,k)=>(v-expansionPositions[observer][k])*scale) as [number,number,number];
}
