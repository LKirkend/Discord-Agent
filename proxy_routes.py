"""
File: proxy_routes.py
Description:
    Implements the OpenAI-compatible translation proxy completions and models
    endpoints, mapping incoming OpenAI client requests to corresponding backend LLMs.
Author: Logan Kirkendall <Logan@LKAud.io>
"""

import os
import json
import datetime
import asyncio
import httpx
import uuid
import time
from typing import Dict, Optional, List, Tuple
from fastapi import HTTPException, Request, APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

import state
import helpers
from helpers import extract_and_prepare_files

router = APIRouter()

# Wrapper import for get_discord_target
def get_discord_target(*args, **kwargs):
    """
    Description:
        Wrapper delegating to web_server.get_discord_target.
    Usage:
        target = get_discord_target()
    Usage Example:
        target = get_discord_target()
    """
    import web_server
    return web_server.get_discord_target(*args, **kwargs)

def translate_claude_response_to_openai(claude_res: dict) -> dict:
    """
    Description:
        Translates a non-streaming Anthropic Claude response to OpenAI chat completions format.
    Usage:
        openai_res = translate_claude_response_to_openai(claude_res)
    Usage Example:
        openai_res = translate_claude_response_to_openai({"content": [{"type": "text", "text": "Hi"}]})
    """
    choices = []
    content_list = claude_res.get("content", [])
    text_content = ""
    for item in content_list:
        if item.get("type") == "text":
            text_content += item.get("text", "")
            
    choices.append({
        "index": 0,
        "message": {
            "role": "assistant",
            "content": text_content
        },
        "finish_reason": "stop" if claude_res.get("stop_reason") == "end_turn" else claude_res.get("stop_reason")
    })
    
    return {
        "id": claude_res.get("id", "chatcmpl-unknown"),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": claude_res.get("model", "claude-3-5-sonnet-latest"),
        "choices": choices,
        "usage": {
            "prompt_tokens": claude_res.get("usage", {}).get("input_tokens", 0),
            "completion_tokens": claude_res.get("usage", {}).get("output_tokens", 0),
            "total_tokens": claude_res.get("usage", {}).get("input_tokens", 0) + claude_res.get("usage", {}).get("output_tokens", 0)
        }
    }


def resolve_target_and_payload(raw_request: dict) -> Tuple[str, dict, dict]:
    """
    Description:
        Resolves target URL, payload, and headers based on active state configurations
        (MODEL_PROVIDER, LOCAL_ENDPOINT, LOCAL_MODEL_NAME, etc.).
    Usage:
        target_url, payload, headers = resolve_target_and_payload(raw_request)
    Usage Example:
        url, pay, head = resolve_target_and_payload({"messages": []})
    """
    headers = {"Content-Type": "application/json"}
    
    if state.MODEL_PROVIDER == "ollama":
        base_url = state.AGENT_ENDPOINT.rstrip("/")
        if not base_url.endswith("/chat/completions"):
            target_url = f"{base_url}/chat/completions"
        else:
            target_url = base_url
        payload = dict(raw_request)
        payload["model"] = state.AGENT_MODEL_NAME
        
    elif state.MODEL_PROVIDER == "claude":
        target_url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": state.CLAUDE_API_KEY.strip() if state.CLAUDE_API_KEY else os.getenv("CLAUDE_API_KEY", ""),
            "anthropic-version": "2023-06-01"
        }
        # Translate OpenAI messages to Anthropic messages
        messages = []
        system_prompt = ""
        for m in raw_request.get("messages", []):
            role = m.get("role")
            content = m.get("content")
            if role == "system":
                system_prompt = content
            else:
                messages.append({"role": role, "content": content})
        payload = {
            "model": state.CLAUDE_MODEL_NAME or raw_request.get("model", "claude-3-5-sonnet-latest"),
            "messages": messages,
            "max_tokens": raw_request.get("max_tokens", 4096),
            "stream": raw_request.get("stream", False)
        }
        if system_prompt:
            payload["system"] = system_prompt
            
    elif state.MODEL_PROVIDER == "deepseek":
        target_url = "https://api.deepseek.com/v1/chat/completions"
        api_key = state.DEEPSEEK_API_KEY.strip() if state.DEEPSEEK_API_KEY else os.getenv("DEEPSEEK_API_KEY", "")
        headers["Authorization"] = f"Bearer {api_key}"
        payload = dict(raw_request)
        payload["model"] = state.DEEPSEEK_MODEL_NAME or "deepseek-chat"
        
    elif state.MODEL_PROVIDER == "groq":
        target_url = "https://api.groq.com/openai/v1/chat/completions"
        api_key = state.GROQ_API_KEY.strip() if state.GROQ_API_KEY else os.getenv("GROQ_API_KEY", "")
        headers["Authorization"] = f"Bearer {api_key}"
        payload = dict(raw_request)
        payload["model"] = state.GROQ_MODEL_NAME or "llama3-8b-8192"
        
    elif state.MODEL_PROVIDER == "openrouter":
        target_url = "https://openrouter.ai/api/v1/chat/completions"
        api_key = state.OPENROUTER_API_KEY.strip() if state.OPENROUTER_API_KEY else os.getenv("OPENROUTER_API_KEY", "")
        headers["Authorization"] = f"Bearer {api_key}"
        headers["HTTP-Referer"] = "https://github.com/LKirkend/Discord-Agent"
        headers["X-Title"] = "Discord-Agent"
        payload = dict(raw_request)
        payload["model"] = state.OPENROUTER_MODEL_NAME or "meta-llama/llama-3-8b-instruct:free"
        
    elif state.MODEL_PROVIDER == "together":
        target_url = "https://api.together.xyz/v1/chat/completions"
        api_key = state.TOGETHER_API_KEY.strip() if state.TOGETHER_API_KEY else os.getenv("TOGETHER_API_KEY", "")
        headers["Authorization"] = f"Bearer {api_key}"
        payload = dict(raw_request)
        payload["model"] = state.TOGETHER_MODEL_NAME or "meta-llama/Llama-3-8b-chat-hf"
        
    elif state.MODEL_PROVIDER == "huggingface":
        target_url = "https://api-inference.huggingface.co/v1/chat/completions"
        api_key = state.HF_API_KEY.strip() if state.HF_API_KEY else os.getenv("HF_API_KEY", "")
        headers["Authorization"] = f"Bearer {api_key}"
        payload = dict(raw_request)
        payload["model"] = state.HF_MODEL_NAME or "meta-llama/Meta-Llama-3-8B-Instruct"
        
    elif state.MODEL_PROVIDER == "openai":
        target_url = "https://api.openai.com/v1/chat/completions"
        api_key = state.OPENAI_API_KEY.strip() if state.OPENAI_API_KEY else os.getenv("OPENAI_API_KEY", "")
        headers["Authorization"] = f"Bearer {api_key}"
        payload = dict(raw_request)
        payload["model"] = state.OPENAI_MODEL_NAME or "gpt-4o"
        
    elif state.MODEL_PROVIDER == "custom":
        target_url = state.CUSTOM_ENDPOINT.strip() if state.CUSTOM_ENDPOINT else ""
        if target_url and not target_url.endswith("/chat/completions"):
            target_url = f"{target_url.rstrip('/')}/chat/completions"
        api_key = state.CUSTOM_API_KEY.strip() if state.CUSTOM_API_KEY else os.getenv("CUSTOM_API_KEY", "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = dict(raw_request)
        if state.CUSTOM_MODEL_NAME:
            payload["model"] = state.CUSTOM_MODEL_NAME
            
    else:  # gemini default
        remote_base = state.REMOTE_ENDPOINT.strip() if state.REMOTE_ENDPOINT else "https://generativelanguage.googleapis.com/v1beta/openai"
        remote_base = remote_base.rstrip("/")
        if not remote_base.endswith("/chat/completions"):
            target_url = f"{remote_base}/chat/completions"
        else:
            target_url = remote_base
            
        payload = dict(raw_request)
        req_model = payload.get("model", "")
        if not req_model or (not req_model.startswith("gemini") and not state.REMOTE_ENDPOINT):
            payload["model"] = "gemini-2.5-flash"
            
        api_key = state.REMOTE_API_KEY.strip() if state.REMOTE_API_KEY else os.getenv("REMOTE_API_KEY", "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            if "generativelanguage.googleapis.com" in target_url and "?" not in target_url:
                target_url = f"{target_url}?key={api_key}"
                
    return target_url, payload, headers


async def send_prompt_to_discord(convo_id: str, prompt: str):
    """
    Description:
        Sends the user's proxy prompt to the Discord target.
    Usage:
        await send_prompt_to_discord(convo_id, prompt)
    Usage Example:
        await send_prompt_to_discord("convo-123", "hello")
    """
    target = await get_discord_target()
    if not target:
        print("[API Proxy] No Discord target resolved to send prompt notification.")
        return
    
    seen_paths = set()
    cleaned_prompt, all_files = extract_and_prepare_files(prompt, seen_paths)
    
    convo_short = convo_id[:8] if convo_id else "unknown"
    header = f"💬 **[Proxy Prompt - `{convo_short}`]**\n"
    content = header + cleaned_prompt
    
    try:
        if len(content) > 1900:
            chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]
            if all_files:
                await target.send(content=chunks[0], files=all_files)
            else:
                await target.send(content=chunks[0])
            for chunk in chunks[1:]:
                await target.send(content=chunk)
        else:
            if all_files:
                await target.send(content=content, files=all_files)
            else:
                await target.send(content=content)
    except Exception as e:
        print(f"[API Proxy] Failed to send prompt to Discord: {e}")


async def send_response_to_discord(convo_id: str, response_text: str):
    """
    Description:
        Sends the model's proxy response to the Discord target.
    Usage:
        await send_response_to_discord(convo_id, response_text)
    Usage Example:
        await send_response_to_discord("convo-123", "here is the response")
    """
    if not response_text.strip():
        return
        
    target = await get_discord_target()
    if not target:
        print("[API Proxy] No Discord target resolved to send response notification.")
        return
        
    seen_paths = set()
    cleaned_text, all_files = extract_and_prepare_files(response_text, seen_paths)
    
    convo_short = convo_id[:8] if convo_id else "unknown"
    header = f"🏆 **[Proxy Response - `{convo_short}`]**\n"
    content = header + cleaned_text
    
    try:
        if len(content) > 1900:
            chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]
            if all_files:
                await target.send(content=chunks[0], files=all_files)
            else:
                await target.send(content=chunks[0])
            for chunk in chunks[1:]:
                await target.send(content=chunk)
        else:
            if all_files:
                await target.send(content=content, files=all_files)
            else:
                await target.send(content=content)
    except Exception as e:
        print(f"[API Proxy] Failed to send response to Discord: {e}")


@router.post("/v1/chat/completions")
async def chat_completions(raw_request: dict, request: Request):
    """
    Description:
        OpenAI-compatible chat completions proxy endpoint. Forwards request to local
        or remote LLM endpoints based on configuration and broadcasts prompt/response
        to the user's Discord channel.
    Usage:
        res = await chat_completions(raw_request, request)
    Usage Example:
        res = await chat_completions({"messages": []}, request)
    """
    convo_id = request.headers.get("x-conversation-id") or request.headers.get("x-session-id")
    if not convo_id:
        convo_id = raw_request.get("user")
    if not convo_id:
        convo_id = f"proxy-{uuid.uuid4()}"

    target_url, payload, headers = resolve_target_and_payload(raw_request)
    
    # Extract last user message and post to Discord
    user_msgs = [m for m in payload.get("messages", []) if m.get("role") == "user"]
    if user_msgs:
        last_user_prompt = user_msgs[-1].get("content")
        if last_user_prompt:
            asyncio.create_task(send_prompt_to_discord(convo_id, last_user_prompt))

    is_stream = payload.get("stream", False)
    
    if is_stream:
        async def stream_generator():
            accumulated_content = []
            async with httpx.AsyncClient(timeout=60.0) as client:
                try:
                    async with client.stream("POST", target_url, json=payload, headers=headers) as response:
                        if response.status_code != 200:
                            err_text = await response.aread()
                            yield f"data: {json.dumps({'error': err_text.decode('utf-8', errors='ignore')})}\n\n".encode("utf-8")
                            return
                        
                        buffer = ""
                        if state.MODEL_PROVIDER == "claude":
                            async for chunk in response.aiter_bytes():
                                buffer += chunk.decode("utf-8", errors="ignore")
                                while "\n\n" in buffer:
                                    block, buffer = buffer.split("\n\n", 1)
                                    event_type = None
                                    data_body = None
                                    for line in block.split("\n"):
                                        line = line.strip()
                                        if line.startswith("event:"):
                                            event_type = line[6:].strip()
                                        elif line.startswith("data:"):
                                            data_body = line[5:].strip()
                                    
                                    if data_body and data_body != "[DONE]":
                                        try:
                                            parsed = json.loads(data_body)
                                            if event_type == "content_block_delta":
                                                delta_text = parsed.get("delta", {}).get("text", "")
                                                if delta_text:
                                                    accumulated_content.append(delta_text)
                                                    openai_chunk = {
                                                        "id": "chatcmpl-claude",
                                                        "object": "chat.completion.chunk",
                                                        "created": int(time.time()),
                                                        "model": payload.get("model", "claude-3-5-sonnet-latest"),
                                                        "choices": [{
                                                            "index": 0,
                                                            "delta": {"content": delta_text},
                                                            "finish_reason": None
                                                        }]
                                                    }
                                                    yield f"data: {json.dumps(openai_chunk)}\n\n".encode("utf-8")
                                            elif event_type == "message_delta":
                                                stop_reason = parsed.get("delta", {}).get("stop_reason")
                                                openai_chunk = {
                                                    "id": "chatcmpl-claude",
                                                    "object": "chat.completion.chunk",
                                                    "created": int(time.time()),
                                                    "model": payload.get("model", "claude-3-5-sonnet-latest"),
                                                    "choices": [{
                                                        "index": 0,
                                                        "delta": {},
                                                        "finish_reason": "stop" if stop_reason == "end_turn" else stop_reason
                                                    }]
                                                }
                                                yield f"data: {json.dumps(openai_chunk)}\n\n".encode("utf-8")
                                        except Exception:
                                            pass
                            yield b"data: [DONE]\n\n"
                        else:
                            async for chunk in response.aiter_bytes():
                                yield chunk
                                
                                buffer += chunk.decode("utf-8", errors="ignore")
                                while "\n" in buffer:
                                    line, buffer = buffer.split("\n", 1)
                                    line = line.strip()
                                    if line.startswith("data:"):
                                        data_content = line[5:].strip()
                                        if data_content == "[DONE]":
                                            continue
                                        try:
                                            parsed = json.loads(data_content)
                                            choices = parsed.get("choices", [])
                                            if choices:
                                                delta = choices[0].get("delta", {})
                                                content = delta.get("content")
                                                if content:
                                                    accumulated_content.append(content)
                                        except Exception:
                                            pass
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n".encode("utf-8")
                finally:
                    # After stream concludes, dispatch the full response to Discord
                    final_response_text = "".join(accumulated_content)
                    if final_response_text:
                        asyncio.create_task(send_response_to_discord(convo_id, final_response_text))
                        
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
        
    else:
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(target_url, json=payload, headers=headers)
                if response.status_code == 200:
                    res_data = response.json()
                    
                    if state.MODEL_PROVIDER == "claude":
                        res_data = translate_claude_response_to_openai(res_data)
                        
                    # Try to extract message content to notify Discord
                    choices = res_data.get("choices", [])
                    if choices:
                        message = choices[0].get("message", {})
                        content = message.get("content", "")
                        if content:
                            asyncio.create_task(send_response_to_discord(convo_id, content))
                            
                    return JSONResponse(content=res_data, status_code=200)
                else:
                    try:
                        res_data = response.json()
                    except Exception:
                        res_data = {"error": response.text}
                    return JSONResponse(content=res_data, status_code=response.status_code)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to communicate with LLM provider: {e}")


@router.get("/v1/models")
async def list_models():
    """
    Description:
        OpenAI-compatible models list endpoint.
    Usage:
        res = await list_models()
    Usage Example:
        res = await list_models()
    """
    created_time = int(time.time())
    
    if state.MODEL_PROVIDER == "ollama":
        base_url = state.AGENT_ENDPOINT.rstrip("/")
        if base_url.endswith("/v1"):
            models_url = f"{base_url}/models"
        else:
            models_url = f"{base_url}/v1/models"
            
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(models_url)
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
            
        return {
            "object": "list",
            "data": [
                {
                    "id": state.LOCAL_MODEL_NAME,
                    "object": "model",
                    "created": created_time,
                    "owned_by": "ollama"
                }
            ]
        }
    else:
        model_id = None
        owned_by = None
        
        if state.MODEL_PROVIDER == "claude":
            model_id = state.CLAUDE_MODEL_NAME or "claude-3-5-sonnet-latest"
            owned_by = "anthropic"
        elif state.MODEL_PROVIDER == "deepseek":
            model_id = state.DEEPSEEK_MODEL_NAME or "deepseek-chat"
            owned_by = "deepseek"
        elif state.MODEL_PROVIDER == "groq":
            model_id = state.GROQ_MODEL_NAME or "llama3-8b-8192"
            owned_by = "groq"
        elif state.MODEL_PROVIDER == "openrouter":
            model_id = state.OPENROUTER_MODEL_NAME or "meta-llama/llama-3-8b-instruct:free"
            owned_by = "openrouter"
        elif state.MODEL_PROVIDER == "together":
            model_id = state.TOGETHER_MODEL_NAME or "meta-llama/Llama-3-8b-chat-hf"
            owned_by = "together"
        elif state.MODEL_PROVIDER == "huggingface":
            model_id = state.HF_MODEL_NAME or "meta-llama/Meta-Llama-3-8B-Instruct"
            owned_by = "huggingface"
        elif state.MODEL_PROVIDER == "openai":
            model_id = state.OPENAI_MODEL_NAME or "gpt-4o"
            owned_by = "openai"
        elif state.MODEL_PROVIDER == "custom":
            model_id = state.CUSTOM_MODEL_NAME or "custom-model"
            owned_by = "custom"
            
        if model_id and owned_by:
            return {
                "object": "list",
                "data": [
                    {
                        "id": model_id,
                        "object": "model",
                        "created": created_time,
                        "owned_by": owned_by
                    }
                ]
            }
            
        return {
            "object": "list",
            "data": [
                {
                    "id": "gemini-2.5-flash",
                    "object": "model",
                    "created": created_time,
                    "owned_by": "google"
                },
                {
                    "id": "gemini-2.5-pro",
                    "object": "model",
                    "created": created_time,
                    "owned_by": "google"
                }
            ]
        }
