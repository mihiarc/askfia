"use client";

import { useState, useEffect, useCallback } from "react";
import { Message } from "@ai-sdk/react";

const STORAGE_KEY = "askfia_conversation";
const SHOW_CHAT_KEY = "askfia_show_chat";

/**
 * Default welcome message shown to new users.
 */
export const WELCOME_MESSAGE: Message = {
  id: "welcome",
  role: "assistant",
  content: `Welcome to the Forest Inventory Explorer!

I can help you understand forest resources across the United States using data from the **USDA Forest Service Forest Inventory and Analysis (FIA)** program.

**Try asking:**
- "How much forest land is in North Carolina?"
- "Compare timber volume in Georgia, South Carolina, and Florida"
- "What are the top tree species by biomass in Oregon?"
- "Show me forest carbon stocks in California"

All statistics are computed using [pyFIA](https://github.com/mihiarc/pyfia) and validated against official USFS estimates.`,
};

interface ConversationStorageState {
  /** Whether hydration from localStorage is complete */
  isHydrated: boolean;
  /** Whether the chat interface should be shown */
  showChat: boolean;
  /** Set whether chat is shown and persist to localStorage */
  setShowChat: (show: boolean) => void;
  /** Get initial messages from localStorage or return default */
  getInitialMessages: () => Message[];
  /** Save messages to localStorage */
  saveMessages: (messages: Message[]) => void;
  /** Clear saved conversation and reset to welcome message */
  clearConversation: () => void;
}

/**
 * Hook for managing conversation persistence in localStorage.
 *
 * Handles:
 * - Loading/saving messages to localStorage
 * - Persisting chat visibility state
 * - Hydration state for SSR compatibility
 *
 * @param initialShowChat - Whether to show chat initially (e.g., from URL params)
 * @returns Conversation storage state and methods
 */
export function useConversationStorage(
  initialShowChat: boolean = false
): ConversationStorageState {
  const [isHydrated, setIsHydrated] = useState(false);
  const [showChat, setShowChatState] = useState(false);

  // Hydrate from localStorage on mount
  useEffect(() => {
    const savedShowChat = localStorage.getItem(SHOW_CHAT_KEY);

    if (initialShowChat) {
      setShowChatState(true);
    } else if (savedShowChat === "true") {
      setShowChatState(true);
    }

    setIsHydrated(true);
  }, [initialShowChat]);

  // Persist showChat state to localStorage
  const setShowChat = useCallback(
    (show: boolean) => {
      setShowChatState(show);
      if (isHydrated) {
        localStorage.setItem(SHOW_CHAT_KEY, show.toString());
      }
    },
    [isHydrated]
  );

  // Load saved messages from localStorage
  const getInitialMessages = useCallback((): Message[] => {
    if (typeof window === "undefined") return [WELCOME_MESSAGE];

    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      }
    } catch (e) {
      console.error("Failed to parse saved conversation:", e);
    }
    return [WELCOME_MESSAGE];
  }, []);

  // Save messages to localStorage
  const saveMessages = useCallback(
    (messages: Message[]) => {
      if (!isHydrated || messages.length === 0) return;

      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
      } catch (e) {
        console.error("Failed to save conversation:", e);
      }
    },
    [isHydrated]
  );

  // Clear conversation and reset to welcome message
  const clearConversation = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return {
    isHydrated,
    showChat,
    setShowChat,
    getInitialMessages,
    saveMessages,
    clearConversation,
  };
}
