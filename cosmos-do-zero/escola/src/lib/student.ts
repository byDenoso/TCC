import { useEffect, useState } from 'react';
import type { Entry } from './records';
export const CLASSROOM = 'https://cosmos-do-zero.vercel.app';
const guestKey = 'cosmos-escola:estudo:v1';
type Account = { name: string; role: string };
type Store = { entries: Entry[]; account: Account | null; loaded: boolean; sync: string };
let state: Store = { entries: [], account: null, loaded: false, sync: '' },
  started = false;
const watchers = new Set<() => void>();
function publish(part: Partial<Store>) {
  state = { ...state, ...part };
  watchers.forEach((f) => f());
}
function local(): Entry[] {
  try {
    const data = JSON.parse(localStorage.getItem(guestKey) || '[]');
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}
export function isPages() {
  return (
    process.env.NEXT_PUBLIC_COSMOS_STATIC === '1' ||
    (typeof location !== 'undefined' && location.hostname === 'cosmos.denerpereira.com.br')
  );
}
export async function api(op: string, body?: unknown) {
  const response = await fetch(
    '/api/school/?op=' + encodeURIComponent(op),
    body === undefined
      ? { cache: 'no-store' }
      : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
  );
  let data;
  try {
    data = await response.json();
  } catch {
    throw Error('O serviço de contas está indisponível.');
  }
  if (!response.ok) throw Error(data.message ?? 'Falha ao salvar. Tente novamente.');
  return data;
}
export async function loadStudent() {
  if (isPages()) {
    publish({ loaded: true, entries: local(), account: null });
    return;
  }
  try {
    const result = await api('session');
    publish({
      loaded: true,
      account: result.account ?? null,
      entries: result.account ? result.entries : local(),
      sync: '',
    });
  } catch {
    if (!state.account) publish({ loaded: true, entries: local() });
    else publish({ sync: 'A conexão com a conta caiu. Recarregue para sincronizar.' });
  }
}
function init() {
  if (started) return;
  started = true;
  void loadStudent();
  window.addEventListener('storage', (e) => {
    if (e.key === guestKey && !state.account) publish({ entries: local() });
  });
}
export function useStudent() {
  const [value, set] = useState(state);
  useEffect(() => {
    const listener = () => set(state);
    watchers.add(listener);
    listener();
    init();
    return () => {
      watchers.delete(listener);
    };
  }, []);
  return value;
}
export async function record(input: Omit<Entry, 'id' | 'at'>) {
  if (!state.loaded) await loadStudent();
  const event = { ...input, id: crypto.randomUUID(), at: Date.now() };
  if (state.account) {
    try {
      const result = await api('record', { event });
      publish({
        entries: [...state.entries.filter((e) => e.id !== result.event.id), result.event],
        sync: '',
      });
      return result.event as Entry;
    } catch (e) {
      publish({ sync: (e as Error).message });
      throw e;
    }
  }
  const save = () => {
    const merged = Array.from(
      new Map([...local(), ...state.entries, event].map((e) => [e.id, e])).values()
    ).sort((a, b) => a.at - b.at);
    try {
      localStorage.setItem(guestKey, JSON.stringify(merged));
      publish({ entries: merged, sync: '' });
    } catch {
      publish({
        entries: [...state.entries, event],
        sync: 'O navegador bloqueou o armazenamento. O registro dura até o fechamento desta página.',
      });
    }
  };
  if (navigator.locks) await navigator.locks.request(guestKey, save);
  else save();
  return event;
}
export async function importGuest() {
  const items = local();
  for (let start = 0; start < items.length; start += 50)
    await api('import', { events: items.slice(start, start + 50) });
  await loadStudent();
}
export function guestCount() {
  return typeof window === 'undefined' ? 0 : local().length;
}
export function usePublished() {
  const [items, set] = useState<Editorial[]>([]);
  useEffect(() => {
    const url = (isPages() ? CLASSROOM : '') + '/api/school/?op=published';
    const ctl = new AbortController();
    fetch(url, { signal: ctl.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.items) set(data.items);
      })
      .catch(() => {});
    return () => ctl.abort();
  }, []);
  return items;
}
export type Editorial = {
  key: string;
  version: number;
  status: string;
  payload: {
    type: string;
    title: string;
    body: string;
    level: number;
    subject: string;
    lab: string;
    reference: string;
    question: string;
    answer: string;
    unit: string;
    tolerance: number;
    options?: string[];
  };
};
