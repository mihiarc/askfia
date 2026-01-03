"use client";

import { useRef, useEffect } from "react";
import { Message } from "@ai-sdk/react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Send,
  StopCircle,
  TreeDeciduous,
  Sparkles,
  ExternalLink,
  Home,
  MessageSquarePlus,
} from "lucide-react";
import { MessageBubble } from "./message-bubble";
import { EnhancedErrorCard, getErrorHelp } from "./enhanced-error-card";

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
  onBackToHero?: () => void;
  onNewChat?: () => void;
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
  onBackToHero,
  onNewChat,
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

  // Show fewer suggestions after first exchange, but keep them visible
  const userMessageCount = messages.filter(m => m.role === "user").length;
  const visibleSuggestions = userMessageCount === 0
    ? suggestions
    : suggestions.slice(0, 2);
  const showSuggestions = !isLoading && visibleSuggestions.length > 0;

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <header className="border-b bg-card/95 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Clickable logo to go back to hero */}
            <button
              onClick={onBackToHero}
              className="w-9 h-9 rounded-lg bg-gradient-to-br from-forest-500 to-forest-700 flex items-center justify-center hover:from-forest-400 hover:to-forest-600 transition-all duration-200 cursor-pointer"
              title="Back to home"
            >
              <TreeDeciduous className="h-5 w-5 text-white" />
            </button>
            <div>
              <h1 className="text-lg font-semibold text-foreground">
                Forest Inventory Explorer
              </h1>
              <p className="text-xs text-muted-foreground">
                AI-powered FIA data interface
              </p>
            </div>
          </div>
          <nav className="flex items-center gap-2">
            {/* New Chat Button */}
            {onNewChat && (
              <Button
                variant="outline"
                size="sm"
                onClick={onNewChat}
                className="gap-1.5"
                title="Start new conversation"
              >
                <MessageSquarePlus className="h-4 w-4" />
                <span className="hidden sm:inline">New Chat</span>
              </Button>
            )}
            {/* Back to Hero Button */}
            {onBackToHero && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onBackToHero}
                className="gap-1.5"
                title="Back to home"
              >
                <Home className="h-4 w-4" />
                <span className="hidden sm:inline">Home</span>
              </Button>
            )}
            <div className="hidden md:flex items-center gap-4 ml-2 pl-2 border-l">
              <a
                href="https://github.com/mihiarc/pyfia"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                pyFIA
                <ExternalLink className="h-3 w-3" />
              </a>
              <a
                href="https://www.fia.fs.usda.gov/"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                FIA Program
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </nav>
        </div>
      </header>

      {/* Messages Area */}
      <ScrollArea className="flex-1 p-4" ref={scrollRef}>
        <div className="space-y-6 max-w-3xl mx-auto">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {isLoading && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Sparkles className="h-4 w-4 animate-pulse text-forest-500" />
              <span className="text-sm">Querying FIA data...</span>
            </div>
          )}

          {error && (
            <EnhancedErrorCard
              error={error}
              errorHelp={getErrorHelp(error)}
              onReload={onReload}
            />
          )}
        </div>
      </ScrollArea>

      {/* Suggestions (always visible but fewer after first exchange) */}
      {showSuggestions && (
        <div className="px-4 pb-2 max-w-3xl mx-auto w-full">
          <p className="text-sm text-muted-foreground mb-2">
            {userMessageCount === 0 ? "Try one of these:" : "More questions:"}
          </p>
          <div className="flex flex-wrap gap-2">
            {visibleSuggestions.map((suggestion, i) => (
              <Button
                key={i}
                variant="outline"
                size="sm"
                onClick={() => handleSuggestionClick(suggestion)}
                className="text-xs hover:bg-forest-50 hover:border-forest-300 dark:hover:bg-forest-950 dark:hover:border-forest-700"
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
              className="h-[60px] w-[60px] bg-forest-600 hover:bg-forest-500"
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
