"use client";

import { useEffect } from "react";
import { useChat, Message } from "@ai-sdk/react";
import { API_CONFIG } from "@/lib/config/api";
import {
  useConversationStorage,
  WELCOME_MESSAGE,
} from "./use-conversation-storage";

/**
 * Default query suggestions for the chat interface.
 */
export const DEFAULT_SUGGESTIONS = [
  "How much forest is in Georgia?",
  "Compare forest area in NC, SC, and VA",
  "What's the timber volume in Oregon?",
  "Show carbon stocks in California",
];

interface UseForestChatOptions {
  /** Whether to show chat initially (e.g., from URL params) */
  initialShowChat?: boolean;
  /** Called when authentication is required */
  onAuthRequired?: () => void;
}

interface UseForestChatReturn {
  // Chat state
  messages: Message[];
  setMessages: (messages: Message[]) => void;
  input: string;
  handleInputChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  handleSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
  stop: () => void;
  error?: Error;
  reload: () => void;

  // UI state
  isHydrated: boolean;
  showChat: boolean;
  setShowChat: (show: boolean) => void;
  suggestions: string[];

  // Actions
  handleNewChat: () => void;
  handleBackToHero: () => void;
}

/**
 * Hook for forest inventory chat functionality.
 *
 * Combines useChat from AI SDK with conversation persistence and
 * project-specific configuration.
 *
 * @param options - Configuration options
 * @returns Chat state and methods
 */
export function useForestChat({
  initialShowChat = false,
  onAuthRequired,
}: UseForestChatOptions = {}): UseForestChatReturn {
  const {
    isHydrated,
    showChat,
    setShowChat,
    getInitialMessages,
    saveMessages,
    clearConversation,
  } = useConversationStorage(initialShowChat);

  const {
    messages,
    setMessages,
    input,
    handleInputChange,
    handleSubmit: originalHandleSubmit,
    isLoading,
    stop,
    error,
    reload,
  } = useChat({
    api: `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.chat.stream}`,
    credentials: "include",
    initialMessages: getInitialMessages(),
    onError: (error) => {
      // Check if this is an auth error
      if (
        error.message.includes("401") ||
        error.message.includes("unauthorized")
      ) {
        onAuthRequired?.();
      }
    },
  });

  // Persist messages to localStorage when they change
  useEffect(() => {
    if (isHydrated && messages.length > 0) {
      saveMessages(messages);
    }
  }, [messages, isHydrated, saveMessages]);

  // Handle form submission with auth check
  const handleSubmit = (e: React.FormEvent) => {
    originalHandleSubmit(e);
  };

  // Start a new conversation
  const handleNewChat = () => {
    setMessages([WELCOME_MESSAGE]);
    clearConversation();
  };

  // Go back to hero section
  const handleBackToHero = () => {
    setShowChat(false);
  };

  return {
    // Chat state
    messages,
    setMessages,
    input,
    handleInputChange,
    handleSubmit,
    isLoading,
    stop,
    error,
    reload,

    // UI state
    isHydrated,
    showChat,
    setShowChat,
    suggestions: DEFAULT_SUGGESTIONS,

    // Actions
    handleNewChat,
    handleBackToHero,
  };
}
