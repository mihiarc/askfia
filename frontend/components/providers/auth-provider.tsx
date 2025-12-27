"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/hooks/use-auth";

// Hero/landing page is public, chat requires auth
const PUBLIC_PATHS = ["/", "/login"];

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
      router.push("/login");
    } else if (isAuthenticated && pathname === "/login") {
      router.push("/");
    }
  }, [isAuthenticated, isLoading, pathname, router]);

  // Check if on a public path
  const isPublicPath = PUBLIC_PATHS.includes(pathname);

  // Show loading state only for protected paths
  if (isLoading && !isPublicPath) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin h-8 w-8 border-4 border-forest-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  // Don't render protected content until authenticated
  if (!isAuthenticated && !isPublicPath) {
    return null;
  }

  return <>{children}</>;
}
