"use client";

import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface QueryPreviewCardProps {
  queries: string[];
  activeIndex: number;
}

/**
 * Interactive query preview card with rotating example queries.
 */
export function QueryPreviewCard({
  queries,
  activeIndex,
}: QueryPreviewCardProps) {
  return (
    <div className="max-w-2xl mx-auto">
      {/* Glassmorphism card */}
      <div className="relative rounded-2xl bg-forest-950/60 backdrop-blur-xl border border-forest-700/30 shadow-2xl shadow-black/20 overflow-hidden">
        {/* Header bar */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-forest-700/30 bg-forest-900/40">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/70" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
            <div className="w-3 h-3 rounded-full bg-green-500/70" />
          </div>
          <div className="flex-1 flex justify-center">
            <span className="text-xs text-forest-400/60 font-mono">
              Forest Inventory Explorer
            </span>
          </div>
        </div>

        {/* Query content */}
        <div className="p-6">
          <div className="flex items-start gap-3 mb-4">
            <div className="w-8 h-8 rounded-full bg-forest-600 flex items-center justify-center shrink-0">
              <Sparkles className="h-4 w-4 text-white" />
            </div>
            <div className="flex-1">
              <p className="text-sm text-forest-300 mb-2">Try asking:</p>
              <div className="relative h-8 overflow-hidden">
                {queries.map((query, index) => (
                  <p
                    key={index}
                    className={cn(
                      "absolute inset-0 text-lg md:text-xl font-medium text-white transition-all duration-500",
                      index === activeIndex
                        ? "opacity-100 translate-y-0"
                        : "opacity-0 translate-y-4"
                    )}
                  >
                    &ldquo;{query}&rdquo;
                  </p>
                ))}
              </div>
            </div>
          </div>

          {/* Query indicator dots */}
          <div className="flex justify-center gap-2">
            {queries.map((_, index) => (
              <div
                key={index}
                className={cn(
                  "w-2 h-2 rounded-full transition-all duration-300",
                  index === activeIndex ? "bg-forest-400 w-6" : "bg-forest-700"
                )}
              />
            ))}
          </div>
        </div>

        {/* Subtle shine effect */}
        <div className="absolute inset-0 bg-gradient-to-br from-white/5 via-transparent to-transparent pointer-events-none" />
      </div>
    </div>
  );
}
