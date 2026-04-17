"""
图片生成接口 — 兼容 OpenAI /v1/images/generations 规范。

底层通过现有直连 HTTP 聊天能力触发千问“生成图像”模式，
不依赖浏览器运行时。
"""
import re
import time
import json
import asyncio
import logging
from math import gcd
from fastapi import APIRouter, Request, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse
from backend.services.qwen_client import QwenClient

log = logging.getLogger("qwen2api.images")
router = APIRouter()

DEFAULT_IMAGE_MODEL = "qwen3.6-plus"

IMAGE_MODEL_MAP = {
    "dall-e-3": "qwen3.6-plus",
    "dall-e-2": "qwen3.6-plus",
    "qwen-image": "qwen3.6-plus",
    "qwen-image-plus": "qwen3.6-plus",
    "qwen-image-turbo": "qwen3.6-plus",
    "qwen3.6-plus": "qwen3.6-plus",
}


def _extract_image_urls(text: str) -> list[str]:
    urls: list[str] = []

    for u in re.findall(r'!\[.*?\]\((https?://[^\s\)]+)\)', text):
        urls.append(u.rstrip(").,;"))

    for u in re.findall(r'"(?:url|image|src|imageUrl|image_url)"\s*:\s*"(https?://[^"]+)"', text):
        urls.append(u)

    cdn_pattern = r'https?://(?:cdn\.qwenlm\.ai|wanx\.alicdn\.com|img\.alicdn\.com|[^\s"<>]+\.(?:jpg|jpeg|png|webp|gif))(?:[^\s"<>]*)'
    for u in re.findall(cdn_pattern, text, re.IGNORECASE):
        urls.append(u.rstrip(".,;)\"'>"))

    seen: set[str] = set()
    result: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            result.append(u)
    return result


def _resolve_image_model(requested: str | None) -> str:
    if not requested:
        return DEFAULT_IMAGE_MODEL
    return IMAGE_MODEL_MAP.get(requested, DEFAULT_IMAGE_MODEL)


def _get_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return request.headers.get("x-api-key", "").strip()


def _normalize_qwen_image_size(size: str | None) -> str:
    raw = (size or "").strip().lower()
    if not raw:
        return "1:1"
    if re.fullmatch(r"\d+:\d+", raw):
        return raw

    match = re.fullmatch(r"(\d+)\s*x\s*(\d+)", raw)
    if not match:
        return "1:1"

    width = int(match.group(1))
    height = int(match.group(2))
    if width <= 0 or height <= 0:
        return "1:1"
    divisor = gcd(width, height) or 1
    return f"{width // divisor}:{height // divisor}"


@router.post("/v1/images/generations")
@router.post("/images/generations")
async def create_image(request: Request):
    from backend.core.config import API_KEYS, settings

    client: QwenClient = request.app.state.qwen_client

    token = _get_token(request)
    if API_KEYS:
        if token != settings.ADMIN_KEY and token not in API_KEYS:
            raise HTTPException(status_code=401, detail="Invalid API Key")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")

    prompt: str = body.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(400, "prompt is required")

    n: int = min(max(int(body.get("n", 1)), 1), 4)
    qwen_size = _normalize_qwen_image_size(body.get("size"))
    model = _resolve_image_model(body.get("model"))

    log.info(f"[T2I] model={model}, n={n}, prompt={prompt[:80]!r}")

    acc = None
    chat_id = None
    try:
        prompt_text = prompt.strip()
        event_payloads: list[str] = []
        async for item in client.chat_stream_events_with_retry(
            model,
            prompt_text,
            has_custom_tools=False,
            chat_type="t2i",
            size=qwen_size,
        ):
            if item.get("type") == "meta":
                acc = item.get("acc")
                chat_id = item.get("chat_id")
                continue
            if item.get("type") != "event":
                continue
            event_payloads.append(json.dumps(item.get("event", {}), ensure_ascii=False))

        if acc is None or chat_id is None:
            raise HTTPException(status_code=500, detail="Image generation session was not created")

        chats = await client.list_chats(acc.token, limit=20)
        current_chat = next((c for c in chats if isinstance(c, dict) and c.get("id") == chat_id), None)
        answer_text = "\n".join(event_payloads)
        if current_chat:
            answer_text += "\n" + json.dumps(current_chat, ensure_ascii=False)
            
        lower_text = answer_text.lower()
        if "allocated quota exceeded" in lower_text or "quota exceeded" in lower_text or "token-limit" in lower_text:
            raise Exception("Image Generation Quota Exceeded")
            
        image_urls = _extract_image_urls(answer_text)
        log.info(f"[T2I] 提取到 {len(image_urls)} 张图片 URL: {image_urls}")

        if not image_urls:
            raise HTTPException(status_code=500, detail="Image generation succeeded but no URL found")

        data = [{"url": url, "revised_prompt": prompt} for url in image_urls[:n]]
        return JSONResponse({"created": int(time.time()), "data": data})

    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e).lower()
        if "quota exceeded" in err_msg or "allocated quota exceeded" in err_msg or "token-limit" in err_msg:
            if acc:
                client.account_pool.mark_rate_limited(acc, error_message="Image Generation Quota Exceeded")
        log.error(f"[T2I] 生成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if acc is not None:
            client.account_pool.release(acc)
            if chat_id:
                asyncio.create_task(client.delete_chat(acc.token, chat_id))


@router.post("/v1/images/edits")
@router.post("/images/edits")
async def edit_image(
    request: Request,
    image: UploadFile = File(...),
    mask: UploadFile | None = File(None),
    prompt: str = Form(...),
    n: int = Form(1),
    size: str = Form("1024x1024"),
    model: str = Form("dall-e-3")
):
    from backend.core.config import API_KEYS, settings
    client: QwenClient = request.app.state.qwen_client
    uploader = request.app.state.upstream_file_uploader

    token = _get_token(request)
    if API_KEYS:
        if token != settings.ADMIN_KEY and token not in API_KEYS:
            raise HTTPException(status_code=401, detail="Invalid API Key")

    n_limit = min(max(n, 1), 4)
    model_resolved = _resolve_image_model(model)
    qwen_size = _normalize_qwen_image_size(size)
    log.info(f"[T2I-Edit] model={model_resolved}, n={n_limit}, prompt={prompt[:80]!r}")

    image_bytes = await image.read()
    filename = image.filename or "image.png"
    content_type = image.content_type or "image/png"

    # Save to file_store to get local_meta for uploader
    file_store = request.app.state.file_store
    local_meta = await file_store.save_bytes(filename, content_type, image_bytes, "vision")

    last_error = None
    for attempt in range(settings.MAX_RETRIES):
        acc = await client.account_pool.acquire_wait(timeout=30)
        if not acc:
            raise HTTPException(status_code=503, detail="No available accounts for uploading.")

        try:
            # Upload file
            remote_info = await uploader.upload_local_file(acc, local_meta)
            remote_ref = remote_info["remote_ref"]

            prompt_text = prompt.strip()
            event_payloads: list[str] = []
            chat_id = None

            async for item in client.chat_stream_events_with_retry(
                model_resolved,
                prompt_text,
                has_custom_tools=False,
                files=[remote_ref],
                fixed_account=acc,
                chat_type="t2i",
                size=qwen_size,
            ):
                if item.get("type") == "meta":
                    chat_id = item.get("chat_id")
                    continue
                if item.get("type") != "event":
                    continue
                event_payloads.append(json.dumps(item.get("event", {}), ensure_ascii=False))

            if not chat_id:
                raise HTTPException(status_code=500, detail="Image generation session was not created")

            chats = await client.list_chats(acc.token, limit=20)
            current_chat = next((c for c in chats if isinstance(c, dict) and c.get("id") == chat_id), None)
            answer_text = "\n".join(event_payloads)
            if current_chat:
                answer_text += "\n" + json.dumps(current_chat, ensure_ascii=False)

            lower_text = answer_text.lower()
            if "allocated quota exceeded" in lower_text or "quota exceeded" in lower_text or "token-limit" in lower_text:
                raise Exception("Image Edit Quota Exceeded")

            image_urls = _extract_image_urls(answer_text)
            log.info(f"[T2I-Edit] 提取到 {len(image_urls)} 张图片 URL: {image_urls}")

            if not image_urls:
                log.error(f"[T2I-Edit] Answer text: {answer_text}")
                raise HTTPException(status_code=500, detail="Image edit succeeded but no URL found")

            data = [{"url": url, "revised_prompt": prompt} for url in image_urls[:n_limit]]
            
            # Clean up
            asyncio.create_task(client.delete_chat(acc.token, chat_id))
            
            return JSONResponse({"created": int(time.time()), "data": data})

        except HTTPException:
            raise
        except Exception as e:
            err_msg = str(e).lower()
            if "quota exceeded" in err_msg or "allocated quota exceeded" in err_msg or "token-limit" in err_msg:
                log.warning(f"[T2I-Edit] 账号 {acc.email} 图像编辑配额不足，标记限流并换号重试")
                client.account_pool.mark_rate_limited(acc, error_message="Image Edit Quota Exceeded")
            else:
                log.warning(f"[T2I-Edit] 尝试 {attempt+1}/{settings.MAX_RETRIES} 失败: {e}")
            last_error = e
        finally:
            client.account_pool.release(acc)

    log.error(f"[T2I-Edit] 所有 {settings.MAX_RETRIES} 次尝试均失败。最后错误: {last_error}")
    raise HTTPException(status_code=500, detail=str(last_error))
