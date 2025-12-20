"use client";

import { useChat } from "@ai-sdk/react";
import { ChatInterface } from "@/components/chat/chat-interface";

export default function Home() {
  const {
    messages,
    input,
    handleInputChange,
    handleSubmit,
    isLoading,
    stop,
    error,
    reload,
  } = useChat({
    api: "/api/chat",
    initialMessages: [
      {
        id: "welcome",
        role: "assistant",
        content: `Welcome to the Forest Inventory Explorer! 🌲

I can help you understand forest resources across the United States using data from the **USDA Forest Service Forest Inventory and Analysis (FIA)** program.

**Try asking:**
- "How much forest land is in North Carolina?"
- "Compare timber volume in Georgia, South Carolina, and Florida"
- "What are the top tree species by biomass in Oregon?"
- "Show me forest carbon stocks in California"

All statistics are computed using [pyFIA](https://github.com/mihiarc/pyfia) and validated against official USFS estimates.`,
      },
    ],
  });

  const suggestions = [
    "How much forest is in Georgia?",
    "Compare forest area in NC, SC, and VA",
    "What's the timber volume in Oregon?",
    "Show carbon stocks in California",
  ];

  return (
    <div className="container mx-auto max-w-4xl">
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
      />
    </div>
  );
}
