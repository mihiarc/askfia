/**
 * Centralized API configuration for AskFIA frontend.
 *
 * This module consolidates API URL configuration that was previously
 * duplicated across multiple files.
 */

/**
 * API configuration object.
 *
 * - `baseUrl`: Used for client-side API calls (browser to backend)
 * - `backendUrl`: Used for server-side API calls (Next.js server to backend)
 */
export const API_CONFIG = {
  /** Base URL for client-side requests (uses NEXT_PUBLIC_ prefix for browser access) */
  baseUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",

  /** Backend URL for server-side requests (not exposed to browser) */
  backendUrl: process.env.BACKEND_URL || "http://localhost:8000",

  /** API endpoints */
  endpoints: {
    chat: {
      stream: "/api/v1/chat/stream",
    },
    auth: {
      signup: "/api/v1/auth/signup",
      login: "/api/v1/auth/login",
      verify: "/api/v1/auth/verify",
      refresh: "/api/v1/auth/refresh",
      logout: "/api/v1/auth/logout",
    },
    query: {
      area: "/api/v1/query/area",
      volume: "/api/v1/query/volume",
      biomass: "/api/v1/query/biomass",
      tpa: "/api/v1/query/tpa",
      compare: "/api/v1/query/compare",
      states: "/api/v1/query/states",
      metrics: "/api/v1/query/metrics",
    },
    downloads: {
      prepare: "/api/v1/downloads/prepare",
    },
  },
} as const;

/** Type for API configuration */
export type ApiConfig = typeof API_CONFIG;
