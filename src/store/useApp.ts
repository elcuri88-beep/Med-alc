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
      setTheme: (theme) => setState({ theme }),
      acceptDisclaimer: () => setState({ disclaimerAccepted: true }),
      toggleFavorite: (id) =>
        setState((s) => ({ favorites: s.favorites.includes(id) ? s.favorites.filter((f) => f !== id) : [...s.favorites, id] })),
      markRead: (ids) => setState((s) => ({ readClaims: Array.from(new Set([...s.readClaims, ...ids])) })),
    }),
    { name: 'v60-academy', storage: createJSONStorage(() => idbStorage) },
  ),
);
