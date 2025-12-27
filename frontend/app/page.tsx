"use client";

import { useState, useRef, useEffect, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useChat, Message } from "@ai-sdk/react";
import { ChatInterface } from "@/components/chat/chat-interface";
import { HeroSection } from "@/components/hero/hero-section";
import { useAuth } from "@/lib/hooks/use-auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STORAGE_KEY = "askfia_conversation";
const SHOW_CHAT_KEY = "askfia_show_chat";

const WELCOME_MESSAGE: Message = {
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

function HomeContent() {
  const [showChat, setShowChat] = useState(false);
  const [isHydrated, setIsHydrated] = useState(false);
  const chatRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, verify } = useAuth();

  // Verify auth status on mount
  useEffect(() => {
    verify();
  }, [verify]);

  // Load initial state from localStorage after hydration
  // Also check if returning from login with chat=true param
  useEffect(() => {
    const chatParam = searchParams.get("chat");
    const savedShowChat = localStorage.getItem(SHOW_CHAT_KEY);

    if (chatParam === "true" && isAuthenticated) {
      setShowChat(true);
      // Clean up URL
      router.replace("/", { scroll: false });
    } else if (savedShowChat === "true" && isAuthenticated) {
      setShowChat(true);
    }
    setIsHydrated(true);
  }, [searchParams, isAuthenticated, router]);

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

  const {
    messages,
    setMessages,
    input,
    handleInputChange,
    handleSubmit,
    isLoading,
    stop,
    error,
    reload,
  } = useChat({
    api: `${API_URL}/api/v1/chat/stream`,
    credentials: "include",
    initialMessages: getInitialMessages(),
  });

  // Persist messages to localStorage when they change
  useEffect(() => {
    if (isHydrated && messages.length > 0) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
      } catch (e) {
        console.error("Failed to save conversation:", e);
      }
    }
  }, [messages, isHydrated]);

  // Persist showChat state
  useEffect(() => {
    if (isHydrated) {
      localStorage.setItem(SHOW_CHAT_KEY, showChat.toString());
    }
  }, [showChat, isHydrated]);

  const suggestions = [
    "How much forest is in Georgia?",
    "Compare forest area in NC, SC, and VA",
    "What's the timber volume in Oregon?",
    "Show carbon stocks in California",
  ];

  const handleStartExploring = () => {
    if (!isAuthenticated) {
      // Redirect to login, will return with ?chat=true
      router.push("/login?return=chat");
      return;
    }
    setShowChat(true);
  };

  const handleBackToHero = () => {
    setShowChat(false);
  };

  const handleNewChat = () => {
    // Clear conversation and start fresh
    setMessages([WELCOME_MESSAGE]);
    localStorage.removeItem(STORAGE_KEY);
  };

  // Scroll to chat when it becomes visible
  useEffect(() => {
    if (showChat && chatRef.current) {
      chatRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [showChat]);

  // Don't render until hydrated to avoid flash
  if (!isHydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      {!showChat && <HeroSection onStartExploring={handleStartExploring} />}

      {/* Chat Interface */}
      {showChat && (
        <div ref={chatRef} className="container mx-auto max-w-4xl animate-fade-in-up">
          <ChatInterface
            messages={messages}
            input={input}
            onInputChange={handleInputChange}
            onSubmit={handleSubmit}
            isLoading={isLoading}
            onStop={stop}
            error={error}
            onReload={reload}
            suggestions={suggestions}
            onBackToHero={handleBackToHero}
            onNewChat={handleNewChat}
          />
        </div>
      )}
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    }>
      <HomeContent />
    </Suspense>
  );
}
