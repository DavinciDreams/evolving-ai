"""Interaction endpoints: /chat, /chat/stream, /v1/chat/completions, /v1/models."""

import asyncio
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from starlette.responses import StreamingResponse

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.core.runtime import RuntimeBusyError
from evolving_agent.utils.config import config
from evolving_agent.utils.deps import get_agent, verify_api_key
from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.schemas import (
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
    QueryRequest,
    QueryResponse,
)

logger = setup_logger(__name__)

router = APIRouter()


def _public_error(exc: Exception) -> str:
    if isinstance(exc, RuntimeBusyError):
        return "Katbot is busy; retry after the current operation finishes"
    if isinstance(exc, TimeoutError):
        return "Katbot reached its response deadline; check runtime status before retrying"
    return "Katbot could not complete this response; inspect value-free runtime telemetry"


def _estimate_token_count(text: str) -> int:
    """Estimate token count for usage reporting."""
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        return max(1, len(text) // 4)


@router.post("/chat", response_model=QueryResponse, tags=["Interaction"], dependencies=[Depends(verify_api_key)])
async def chat_with_agent(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    current_agent: SelfImprovingAgent = Depends(get_agent),
):
    """
    Send a query to the agent and receive a response.

    The agent will:
    - Process your query using its knowledge and memory
    - Generate an intelligent response
    - Evaluate the response quality
    - Store the interaction for future learning
    - Update its knowledge base if new insights are discovered
    """
    try:
        query_id = str(uuid.uuid4())
        timestamp = datetime.now()

        logger.info("Processing query {}", query_id)

        # Process the query
        response = await current_agent.run(
            request.query,
            context_hints=request.context_hints,
            conversation_id=request.conversation_id,
            wait_for_storage=True,
        )

        return QueryResponse(
            response=response,
            query_id=query_id,
            timestamp=timestamp,
            evaluation_score=current_agent.last_evaluation_score,
            memory_stored=getattr(current_agent, "last_storage_status", {}).get("memory_stored", False),
            knowledge_updated=getattr(current_agent, "last_storage_status", {}).get("knowledge_updated", False),
        )

    except Exception as e:
        logger.error("Chat failed: {}", type(e).__name__)
        status = 409 if isinstance(e, RuntimeBusyError) else 504 if isinstance(e, TimeoutError) else 500
        raise HTTPException(status_code=status, detail=_public_error(e)) from None


@router.post(
    "/v1/chat/completions",
    response_model=ChatCompletionResponse,
    tags=["OpenAI Compatible"],
    summary="OpenAI-compatible chat completions",
    dependencies=[Depends(verify_api_key)],
)
async def openai_chat_completions(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    current_agent: SelfImprovingAgent = Depends(get_agent),
):
    """
    OpenAI-compatible chat completions endpoint (non-streaming).

    Accepts the standard OpenAI ChatCompletion request format and returns
    a compatible response. The agent uses its configured LLM provider
    regardless of the `model` field value.
    """
    try:
        # Extract system messages as context hints
        system_messages = [
            msg.content for msg in request.messages if msg.role == "system"
        ]
        context_hints = system_messages if system_messages else None

        # Extract the last user message as the query
        user_messages = [msg for msg in request.messages if msg.role == "user"]
        if not user_messages:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "message": "At least one message with role 'user' is required.",
                        "type": "invalid_request_error",
                        "param": "messages",
                        "code": None,
                    }
                },
            )

        query = user_messages[-1].content
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        conversation_id = request.user or completion_id
        created_timestamp = int(datetime.now().timestamp())

        # Build conversation history from the OpenAI messages array.
        # Pair up user/assistant messages (excluding the last user message which is the query).
        non_system_messages = [msg for msg in request.messages if msg.role != "system"]
        conversation_history = []
        i = 0
        while i < len(non_system_messages) - 1:  # -1 to exclude the final user message (query)
            msg = non_system_messages[i]
            if msg.role == "user":
                entry = {"query": msg.content, "response": ""}
                # Check if next message is an assistant response
                if i + 1 < len(non_system_messages) - 1 and non_system_messages[i + 1].role == "assistant":
                    entry["response"] = non_system_messages[i + 1].content
                    i += 2
                else:
                    i += 1
                conversation_history.append(entry)
            elif msg.role == "assistant":
                # Standalone assistant message (rare but possible)
                conversation_history.append({"query": "", "response": msg.content})
                i += 1
            else:
                i += 1

        logger.info("OpenAI-compatible request {}", completion_id)

        # Handle streaming
        if request.stream:
            import json as _json

            async def openai_stream():
                try:
                    response_text = await current_agent.run(
                        query,
                        context_hints=context_hints,
                        conversation_id=conversation_id,
                        conversation_history=conversation_history if conversation_history else None,
                        wait_for_storage=True,
                    )

                    # Stream the response in chunks
                    chunk_size = 50
                    for i in range(0, len(response_text), chunk_size):
                        chunk = response_text[i:i + chunk_size]
                        delta = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created_timestamp,
                            "model": request.model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": chunk},
                                "finish_reason": None,
                            }],
                        }
                        yield f"data: {_json.dumps(delta)}\n\n"

                    # Final chunk with finish_reason
                    final = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created_timestamp,
                        "model": request.model,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop",
                        }],
                    }
                    yield f"data: {_json.dumps(final)}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    error_chunk = {
                        "error": {"message": _public_error(e), "type": "internal_error"}
                    }
                    yield f"data: {_json.dumps(error_chunk)}\n\n"

            return StreamingResponse(
                openai_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )

        response_text = await current_agent.run(
            query,
            context_hints=context_hints,
            conversation_id=conversation_id,
            conversation_history=conversation_history if conversation_history else None,
            wait_for_storage=True,
        )

        # Estimate token usage
        prompt_text = " ".join(msg.content for msg in request.messages)
        prompt_tokens = _estimate_token_count(prompt_text)
        completion_tokens = _estimate_token_count(response_text)

        return ChatCompletionResponse(
            id=completion_id,
            object="chat.completion",
            created=created_timestamp,
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=response_text,
                    ),
                    finish_reason="stop",
                )
            ],
            usage=ChatCompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("OpenAI-compatible request failed: {}", type(e).__name__)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": _public_error(e),
                    "type": "internal_error",
                    "param": None,
                    "code": None,
                }
            },
        )


@router.post("/chat/stream", tags=["Interaction"], summary="Chat with streaming + tool visibility", dependencies=[Depends(verify_api_key)])
async def chat_stream(
    request: Request,
    current_agent: SelfImprovingAgent = Depends(get_agent),
):
    """
    Streaming chat endpoint with tool-use visibility via SSE.

    Streams events as Server-Sent Events:
    - `chunk`: text content from the LLM
    - `tool_call`: tool invocation (name + arguments)
    - `tool_result`: tool execution output
    - `complete`: final response with metadata
    - `error`: error information
    """
    import json as _json

    try:
        body = await request.json()
        query = body.get("query", "")
        context_hints = body.get("context_hints")
        conversation_id = body.get("conversation_id")

        if not query:
            raise HTTPException(status_code=400, detail="query is required")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid request body") from None

    async def event_stream():
        # Buffer through the same guarded, redacting path as normal chat.
        # Raw provider/tool fragments may split a secret across chunks.
        try:
            full_text = await current_agent.run(
                query, context_hints=context_hints,
                conversation_id=conversation_id, wait_for_storage=True,
            )
            for offset in range(0, len(full_text), 256):
                event_data = _json.dumps({"type": "chunk", "content": full_text[offset:offset + 256]})
                yield f"data: {event_data}\n\n"
            complete = _json.dumps({
                "type": "complete", "text": full_text, "tool_calls_count": 0,
                "buffered": True, "evaluation_score": current_agent.last_evaluation_score,
                **getattr(current_agent, "last_storage_status", {}),
            })
            yield f"data: {complete}\n\n"
        except Exception as exc:
            message = _public_error(exc)
            yield f"data: {_json.dumps({'type': 'error', 'message': message})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/v1/models", tags=["OpenAI Compatible"], summary="List available models")
async def list_models():
    """List available models (OpenAI-compatible)."""
    model_id = f"{config.default_llm_provider}/{config.default_model}"
    return {
        "object": "list",
        "data": [
            {
                "id": model_id,
                "object": "model",
                "created": 0,
                "owned_by": "evolving-ai",
            }
        ],
    }
