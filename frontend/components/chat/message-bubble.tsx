"use client";

import { Message } from "@ai-sdk/react";
import { Card } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { TreeDeciduous, User } from "lucide-react";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ToolCallDisplay, ToolCall } from "./tool-call-display";

interface MessageBubbleProps {
  message: Message;
}

/**
 * Message bubble component for displaying chat messages.
 */
export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <Avatar className="h-8 w-8 shrink-0">
        <AvatarFallback
          className={cn(
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-forest-600 text-white"
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
              <ToolCallDisplay key={i} tool={tool as ToolCall} />
            ))}
          </div>
        )}

        {/* Message content */}
        {message.content && (
          <div className={cn("prose-chat", isUser ? "prose-invert" : "")}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </Card>
    </div>
  );
}
