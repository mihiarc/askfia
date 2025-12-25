"use client";

import { useRef, useEffect } from "react";
import { Message } from "@ai-sdk/react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  Send,
  StopCircle,
  RefreshCw,
  TreeDeciduous,
  User,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ChatInterfaceProps {
  messages: Message[];
  input: string;
  onInputChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
  onStop: () => void;
  error?: Error;
  onReload: () => void;
  suggestions?: string[];
}

export function ChatInterface({
  messages,
  input,
  onInputChange,
  onSubmit,
  isLoading,
  onStop,
  error,
  onReload,
  suggestions = [],
}: ChatInterfaceProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Get the last message content for scroll trigger during streaming
  const lastMessage = messages[messages.length - 1];
  const lastMessageContent = lastMessage?.content || "";

  // Auto-scroll to bottom on new messages and during streaming
  useEffect(() => {
    if (scrollRef.current) {
      // Find the actual scrollable viewport inside ScrollArea
      const viewport = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (viewport) {
        viewport.scrollTop = viewport.scrollHeight;
      }
    }
  }, [messages, lastMessageContent, isLoading]);

  // Focus input on load
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (input.trim()) {
        onSubmit(e as unknown as React.FormEvent);
      }
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    const event = {
      target: { value: suggestion },
    } as React.ChangeEvent<HTMLTextAreaElement>;
    onInputChange(event);
    // Auto-submit after brief delay
    setTimeout(() => {
      const form = document.querySelector("form");
      form?.requestSubmit();
    }, 100);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)]">
      {/* Messages Area */}
      <ScrollArea className="flex-1 p-4" ref={scrollRef}>
        <div className="space-y-6 max-w-3xl mx-auto">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {isLoading && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Sparkles className="h-4 w-4 animate-pulse text-primary" />
              <span className="text-sm">Querying FIA data...</span>
            </div>
          )}

          {error && (
            <Card className="p-4 border-destructive bg-destructive/10">
              <p className="text-sm text-destructive">Error: {error.message}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={onReload}
                className="mt-2"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Retry
              </Button>
            </Card>
          )}
        </div>
      </ScrollArea>

      {/* Suggestions (show when few messages) */}
      {messages.length <= 1 && suggestions.length > 0 && (
        <div className="px-4 pb-2 max-w-3xl mx-auto w-full">
          <p className="text-sm text-muted-foreground mb-2">Try one of these:</p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((suggestion, i) => (
              <Button
                key={i}
                variant="outline"
                size="sm"
                onClick={() => handleSuggestionClick(suggestion)}
                className="text-xs"
              >
                {suggestion}
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="border-t bg-background p-4">
        <form
          onSubmit={onSubmit}
          className="flex gap-2 max-w-3xl mx-auto"
        >
          <Textarea
            ref={inputRef}
            value={input}
            onChange={onInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask about forest inventory..."
            className="min-h-[60px] max-h-[200px] resize-none flex-1"
            disabled={isLoading}
          />
          {isLoading ? (
            <Button
              type="button"
              onClick={onStop}
              variant="destructive"
              size="icon"
              className="h-[60px] w-[60px]"
            >
              <StopCircle className="h-5 w-5" />
            </Button>
          ) : (
            <Button
              type="submit"
              disabled={!input.trim()}
              size="icon"
              className="h-[60px] w-[60px]"
            >
              <Send className="h-5 w-5" />
            </Button>
          )}
        </form>
        <p className="text-xs text-muted-foreground mt-2 text-center">
          Data from USDA Forest Service FIA • Validated with{" "}
          <a
            href="https://github.com/mihiarc/pyfia"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-foreground"
          >
            pyFIA
          </a>
        </p>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <Avatar className="h-8 w-8 shrink-0">
        <AvatarFallback
          className={cn(
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-green-600 text-white"
          )}
        >
          {isUser ? (
            <User className="h-4 w-4" />
          ) : (
            <TreeDeciduous className="h-4 w-4" />
          )}
        </AvatarFallback>
      </Avatar>

      <Card
        className={cn(
          "max-w-[85%] p-4",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        )}
      >
        {/* Tool invocations */}
        {message.toolInvocations && message.toolInvocations.length > 0 && (
          <div className="space-y-2 mb-3">
            {message.toolInvocations.map((tool, i) => (
              <ToolCallDisplay key={i} tool={tool} />
            ))}
          </div>
        )}

        {/* Message content */}
        {message.content && (
          <div
            className={cn(
              "prose-chat",
              isUser ? "prose-invert" : ""
            )}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          </div>
        )}
      </Card>
    </div>
  );
}

interface ToolCall {
  toolCallId: string;
  toolName: string;
  args: Record<string, unknown>;
  state: "partial-call" | "call" | "result";
  result?: unknown;
}

function ToolCallDisplay({ tool }: { tool: ToolCall }) {
  const toolLabels: Record<string, string> = {
    query_forest_area: "Forest Area",
    query_timber_volume: "Timber Volume",
    query_biomass_carbon: "Biomass & Carbon",
    query_trees_per_acre: "Trees Per Acre",
    query_mortality: "Mortality",
    query_growth: "Growth",
    compare_states: "State Comparison",
  };

  const label = toolLabels[tool.toolName] || tool.toolName;
  const states = (tool.args.states as string[]) || [];

  if (tool.state === "call" || tool.state === "partial-call") {
    return (
      <div className="flex items-center gap-2 text-muted-foreground text-sm">
        <Sparkles className="h-3 w-3 animate-pulse" />
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
    <div className="flex items-center gap-2 text-sm">
      <TreeDeciduous className="h-3 w-3 text-green-600" />
      <span className="font-medium">{label}</span>
      {states.length > 0 && (
        <Badge variant="secondary" className="text-xs">
          {states.join(", ")}
        </Badge>
      )}
    </div>
  );
}
