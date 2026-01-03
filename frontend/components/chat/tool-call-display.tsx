"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TreeDeciduous, Sparkles, ChevronDown, ChevronUp } from "lucide-react";
import { getToolLabel } from "@/lib/constants/tool-labels";

export interface ToolCall {
  toolCallId: string;
  toolName: string;
  args: Record<string, unknown>;
  state: "partial-call" | "call" | "result";
  result?: unknown;
}

interface ToolCallDisplayProps {
  tool: ToolCall;
}

/**
 * Tool call display component for showing FIA query tool invocations.
 */
export function ToolCallDisplay({ tool }: ToolCallDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const label = getToolLabel(tool.toolName);
  const states = (tool.args.states as string[]) || [];
  const hasResult =
    tool.state === "result" && tool.result !== undefined && tool.result !== null;

  if (tool.state === "call" || tool.state === "partial-call") {
    return (
      <div className="flex items-center gap-2 text-muted-foreground text-sm">
        <Sparkles className="h-3 w-3 animate-pulse text-forest-500" />
        <span>Querying {label}...</span>
        {states.length > 0 && (
          <Badge variant="outline" className="text-xs">
            {states.join(", ")}
          </Badge>
        )}
      </div>
    );
  }

  return (
    <div className="text-sm">
      <div className="flex items-center gap-2">
        <TreeDeciduous className="h-3 w-3 text-forest-600" />
        <span className="font-medium">{label}</span>
        {states.length > 0 && (
          <Badge variant="secondary" className="text-xs">
            {states.join(", ")}
          </Badge>
        )}
        {hasResult ? (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs ml-auto"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? (
              <>
                Hide data <ChevronUp className="h-3 w-3 ml-1" />
              </>
            ) : (
              <>
                View data <ChevronDown className="h-3 w-3 ml-1" />
              </>
            )}
          </Button>
        ) : null}
      </div>

      {/* Expandable raw data section */}
      {isExpanded && hasResult ? (
        <div className="mt-2 p-3 bg-background/50 rounded-lg border text-xs font-mono overflow-x-auto">
          <pre className="whitespace-pre-wrap">
            {JSON.stringify(tool.result, null, 2)}
          </pre>
        </div>
      ) : null}
    </div>
  );
}
