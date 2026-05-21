"""Interaction endpoints: /chat, /chat/stream, /v1/chat/completions, /v1/models."""

import asyncio
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from starlette.responses import StreamingResponse

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.core.evaluator import EvaluationResult
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

        logger.info(f"Processing query {query_id}: {request.query[:100]}...")

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
            memory_stored=True,
            knowledge_updated=True,
        )

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


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

        logger.info(f"OpenAI-compat request {completion_id}: {query[:100]}... ({len(conversation_history)} prior turns)")

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
                        "error": {"message": str(e), "type": "internal_error"}
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
        logger.error(f"Error in OpenAI-compat completions: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": str(e),
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
        raise HTTPException(status_code=400, detail=f"Invalid request body: {e}")

    async def event_stream():
        try:
            from ai_sdk import stream_text
            from evolving_agent.core.tools import get_all_tools

            # Build context (reusing agent internals)
            current_agent.interaction_count += 1
            context = await current_agent.context_manager.get_relevant_context(
                query=query, context_types=context_hints
            )

            conversation_history = []
            if conversation_id:
                try:
                    conversation_history = await current_agent.data_manager.get_conversation_history(
                        conversation_id, limit=10
                    )
                except Exception:
                    pass

            # Use the same system prompt and messages format as _generate_response
            system_prompt = current_agent._build_system_prompt()
            messages = current_agent._build_messages(query, context, conversation_history)

            tools = []
            if config.enable_tool_use:
                tools = get_all_tools(
                    web_search=current_agent.web_search,
                    memory=current_agent.memory,
                    tpmjs_client=current_agent.tpmjs_client,
                    enable_tpmjs=bool(current_agent.tpmjs_client),
                    e2b_sandbox=current_agent.e2b_sandbox,
                )

            model = current_agent._get_ai_sdk_model()

            def _run_stream():
                return stream_text(
                    model=model,
                    system=system_prompt,
                    messages=messages,
                    tools=tools if tools else None,
                    max_steps=config.max_tool_iterations,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                    on_step=lambda step: None,
                )

            stream_result = await asyncio.to_thread(_run_stream)

            # Stream text chunks
            full_text = ""
            async for chunk in stream_result.text_stream:
                full_text += chunk
                event_data = _json.dumps({"type": "chunk", "content": chunk})
                yield f"data: {event_data}\n\n"

            # Send tool call/result info if available
            if stream_result.tool_results:
                for tr in stream_result.tool_results:
                    tc_event = _json.dumps({
                        "type": "tool_call",
                        "tool_name": tr.tool_name,
                        "tool_call_id": tr.tool_call_id,
                    })
                    yield f"data: {tc_event}\n\n"

                    tr_event = _json.dumps({
                        "type": "tool_result",
                        "tool_name": tr.tool_name,
                        "result": str(tr.result)[:1000],
                        "is_error": tr.is_error,
                    })
                    yield f"data: {tr_event}\n\n"

            # Final complete event
            evaluation = EvaluationResult(
                overall_score=0.8,
                criteria_scores={},
                strengths=[],
                weaknesses=[],
                improvement_suggestions=[],
                feedback="Streaming interaction stored without evaluation",
                confidence=1.0,
                metadata={"streaming": True},
            )
            current_agent.last_evaluation_score = evaluation.overall_score
            await current_agent._post_response_work(
                query=query,
                final_response=full_text,
                initial_response=full_text,
                context=context,
                evaluation=evaluation,
                conversation_id=conversation_id,
            )

            complete_event = _json.dumps({
                "type": "complete",
                "text": full_text,
                "tool_calls_count": len(stream_result.tool_results) if stream_result.tool_results else 0,
            })
            yield f"data: {complete_event}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}")
            error_event = _json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_event}\n\n"

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
