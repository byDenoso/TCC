import { CHAPTER_IDS } from '../types';

const KEY = 'cosmos-v6-onde';
export interface Place { chapter: string; step: number; total: number; section: string; title: string; at: number }

/** Estado antigo ou editado no navegador nunca deve quebrar a navegação. */
export function parsePlaces(raw: string): Record<string, Place> {
  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
    const out: Record<string, Place> = {};
    for (const [id, candidate] of Object.entries(value)) {
      if (!(CHAPTER_IDS as readonly string[]).includes(id) || !candidate || typeof candidate !== 'object') continue;
      const p = candidate as Place;
      if (p.chapter !== id || !Number.isInteger(p.step) || !Number.isInteger(p.total) || p.step < 0 || p.step >= p.total || p.total > 100 ||
          typeof p.section !== 'string' || !p.section.startsWith(`${id}-`) || typeof p.title !== 'string' || !Number.isFinite(p.at)) continue;
      out[id] = p;
    }
    return out;
  } catch { return {}; }
}
function readAll(): Record<string, Place> {
  try { return parsePlaces(localStorage.getItem(KEY) ?? '{}'); } catch { return {}; }
}
export function readPlace(chapter?: string): Place | null {
  const all = readAll();
  return chapter ? all[chapter] ?? null : Object.values(all).sort((a, b) => b.at - a.at)[0] ?? null;
}
/** A completed recent visit must not hide an older unfinished lesson. */
export function latestUnfinishedPlace(places: Record<string, Place>, completed: readonly string[]): Place | null {
  return Object.values(places).filter(place=>place.step>0 && !completed.includes(place.chapter)).sort((a,b)=>b.at-a.at)[0] ?? null;
}
export function readUnfinishedPlace(completed: readonly string[]): Place | null {
  return latestUnfinishedPlace(readAll(), completed);
}
export function rememberPlace(place: Place): void {
  const all = readAll();
  all[place.chapter] = place;
  try { localStorage.setItem(KEY, JSON.stringify(all)); } catch { /* a leitura continua sem armazenamento */ }
}

