let active: (() => void) | null = null;
let mountQueue: Promise<void> = Promise.resolve();
let blocked = false;

/** Called inside mountWithGpu, before yielding ownership back to the queue. */
export function claimContext(dispose: () => void): () => void {
  if (active) throw new Error('O contexto anterior ainda não foi liberado');
  active = dispose;
  document.documentElement.dataset.cosmosContexts = '1';
  return () => {
    if (active !== dispose) return;
    active = null;
    document.documentElement.dataset.cosmosContexts = '0';
  };
}

export function mountWithGpu<T>(
  valid: () => boolean,
  mount: () => T | null | Promise<T | null>
): Promise<T | null> {
  const operation = mountQueue.then(async () => {
    if (blocked || !valid()) return null;
    try {
      active?.();
      if (active) throw new Error('Contexto não devolvido ao trocar de cena');
    } catch (error) {
      blocked = true;
      console.warn('[cosmos] descarte anterior da GPU falhou', error);
      return null;
    }
    return valid() ? mount() : null;
  });
  mountQueue = operation.then(() => {}, () => {});
  return operation;
}
