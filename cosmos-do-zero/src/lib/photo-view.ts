/** Geometria do explorador de imagens: enquadramento, limites de arraste, zoom e foco em um ponto. */
export interface ViewBox { vw: number; vh: number; cw: number; ch: number }
export interface ViewState { z: number; tx: number; ty: number }
export const MIN_ZOOM = 1;
export const MAX_ZOOM = 4;

/** Tamanho-base da imagem para cobrir a janela inteira, sem faixas vazias. */
export function coverSize(vw: number, vh: number, ratio: number): { cw: number; ch: number } {
  if (!(vw > 0) || !(vh > 0) || !(ratio > 0)) return { cw: 0, ch: 0 };
  return vw / vh > ratio ? { cw: vw, ch: vw / ratio } : { cw: vh * ratio, ch: vh };
}

/** Mantém o zoom na faixa permitida e a imagem cobrindo a janela. */
export function clampView(state: ViewState, box: ViewBox): ViewState {
  const z = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, state.z));
  const minX = box.vw - box.cw * z, minY = box.vh - box.ch * z;
  return { z, tx: Math.min(0, Math.max(minX, state.tx)), ty: Math.min(0, Math.max(minY, state.ty)) };
}

/** Centraliza um ponto da imagem (em porcentagem) na janela, até onde os limites deixam. */
export function focusOn(xPct: number, yPct: number, z: number, box: ViewBox): ViewState {
  const zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z));
  return clampView({ z: zoom, tx: box.vw / 2 - (xPct / 100) * box.cw * zoom, ty: box.vh / 2 - (yPct / 100) * box.ch * zoom }, box);
}

/** Muda o zoom mantendo fixo o ponto da janela (ax, ay). */
export function zoomAbout(state: ViewState, nextZoom: number, ax: number, ay: number, box: ViewBox): ViewState {
  const z = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, nextZoom));
  const k = z / state.z;
  return clampView({ z, tx: ax - (ax - state.tx) * k, ty: ay - (ay - state.ty) * k }, box);
}

/** Posição de um ponto da imagem dentro da janela, em pixels. */
export function spotInView(xPct: number, yPct: number, state: ViewState, box: ViewBox): { x: number; y: number } {
  return { x: state.tx + (xPct / 100) * box.cw * state.z, y: state.ty + (yPct / 100) * box.ch * state.z };
}
