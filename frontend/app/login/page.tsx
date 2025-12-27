"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/hooks/use-auth";

function LoginForm() {
  const [email, setEmail] = useState("");
  const { signup, isLoading, error } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const result = await signup(email);

    if (result.success) {
      // Check if we should return to chat
      const returnTo = searchParams.get("return");
      if (returnTo === "chat") {
        router.push("/?chat=true");
      } else {
        router.push("/");
      }
    }
  };

  // Basic email validation
  const isValidEmail = (email: string) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  };

  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-73px)]">
      <div className="w-full max-w-md p-8 bg-card rounded-lg shadow-lg border">
        <div className="text-center mb-6">
          <span className="text-4xl">🌲</span>
          <h1 className="text-2xl font-bold mt-2">Forest Inventory Explorer</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Enter your email to start exploring
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium mb-1"
            >
              Email Address
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-green-600 focus:border-transparent"
              placeholder="you@example.com"
              required
              autoFocus
              autoComplete="email"
            />
          </div>

          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
              <p className="text-destructive text-sm">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading || !isValidEmail(email)}
            className="w-full py-2 px-4 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? "Getting started..." : "Get Started"}
          </button>
        </form>

        <p className="text-center text-xs text-muted-foreground mt-4">
          By continuing, you agree to receive updates about the Forest Inventory Explorer.
        </p>

        <p className="text-center text-xs text-muted-foreground mt-4">
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

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin h-8 w-8 border-4 border-forest-600 border-t-transparent rounded-full" />
      </div>
    }>
      <LoginForm />
    </Suspense>
  );
}
