import { observeScene, type MountedScene } from '../src/scripts/visual/runtime';
import { prepareStoryExhibit } from '../src/scripts/visual/story-exhibit';

let view: MountedScene | null = null;

export async function openStory(id: string): Promise<void> {
  view?.dispose();
  const stage = document.querySelector<HTMLElement>('[data-story-world]')!;
  stage.replaceChildren();
  delete stage.dataset.visualFallback;
  stage.dataset.forceWebgl = 'true';
  const create = await prepareStoryExhibit(id);

  await new Promise<void>((resolve, reject) => {
    const controller = new AbortController();
    const finish = (error?: Error) => {
      controller.abort();
      clearTimeout(timeout);
      if (error) reject(error);
      else resolve();
    };
    const timeout = window.setTimeout(() => finish(new Error(`Tempo de montagem excedido: ${id}`)), 30_000);
    stage.addEventListener('cosmos:ready', () => finish(), { signal: controller.signal });
    stage.addEventListener('cosmos:unavailable', () => finish(new Error(`WebGL2 indisponível: ${id}`)), { signal: controller.signal });
    view = observeScene(stage, create);
  });
}

export function captureStory(progress: number, seconds: number): string {
  const canvas = document.querySelector<HTMLCanvasElement>('[data-story-world] canvas');
  if (!view || !canvas || canvas.width !== 960 || canvas.height !== 540) {
    throw new Error('Palco 3D não está pronto em 960 × 540.');
  }
  view.state({ value: progress, phase: progress, elapsed: seconds });
  // Read in the same JavaScript task so WebGL can discard the buffer after presentation.
  return canvas.toDataURL('image/png');
}
