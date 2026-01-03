import { NextRequest } from "next/server";
import { API_CONFIG } from "@/lib/config/api";

export const maxDuration = 60;

export async function POST(req: NextRequest) {
  const { messages } = await req.json();

  try {
    // Forward cookies from the client to the backend for authentication
    const cookies = req.headers.get("cookie") || "";

    const response = await fetch(
      `${API_CONFIG.backendUrl}${API_CONFIG.endpoints.chat.stream}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Cookie: cookies,
        },
        body: JSON.stringify({ messages }),
      }
    );

    if (!response.ok) {
      const error = await response.text();
      return new Response(JSON.stringify({ error }), {
        status: response.status,
        headers: { "Content-Type": "application/json" },
      });
    }

    // Stream the response back to the client
    return new Response(response.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  } catch (error) {
    console.error("Backend error:", error);
    return new Response(
      JSON.stringify({ error: "Failed to connect to backend" }),
      {
        status: 502,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}
