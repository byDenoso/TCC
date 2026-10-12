import { CHAPTER_IDS, PRIMARY_CHAPTER_IDS, type ChapterId } from '../types';

/** Chave mantida da versão anterior para não perder o progresso de quem já usa. */
export const PROGRESS_KEY = 'cosmos-v3-progress';

/**
 * Fronteira de persistência. Hoje: localStorage com fallback em memória.
 * Uma sincronização entre dispositivos exigiria outra implementação desta interface (ver HANDOFF_BACKEND.md).
 */
export interface ProgressStore {
  read(): ChapterId[];
  /** retorna false quando o armazenamento do navegador está indisponível (o progresso vale só para a sessão) */
  write(ids: ChapterId[]): boolean;
}
export const sanitize = (raw: unknown): ChapterId[] =>
  Array.isArray(raw) ? ([...new Set(raw.filter((id): id is ChapterId => typeof id === 'string' && (CHAPTER_IDS as readonly string[]).includes(id)))] as ChapterId[]) : [];

export function createLocalStore(storage?: () => Storage): ProgressStore {
  let memory: ChapterId[] = [];
  // Enquanto a gravação falhar, leituras devem preferir o estado mais recente da sessão
  // ao valor antigo que ainda pode estar disponível no localStorage.
  let pendingWrite = false;
  const get = storage ?? (() => localStorage);
  return {
    read() {
      if (pendingWrite) return memory.slice();
      try {
        const v = sanitize(JSON.parse(get().getItem(PROGRESS_KEY) || '[]'));
        memory = v;
        return v.slice();
      } catch {
        return memory.slice();
      }
    },
    write(ids) {
      memory = sanitize(ids);
      try {
        get().setItem(PROGRESS_KEY, JSON.stringify(memory));
        pendingWrite = false;
        return true;
      } catch {
        pendingWrite = true;
        return false;
      }
    }
  };
}
export const progressLabel = (n: number): string =>
  n >= PRIMARY_CHAPTER_IDS.length
    ? 'Você percorreu a jornada principal. Há mais perguntas para explorar.'
    : `${n <= 0 ? 'Seu caminho começa aqui' : 'Seu caminho pelo cosmos'} · ${Math.max(0, Math.trunc(n))} de ${PRIMARY_CHAPTER_IDS.length} etapas concluídas`;

/** Quantidade concluída na jornada principal; extras continuam salvos no mesmo array. */
export const mainCompletedCount = (done: ChapterId[]): number =>
  PRIMARY_CHAPTER_IDS.filter((id) => done.includes(id)).length;

/** Primeiro capítulo ainda não concluído, na ordem da jornada (ou undefined se todos foram lidos). */
export const nextUnfinished = (done: ChapterId[]): ChapterId | undefined => PRIMARY_CHAPTER_IDS.find((id) => !done.includes(id));
