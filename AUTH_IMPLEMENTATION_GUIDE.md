# Authentication Implementation Guide

This guide explains how to implement password-based JWT authentication with HTTP-only cookies for a FastAPI backend and Next.js frontend.

## Overview

This authentication system provides:
- Shared team password authentication (no user accounts)
- JWT tokens stored in HTTP-only secure cookies
- Dual-token system (access + refresh tokens)
- Optional authentication (can be disabled for public deployments)

---

## Prerequisites

### Backend (Python/FastAPI)
```bash
uv add fastapi pyjwt bcrypt python-dotenv pydantic-settings
```

### Frontend (Next.js/React)
```bash
npm install zustand
```

---

## Part 1: Backend Implementation

### Step 1: Configuration

Create a settings module to manage authentication configuration.

**`app/config.py`**
```python
from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Authentication Settings
    auth_password_hash: Optional[str] = Field(
        default=None,
        alias="AUTH_PASSWORD_HASH",
        description="bcrypt hash of the shared password",
    )
    auth_jwt_secret: Optional[str] = Field(
        default=None,
        alias="AUTH_JWT_SECRET",
        description="Secret key for JWT signing",
    )
    auth_access_token_expire: int = Field(
        default=1800,  # 30 minutes
        alias="AUTH_ACCESS_TOKEN_EXPIRE",
    )
    auth_refresh_token_expire: int = Field(
        default=604800,  # 7 days
        alias="AUTH_REFRESH_TOKEN_EXPIRE",
    )

    @property
    def auth_enabled(self) -> bool:
        """Check if authentication is enabled."""
        return bool(self.auth_password_hash and self.auth_jwt_secret)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

### Step 2: Auth Endpoints

Create the authentication router with login, logout, refresh, and verify endpoints.

**`app/api/v1/auth.py`**
```python
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, Cookie, Response
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# --- Request/Response Models ---

class LoginRequest(BaseModel):
    """Login request with password."""
    password: str


class AuthResponse(BaseModel):
    """Authentication response."""
    authenticated: bool
    message: str


# --- Token Functions ---

def create_token(token_type: str, expires_delta: timedelta) -> str:
    """Create a JWT token.

    Args:
        token_type: Either "access" or "refresh"
        expires_delta: Token validity duration

    Returns:
        Encoded JWT token string
    """
    settings = get_settings()
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "type": token_type,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.auth_jwt_secret, algorithm="HS256")


def verify_token(token: str, token_type: str) -> bool:
    """Verify a JWT token.

    Args:
        token: The JWT token to verify
        token_type: Expected token type ("access" or "refresh")

    Returns:
        True if token is valid, False otherwise
    """
    settings = get_settings()
    if not settings.auth_jwt_secret:
        return False

    try:
        payload = jwt.decode(token, settings.auth_jwt_secret, algorithms=["HS256"])
        return payload.get("type") == token_type
    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return False
    except jwt.InvalidTokenError as e:
        logger.debug(f"Invalid token: {e}")
        return False


def set_auth_cookies(response: Response) -> None:
    """Set authentication cookies on response.

    Creates both access and refresh tokens and sets them as HTTP-only cookies.
    """
    settings = get_settings()

    access_token = create_token(
        "access",
        timedelta(seconds=settings.auth_access_token_expire),
    )
    refresh_token = create_token(
        "refresh",
        timedelta(seconds=settings.auth_refresh_token_expire),
    )

    # Access token cookie - available to all paths
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=settings.auth_access_token_expire,
    )

    # Refresh token cookie - only available to auth endpoints
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/api/v1/auth",
        max_age=settings.auth_refresh_token_expire,
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear authentication cookies."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")


# --- Endpoints ---

@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, response: Response) -> AuthResponse:
    """Authenticate with password and receive JWT tokens in cookies."""
    settings = get_settings()

    if not settings.auth_enabled:
        return AuthResponse(
            authenticated=True,
            message="Authentication disabled",
        )

    # Verify password using bcrypt
    password_bytes = request.password.encode("utf-8")
    hash_bytes = settings.auth_password_hash.encode("utf-8")

    if not bcrypt.checkpw(password_bytes, hash_bytes):
        logger.warning("Failed login attempt")
        return AuthResponse(
            authenticated=False,
            message="Invalid password",
        )

    # Set auth cookies
    set_auth_cookies(response)

    logger.info("Successful login")
    return AuthResponse(
        authenticated=True,
        message="Login successful",
    )


@router.post("/logout", response_model=AuthResponse)
async def logout(response: Response) -> AuthResponse:
    """Clear authentication tokens."""
    clear_auth_cookies(response)
    return AuthResponse(
        authenticated=False,
        message="Logged out successfully",
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None),
) -> AuthResponse:
    """Refresh access token using refresh token."""
    settings = get_settings()

    if not settings.auth_enabled:
        return AuthResponse(
            authenticated=True,
            message="Authentication disabled",
        )

    if not refresh_token:
        return AuthResponse(
            authenticated=False,
            message="No refresh token",
        )

    if not verify_token(refresh_token, "refresh"):
        clear_auth_cookies(response)
        return AuthResponse(
            authenticated=False,
            message="Invalid refresh token",
        )

    # Issue new tokens
    set_auth_cookies(response)

    return AuthResponse(
        authenticated=True,
        message="Token refreshed",
    )


@router.get("/verify", response_model=AuthResponse)
async def verify(
    access_token: Optional[str] = Cookie(default=None),
) -> AuthResponse:
    """Verify if current session is authenticated."""
    settings = get_settings()

    if not settings.auth_enabled:
        return AuthResponse(
            authenticated=True,
            message="Authentication disabled",
        )

    if not access_token:
        return AuthResponse(
            authenticated=False,
            message="Not authenticated",
        )

    if verify_token(access_token, "access"):
        return AuthResponse(
            authenticated=True,
            message="Authenticated",
        )

    return AuthResponse(
        authenticated=False,
        message="Invalid or expired token",
    )
```

### Step 3: Auth Dependency (Middleware)

Create a dependency to protect routes.

**`app/dependencies.py`**
```python
from typing import Optional

from fastapi import Cookie, HTTPException, status

from app.config import get_settings


async def require_auth(
    access_token: Optional[str] = Cookie(default=None),
) -> None:
    """Dependency that requires valid authentication.

    Use this as a dependency on routes or routers that need protection.

    Raises:
        HTTPException: 401 if not authenticated
    """
    from app.api.v1.auth import verify_token

    settings = get_settings()

    # Skip auth check if authentication is disabled
    if not settings.auth_enabled:
        return

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    if not verify_token(access_token, "access"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
```

### Step 4: Apply Auth to Routes

Apply the `require_auth` dependency to protected routers.

**`app/api/v1/protected_router.py`**
```python
from fastapi import APIRouter, Depends

from app.dependencies import require_auth

# All routes in this router require authentication
router = APIRouter(
    prefix="/protected",
    tags=["Protected"],
    dependencies=[Depends(require_auth)],
)


@router.get("/data")
async def get_protected_data():
    """This endpoint requires authentication."""
    return {"message": "You are authenticated!"}
```

### Step 5: FastAPI Main Application

Configure CORS and include routers.

**`app/main.py`**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, protected_router

app = FastAPI(title="My API")

# CORS configuration - IMPORTANT for cookie-based auth
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # Local development
        "https://yourdomain.com",     # Production frontend
    ],
    allow_credentials=True,  # Required for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(protected_router.router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health():
    """Public health check endpoint."""
    return {"status": "healthy"}
```

---

## Part 2: Frontend Implementation

### Step 1: Auth Store (Zustand)

Create a store to manage authentication state.

**`stores/auth-store.ts`**
```typescript
import { create } from "zustand";

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  setAuthenticated: (authenticated: boolean) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  isLoading: true,
  error: null,

  setAuthenticated: (authenticated) => set({ isAuthenticated: authenticated }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  reset: () =>
    set({
      isAuthenticated: false,
      isLoading: false,
      error: null,
    }),
}));
```

### Step 2: Auth Hook

Create a hook for authentication operations.

**`lib/hooks/use-auth.ts`**
```typescript
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
          credentials: "include", // IMPORTANT: Include cookies
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
```

### Step 3: Auth Provider Component

Create a provider to wrap your application and handle auth state.

**`components/providers/auth-provider.tsx`**
```typescript
"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/hooks/use-auth";

const PUBLIC_PATHS = ["/login"];

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading, verify } = useAuth();

  // Verify authentication on mount
  useEffect(() => {
    verify();
  }, [verify]);

  // Handle redirects based on auth state
  useEffect(() => {
    if (isLoading) return;

    const isPublicPath = PUBLIC_PATHS.includes(pathname);

    if (!isAuthenticated && !isPublicPath) {
      // Redirect to login if not authenticated
      router.push("/login");
    } else if (isAuthenticated && pathname === "/login") {
      // Redirect away from login if authenticated
      router.push("/");
    }
  }, [isAuthenticated, isLoading, pathname, router]);

  // Show loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  // Don't render protected content until authenticated
  const isPublicPath = PUBLIC_PATHS.includes(pathname);
  if (!isAuthenticated && !isPublicPath) {
    return null;
  }

  return <>{children}</>;
}
```

### Step 4: Login Page

Create a login page component.

**`app/login/page.tsx`**
```typescript
"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const { login, isLoading, error } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await login(password);
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="w-full max-w-md p-8 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl font-bold text-center mb-6">Login</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="password" className="block text-sm font-medium">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full mt-1 px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter password"
              required
            />
          </div>

          {error && (
            <p className="text-red-500 text-sm">{error}</p>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {isLoading ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
```

### Step 5: Wrap App with Auth Provider

Update your root layout to include the auth provider.

**`app/layout.tsx`**
```typescript
import { AuthProvider } from "@/components/providers/auth-provider";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
```

---

## Part 3: Environment Setup

### Generate Password Hash

Use this Python script to generate a bcrypt hash for your password:

```python
import bcrypt

password = "your_secure_password"
salt = bcrypt.gensalt()
hash_value = bcrypt.hashpw(password.encode("utf-8"), salt)
print(hash_value.decode("utf-8"))
```

### Generate JWT Secret

```python
import secrets
print(secrets.token_urlsafe(32))
```

### Backend `.env` File

```bash
# Authentication
AUTH_PASSWORD_HASH=$2b$12$xxxxx...  # bcrypt hash from above
AUTH_JWT_SECRET=your-generated-secret-key
AUTH_ACCESS_TOKEN_EXPIRE=1800      # 30 minutes (optional)
AUTH_REFRESH_TOKEN_EXPIRE=604800   # 7 days (optional)
```

### Frontend `.env.local` File

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Part 4: Security Considerations

### 1. Cookie Security

The implementation uses secure cookie settings:
- `httponly=True` - Prevents JavaScript access (XSS protection)
- `secure=True` - Only sent over HTTPS
- `samesite="none"` - Required for cross-origin requests with `secure=True`

### 2. Token Security

- Access tokens are short-lived (30 minutes default)
- Refresh tokens are longer-lived but restricted to auth endpoints only
- Token type claim prevents using refresh tokens as access tokens

### 3. CORS Configuration

For cookie-based auth to work cross-origin:
- `allow_credentials=True` is required
- Specific origins must be listed (no wildcards with credentials)

### 4. Password Security

- Passwords are hashed with bcrypt (never stored plain-text)
- Hash is stored in environment variable, not in code

---

## Part 5: Testing

### Test Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "your_password"}' \
  -c cookies.txt

# Check cookies were set
cat cookies.txt
```

### Test Protected Endpoint

```bash
curl http://localhost:8000/api/v1/protected/data \
  -b cookies.txt
```

### Test Verify

```bash
curl http://localhost:8000/api/v1/auth/verify \
  -b cookies.txt
```

---

## Part 6: Optional Authentication

To disable authentication (for development or public deployments):

1. Remove or comment out `AUTH_PASSWORD_HASH` and `AUTH_JWT_SECRET` from `.env`
2. The `auth_enabled` property will return `False`
3. All protected endpoints will be publicly accessible

---

## Troubleshooting

### Cookies Not Being Set

1. Check CORS configuration includes your frontend origin
2. Ensure `credentials: "include"` in fetch requests
3. For local development, both frontend and backend should use `localhost` (not `127.0.0.1`)

### 401 Errors

1. Verify cookies are being sent with requests (check browser DevTools → Network tab)
2. Check token hasn't expired
3. Ensure `require_auth` dependency is correctly applied

### CORS Errors

1. Verify `allow_credentials=True` in CORS middleware
2. Check origin is explicitly listed (no wildcards)
3. Ensure `Access-Control-Allow-Credentials: true` header is present

---

## Summary

This authentication system provides:

| Feature | Implementation |
|---------|----------------|
| Auth type | Shared password with JWT tokens |
| Token storage | HTTP-only secure cookies |
| Token algorithm | HS256 (HMAC-SHA256) |
| Password hashing | bcrypt |
| Access token TTL | 30 minutes (configurable) |
| Refresh token TTL | 7 days (configurable) |
| Optional auth | Disable via environment variables |

The system is designed to be simple, secure, and production-ready while remaining flexible enough to adapt to different deployment scenarios.
