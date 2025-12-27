"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/hooks/use-auth";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const { login, isLoading, error } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const success = await login(password);

    if (success) {
      // Check if we should return to chat
      const returnTo = searchParams.get("return");
      if (returnTo === "chat") {
        router.push("/?chat=true");
      } else {
        router.push("/");
      }
    }
  };

  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-73px)]">
      <div className="w-full max-w-md p-8 bg-card rounded-lg shadow-lg border">
        <div className="text-center mb-6">
          <span className="text-4xl">🌲</span>
          <h1 className="text-2xl font-bold mt-2">Forest Inventory Explorer</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Enter password to access the application
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium mb-1"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-green-600 focus:border-transparent"
              placeholder="Enter password"
              required
              autoFocus
            />
          </div>

          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
              <p className="text-destructive text-sm">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading || !password}
            className="w-full py-2 px-4 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <p className="text-center text-xs text-muted-foreground mt-6">
          Powered by{" "}
          <a
            href="https://github.com/mihiarc/pyfia"
            target="_blank"
            rel="noopener noreferrer"
            className="text-green-600 hover:underline"
          >
            pyFIA
          </a>{" "}
          &{" "}
          <a
            href="https://www.fia.fs.usda.gov/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-green-600 hover:underline"
          >
            USDA FIA
          </a>
        </p>
      </div>
    </div>
  );
}
