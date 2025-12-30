"""Chat endpoints with streaming support."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ...auth import get_current_user_email, require_auth
from ...models.schemas import ChatRequest
from ...services.agent import fia_agent
from ..routes.auth import get_user_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stream", dependencies=[require_auth])
async def chat_stream(
    request: ChatRequest,
    user_email: Annotated[str | None, Depends(get_current_user_email)] = None,
):
    """
    Stream chat responses using Vercel AI SDK Data Stream Protocol.

    Protocol format:
    - 0:{text} - Text delta
    - 9:{tool_call} - Tool call start
    - a:{tool_result} - Tool result
    - d:{finish} - Finish reason
    """

    async def generate() -> AsyncGenerator[str, None]:
        stream_success = False
        try:
            messages = [{"role": m.role, "content": m.content} for m in request.messages]

            async for chunk in fia_agent.stream(messages):
                if chunk["type"] == "text":
                    # Text content
                    yield f'0:{json.dumps(chunk["content"])}\n'

                elif chunk["type"] == "tool_call":
                    # Tool invocation
                    tool_data = {"toolCallId": chunk["tool_call_id"], "toolName": chunk["tool_name"], "args": chunk["args"]}
                    yield f'9:{json.dumps(tool_data)}\n'

                elif chunk["type"] == "tool_result":
                    # Tool result
                    result_data = {"toolCallId": chunk["tool_call_id"], "result": chunk["result"]}
                    yield f'a:{json.dumps(result_data)}\n'

                elif chunk["type"] == "finish":
                    # Finish
                    yield f'd:{json.dumps({"finishReason": "stop"})}\n'
                    stream_success = True

        except Exception as e:
            logger.exception("Error in chat stream")
            yield f'3:{json.dumps(str(e))}\n'

        finally:
            # Track query usage after stream completes (success or failure)
            if user_email and stream_success:
                try:
                    user_service = get_user_service()
                    count = user_service.increment_usage(user_email)
                    logger.info(f"Query usage incremented for {user_email}: {count} queries today")
                except Exception as e:
                    logger.error(f"Failed to track query usage for {user_email}: {e}")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/", dependencies=[require_auth])
async def chat(
    request: ChatRequest,
    user_email: Annotated[str | None, Depends(get_current_user_email)] = None,
):
    """Non-streaming chat endpoint (for testing)."""
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    full_response = ""
    tool_calls = []

    async for chunk in fia_agent.stream(messages):
        if chunk["type"] == "text":
            full_response += chunk["content"]
        elif chunk["type"] == "tool_call":
            tool_calls.append(chunk)
        elif chunk["type"] == "tool_result":
            # Find matching tool call and add result
            for tc in tool_calls:
                if tc.get("tool_call_id") == chunk.get("tool_call_id"):
                    tc["result"] = chunk.get("result")

    # Track query usage
    if user_email:
        try:
            user_service = get_user_service()
            count = user_service.increment_usage(user_email)
            logger.info(f"Query usage incremented for {user_email}: {count} queries today")
        except Exception as e:
            logger.error(f"Failed to track query usage for {user_email}: {e}")

    return {
        "role": "assistant",
        "content": full_response,
        "tool_calls": tool_calls if tool_calls else None,
    }
