"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { AlertCircle, Lightbulb, RefreshCw } from "lucide-react";

interface ErrorHelp {
  title: string;
  description: string;
  suggestions: string[];
}

interface EnhancedErrorCardProps {
  error: Error;
  errorHelp: ErrorHelp;
  onReload: () => void;
}

/**
 * Enhanced error card with contextual help and suggestions.
 */
export function EnhancedErrorCard({
  errorHelp,
  onReload,
}: EnhancedErrorCardProps) {
  return (
    <Card className="p-4 border-destructive/50 bg-destructive/5">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-full bg-destructive/10">
          <AlertCircle className="h-5 w-5 text-destructive" />
        </div>
        <div className="flex-1">
          <h4 className="font-medium text-destructive">{errorHelp.title}</h4>
          <p className="text-sm text-muted-foreground mt-1">
            {errorHelp.description}
          </p>

          <div className="mt-3 space-y-1">
            <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
              <Lightbulb className="h-3 w-3" />
              Suggestions:
            </p>
            <ul className="text-xs text-muted-foreground space-y-0.5">
              {errorHelp.suggestions.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>

          <Button variant="outline" size="sm" onClick={onReload} className="mt-3">
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    </Card>
  );
}

/**
 * Get contextual error help based on error message.
 */
export function getErrorHelp(error: Error): ErrorHelp {
  const message = error.message.toLowerCase();

  if (message.includes("network") || message.includes("fetch")) {
    return {
      title: "Connection Error",
      description:
        "Unable to reach the server. Please check your internet connection.",
      suggestions: [
        "Check your network connection",
        "Try refreshing the page",
        "Wait a moment and retry",
      ],
    };
  }

  if (message.includes("timeout")) {
    return {
      title: "Request Timeout",
      description: "The query took too long to process.",
      suggestions: [
        "Try a simpler query",
        "Ask about fewer states at once",
        "Retry the request",
      ],
    };
  }

  if (message.includes("401") || message.includes("unauthorized")) {
    return {
      title: "Authentication Error",
      description: "Your session may have expired.",
      suggestions: [
        "Refresh the page to re-authenticate",
        "Clear browser cookies and try again",
      ],
    };
  }

  return {
    title: "Something Went Wrong",
    description: error.message || "An unexpected error occurred.",
    suggestions: [
      "Try rephrasing your question",
      "Start a new conversation",
      "Retry the request",
    ],
  };
}
