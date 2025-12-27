import { create } from "zustand";

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  email: string | null;

  setAuthenticated: (authenticated: boolean) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setEmail: (email: string | null) => void;
  reset: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  isLoading: true,
  error: null,
  email: null,

  setAuthenticated: (authenticated) => set({ isAuthenticated: authenticated }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setEmail: (email) => set({ email }),
  reset: () =>
    set({
      isAuthenticated: false,
      isLoading: false,
      error: null,
      email: null,
    }),
}));
