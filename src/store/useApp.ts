import { create } from 'zustand';
import { persist, createJSONStorage, type StateStorage } from 'zustand/middleware';
import { get, set, del } from 'idb-keyval';

// Abstracción de almacenamiento: hoy IndexedDB local; mañana se puede sustituir por sincronización.
const idbStorage: StateStorage = {
  getItem: async (name) => {
    try {
      return (await get<string>(name)) ?? null;
    } catch {
      return localStorage.getItem(name);
    }
  },
  setItem: async (name, value) => {
    try {
      await set(name, value);
    } catch {
      localStorage.setItem(name, value);
    }
  },
  removeItem: async (name) => {
    try {
      await del(name);
    } catch {
      localStorage.removeItem(name);
    }
  },
};

export type Theme = 'light' | 'dark';

interface AppState {
  theme: Theme;
  disclaimerAccepted: boolean;
  favorites: string[];
  readClaims: string[];
  deviceModel: 'V60' | 'V60 Plus';
  setDeviceModel: (m: 'V60' | 'V60 Plus') => void;
  scenarioProgress: Record<string, { done: boolean; errors: number }>;
  quizStats: Record<string, { seen: number; correct: number; last: boolean }>;
  examHistory: { fecha: string; modulo: string; correctas: number; total: number; segundos: number }[];
  recordAnswers: (results: { id: string; ok: boolean }[]) => void;
  addExam: (e: { fecha: string; modulo: string; correctas: number; total: number; segundos: number }) => void;
  setScenarioResult: (id: string, errors: number) => void;
  setTheme: (t: Theme) => void;
  acceptDisclaimer: () => void;
  toggleFavorite: (id: string) => void;
  markRead: (ids: string[]) => void;
}

export const useApp = create<AppState>()(
  persist(
    (setState) => ({
      theme: window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
      disclaimerAccepted: false,
      favorites: [],
      readClaims: [],
      deviceModel: 'V60 Plus',
      setDeviceModel: (deviceModel) => setState({ deviceModel }),
      scenarioProgress: {},
      quizStats: {},
      examHistory: [],
      recordAnswers: (results) =>
        setState((s) => {
          const next = { ...s.quizStats };
          for (const r of results) {
            const p = next[r.id] ?? { seen: 0, correct: 0, last: false };
            next[r.id] = { seen: p.seen + 1, correct: p.correct + (r.ok ? 1 : 0), last: r.ok };
          }
          return { quizStats: next };
        }),
      addExam: (e) => setState((s) => ({ examHistory: [e, ...s.examHistory].slice(0, 20) })),
      setScenarioResult: (id, errors) =>
        setState((s) => {
          const prev = s.scenarioProgress[id];
          return { scenarioProgress: { ...s.scenarioProgress, [id]: { done: true, errors: prev?.done ? Math.min(prev.errors, errors) : errors } } };
        }),
      setTheme: (theme) => setState({ theme }),
      acceptDisclaimer: () => setState({ disclaimerAccepted: true }),
      toggleFavorite: (id) =>
        setState((s) => ({ favorites: s.favorites.includes(id) ? s.favorites.filter((f) => f !== id) : [...s.favorites, id] })),
      markRead: (ids) => setState((s) => ({ readClaims: Array.from(new Set([...s.readClaims, ...ids])) })),
    }),
    { name: 'v60-academy', storage: createJSONStorage(() => idbStorage) },
  ),
);
