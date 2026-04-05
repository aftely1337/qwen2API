from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
import asyncio
import json
import logging
import uuid
from backend.services.qwen_client import QwenClient
from backend.services.token_calc import calculate_usage
from backend.services.tool_sieve import ToolSieve
from backend.services.prompt_builder import build_prompt_with_tools

log = logging.getLogger("qwen2api.chat")
router = APIRouter()

@router.post("/completions")
async def chat_completions(request: Request):
    app = request.app
    users_db = app.state.users_db
    client: QwenClient = app.state.qwen_client
    
    # 鉴权
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = auth_header.split(" ")[1]
    
    # 获取下游用户
    users = await users_db.get()
    user = next((u for u in users if u["id"] == token), None)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API Key")
        
    if user.get("quota", 0) <= user.get("used_tokens", 0):
        raise HTTPException(status_code=402, detail="Quota Exceeded")
        
    body = await request.json()
    from backend.core.config import resolve_model
    model = resolve_model(body.get("model", "gpt-3.5-turbo"))
    messages = body.get("messages", [])
    tools = body.get("tools", [])
    
    # 构建带指令劫持的 Prompt
    content = build_prompt_with_tools(messages, tools)
            
    # 无感重试调用
    try:
        events, chat_id, acc = await client.chat_stream_events_with_retry(model, content)
    except Exception as e:
        log.error(f"Chat request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    async def generate():
        full_text = ""
        sieve = ToolSieve()
        try:
            for evt in events:
                if evt.get("type") == "delta":
                    text = evt.get("content", "")
                    safe_text, tool_calls = sieve.process_delta(text)
                    full_text += safe_text
                    
                    if safe_text:
                        chunk = {
                            "id": "chatcmpl-123",
                            "object": "chat.completion.chunk",
                            "model": model,
                            "choices": [{"index": 0, "delta": {"content": safe_text}, "finish_reason": None}]
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"
                    
                    for tc in tool_calls:
                        # 转换 tool call 格式为 OpenAI 兼容
                        tc_chunk = {
                            "id": "chatcmpl-123",
                            "object": "chat.completion.chunk",
                            "model": model,
                            "choices": [{"index": 0, "delta": {
                                "tool_calls": [{
                                    "id": f"call_{uuid.uuid4().hex[:8]}",
                                    "type": "function",
                                    "function": {
                                        "name": tc.get("name", ""),
                                        "arguments": json.dumps(tc.get("input", {}))
                                    }
                                }]
                            }, "finish_reason": "tool_calls"}]
                        }
                        yield f"data: {json.dumps(tc_chunk)}\n\n"
                    
            # 扣费统计
            usage = calculate_usage(content, full_text)
            chunk = {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": usage
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"
            
            # 更新数据库 (异步锁保护)
            users = await users_db.get()
            for u in users:
                if u["id"] == token:
                    u["used_tokens"] += usage["total_tokens"]
                    break
            await users_db.save(users)
            
        finally:
            client.account_pool.release(acc)
            asyncio.create_task(client.delete_chat(acc.token, chat_id))
            
    return StreamingResponse(generate(), media_type="text/event-stream")
