/** Estado de interface refletido na URL (querystring) sem empilhar histórico: o botão voltar sai da página, não de cada clique. */
export function getParam(name: string, search = location.search): string | null {
  return new URLSearchParams(search).get(name);
}
export function setParams(updates: Record<string, string | null>): void {
  try {
    const url = new URL(location.href);
    for (const [k, v] of Object.entries(updates)) (v === null || v === '' ? url.searchParams.delete(k) : url.searchParams.set(k, v));
    history.replaceState(history.state, '', url);
  } catch {
    /* contextos embutidos podem bloquear o histórico */
  }
}
