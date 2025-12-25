"use client";

import { useCallback } from "react";
import { useAuthStore } from "@/stores/auth-store";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AuthResponse {
  authenticated: boolean;
  message: string;
}

export function useAuth() {
  const {
    isAuthenticated,
    isLoading,
    error,
    setAuthenticated,
    setLoading,
    setError,
    reset,
  } = useAuthStore();

  const login = useCallback(
    async (password: string): Promise<boolean> => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`${API_URL}/api/v1/auth/login`, {
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
      } catch (err) {
        setError("Network error. Please try again.");
        return false;
      } finally {
        setLoading(false);
      }
    },
    [setAuthenticated, setError, setLoading]
  );

  const logout = useCallback(async (): Promise<void> => {
    try {
      await fetch(`${API_URL}/api/v1/auth/logout`, {
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
      const response = await fetch(`${API_URL}/api/v1/auth/verify`, {
        method: "GET",
        credentials: "include",
      });

      const data: AuthResponse = await response.json();
      setAuthenticated(data.authenticated);
      return data.authenticated;
    } catch {
      setAuthenticated(false);
      return false;
    } finally {
      setLoading(false);
    }
  }, [setAuthenticated, setLoading]);

  const refresh = useCallback(async (): Promise<boolean> => {
    try {
      const response = await fetch(`${API_URL}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });

      const data: AuthResponse = await response.json();

      if (data.authenticated) {
        setAuthenticated(true);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, [setAuthenticated]);

  return {
    isAuthenticated,
    isLoading,
    error,
    login,
    logout,
    verify,
    refresh,
  };
}
