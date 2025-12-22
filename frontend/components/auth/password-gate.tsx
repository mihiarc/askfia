"use client";

import { useState, useEffect, ReactNode } from "react";
import { Lock } from "lucide-react";

interface PasswordGateProps {
  children: ReactNode;
}

export function PasswordGate({ children }: PasswordGateProps) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    // Check if already authenticated
    const authToken = localStorage.getItem("pyfia_auth");
    if (authToken) {
      // Verify token is still valid
      verifyToken(authToken);
    } else {
      setIsAuthenticated(false);
    }
  }, []);

  const verifyToken = async (token: string) => {
    try {
      const response = await fetch("/api/auth/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (response.ok) {
        setIsAuthenticated(true);
      } else {
        localStorage.removeItem("pyfia_auth");
        setIsAuthenticated(false);
      }
    } catch {
      setIsAuthenticated(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });

      if (response.ok) {
        const { token } = await response.json();
        localStorage.setItem("pyfia_auth", token);
        setIsAuthenticated(true);
      } else {
        setError("Invalid password");
        setPassword("");
      }
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  // Loading state
  if (isAuthenticated === null) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    );
  }

  // Show login form if not authenticated
  if (!isAuthenticated) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center p-4">
        <div className="w-full max-w-sm">
          <div className="bg-card border rounded-lg shadow-sm p-6">
            <div className="flex flex-col items-center mb-6">
              <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mb-3">
                <Lock className="w-6 h-6 text-green-600" />
              </div>
              <h2 className="text-xl font-semibold text-foreground">
                Internal Preview
              </h2>
              <p className="text-sm text-muted-foreground text-center mt-1">
                Enter the password to access the Forest Inventory Explorer
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                  autoFocus
                  disabled={isLoading}
                />
              </div>

              {error && (
                <p className="text-sm text-red-500 text-center">{error}</p>
              )}

              <button
                type="submit"
                disabled={isLoading || !password}
                className="w-full py-2 px-4 bg-green-600 hover:bg-green-700 disabled:bg-green-400 disabled:cursor-not-allowed text-white font-medium rounded-md transition-colors"
              >
                {isLoading ? "Verifying..." : "Access"}
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  // Authenticated - show children
  return <>{children}</>;
}
