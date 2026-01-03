"use client";

import { useCallback } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { API_CONFIG } from "@/lib/config/api";

interface AuthResponse {
  authenticated: boolean;
  message: string;
  email?: string | null;
  is_new_user?: boolean | null;
}

export function useAuth() {
  const {
    isAuthenticated,
    isLoading,
    error,
    email,
    setAuthenticated,
    setLoading,
    setError,
    setEmail,
    reset,
  } = useAuthStore();

  // Legacy password login (kept for backwards compatibility)
  const login = useCallback(
    async (password: string): Promise<boolean> => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.auth.login}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ password }),
        });

        const data: AuthResponse = await response.json();

        if (data.authenticated) {
          setAuthenticated(true);
          return true;
        } else {
          setError(data.message || "Login failed");
          return false;
        }
      } catch {
        setError("Network error. Please try again.");
        return false;
      } finally {
        setLoading(false);
      }
    },
    [setAuthenticated, setError, setLoading]
  );

  // Email signup/login
  const signup = useCallback(
    async (userEmail: string): Promise<{ success: boolean; isNewUser?: boolean }> => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.auth.signup}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ email: userEmail }),
        });

        const data: AuthResponse = await response.json();

        if (data.authenticated) {
          setAuthenticated(true);
          setEmail(data.email || userEmail);
          return { success: true, isNewUser: data.is_new_user ?? undefined };
        } else {
          setError(data.message || "Signup failed");
          return { success: false };
        }
      } catch {
        setError("Network error. Please try again.");
        return { success: false };
      } finally {
        setLoading(false);
      }
    },
    [setAuthenticated, setEmail, setError, setLoading]
  );

  const logout = useCallback(async (): Promise<void> => {
    try {
      await fetch(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.auth.logout}`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      reset();
    }
  }, [reset]);

  const verify = useCallback(async (): Promise<boolean> => {
    setLoading(true);

    try {
      const response = await fetch(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.auth.verify}`, {
        method: "GET",
        credentials: "include",
      });

      const data: AuthResponse = await response.json();
      setAuthenticated(data.authenticated);
      if (data.email) {
        setEmail(data.email);
      }
      return data.authenticated;
    } catch {
      setAuthenticated(false);
      return false;
    } finally {
      setLoading(false);
    }
  }, [setAuthenticated, setEmail, setLoading]);

  const refresh = useCallback(async (): Promise<boolean> => {
    try {
      const response = await fetch(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.auth.refresh}`, {
        method: "POST",
        credentials: "include",
      });

      const data: AuthResponse = await response.json();

      if (data.authenticated) {
        setAuthenticated(true);
        if (data.email) {
          setEmail(data.email);
        }
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, [setAuthenticated, setEmail]);

  return {
    isAuthenticated,
    isLoading,
    error,
    email,
    login,
    signup,
    logout,
    verify,
    refresh,
  };
}
