"""
图片生成接口 — 兼容 OpenAI /v1/images/generations 规范。

底层通过千问网页当前真实的“生成图像”模式触发，而不是写死 wanx 模型名。
页面实测结果显示：UI 仍显示 `Qwen3.6-Plus`，并通过“生成图像”模式完成图片生成。
"""
import re
import time
import asyncio
import logging
from fastapi import APIRouter, Request, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse
from backend.services.qwen_client import QwenClient

log = logging.getLogger("qwen2api.images")
router = APIRouter()

# 默认图片生成模型：网页实测仍显示为 Qwen3.6-Plus
DEFAULT_IMAGE_MODEL = "qwen3.6-plus"

# 受支持的图片模型别名 -> 网页真实可用的基础模型
IMAGE_MODEL_MAP = {
    "dall-e-3": "qwen3.6-plus",
    "dall-e-2": "qwen3.6-plus",
    "qwen-image": "qwen3.6-plus",
    "qwen-image-plus": "qwen3.6-plus",
    "qwen-image-turbo": "qwen3.6-plus",
    "qwen3.6-plus": "qwen3.6-plus",
}


def _extract_image_urls(text: str) -> list[str]:
    """从模型输出中提取图片 URL（支持 Markdown、JSON 字段、裸 URL 三种格式）"""
    urls: list[str] = []

    # 1. Markdown 图片语法: ![...](url)
    for u in re.findall(r'!\[.*?\]\((https?://[^\s\)]+)\)', text):
        urls.append(u.rstrip(").,;"))

    # 2. JSON 字段: "url":"...", "image":"...", "src":"..."
    if not urls:
        for u in re.findall(r'"(?:url|image|src|imageUrl|image_url)"\s*:\s*"(https?://[^"]+)"', text):
            urls.append(u)

    # 3. 裸 URL（以常见图片扩展名结尾，或来自已知 CDN）
    if not urls:
        cdn_pattern = r'https?://(?:cdn\.qwenlm\.ai|wanx\.alicdn\.com|img\.alicdn\.com|[^\s"<>]+\.(?:jpg|jpeg|png|webp|gif))[^\s"<>]*'
        for u in re.findall(cdn_pattern, text, re.IGNORECASE):
            urls.append(u.rstrip(".,;)\"'>"))

    # 去重并保留顺序
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


@router.post("/v1/images/generations")
@router.post("/images/generations")
async def create_image(request: Request):
    """
    OpenAI 兼容的图片生成接口。

    请求体示例:
    ```json
    {
      "prompt": "一只赛博朋克风格的猫",
      "model": "dall-e-3",
      "n": 1,
      "size": "1024x1024",
      "response_format": "url"
    }
    ```
    """
    from backend.core.config import API_KEYS, settings
    client: QwenClient = request.app.state.qwen_client

    # 鉴权
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

    n: int = min(max(int(body.get("n", 1)), 1), 4)  # 最多 4 张
    model = _resolve_image_model(body.get("model"))

    log.info(f"[T2I] model={model}, n={n}, prompt={prompt[:80]!r}")

    try:
        answer_text, acc, chat_id = await client.image_generate_with_retry(model, prompt)

        # 后台清理会话
        client.account_pool.release(acc)
        asyncio.create_task(client.delete_chat(acc.token, chat_id))

        # 提取图片 URL
        image_urls = _extract_image_urls(answer_text)
        log.info(f"[T2I] 提取到 {len(image_urls)} 张图片 URL: {image_urls}")

        if not image_urls:
            log.warning(f"[T2I] 未能提取图片 URL，原始响应: {answer_text[:300]!r}")
            raise HTTPException(
                status_code=500,
                detail=f"Image generation succeeded but no URL found. Raw response: {answer_text[:200]}"
            )

        data = [{"url": url, "revised_prompt": prompt} for url in image_urls[:n]]
        return JSONResponse({"created": int(time.time()), "data": data})

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[T2I] 生成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/v1/images/edits")
@router.post("/images/edits")
async def edit_image(
    request: Request,
    image: UploadFile = File(...),
    mask: UploadFile = File(None),
    prompt: str = Form(...),
    n: int = Form(1),
    size: str = Form("1024x1024"),
    model: str = Form("dall-e-3")
):
    """
    OpenAI 兼容的图片编辑（图生图/局部重绘）接口。
    上传图片至千问后端获取 file_id，并将图生图任务下发。
    """
    from backend.core.config import API_KEYS, settings
    client: QwenClient = request.app.state.qwen_client

    # 鉴权
    token = _get_token(request)
    if API_KEYS:
        if token != settings.ADMIN_KEY and token not in API_KEYS:
            raise HTTPException(status_code=401, detail="Invalid API Key")

    n_limit = min(max(n, 1), 4)
    model_resolved = _resolve_image_model(model)

    log.info(f"[T2I-Edit] Real mode: model={model_resolved}, n={n_limit}, prompt={prompt[:80]!r}")
    
    # 1. 拿出一个可用账号，以便进行上传
    acc = await client.account_pool.acquire_wait(timeout=10)
    if not acc:
        raise HTTPException(status_code=503, detail="No available accounts for uploading.")
        
    try:
        # 2. 上传原图到千问的 /api/v1/files/
        image_bytes = await image.read()
        filename = image.filename or "image.png"
        content_type = image.content_type or "image/png"
        
        uploaded_file_info = await client.upload_file(acc.token, image_bytes, filename, content_type)
        
        # TODO: 暂时忽略 mask 遮罩文件，千问可能不需要分离的遮罩，或者需要另外拼图。这里只上传主图。
        
        # 3. 携带上传文件发起图生图生成
        answer_text, used_acc, chat_id = await client.image_generate_with_retry(
            model_resolved, 
            prompt,
            uploaded_files=[uploaded_file_info]
        )

        # 后台清理会话
        client.account_pool.release(used_acc)
        asyncio.create_task(client.delete_chat(used_acc.token, chat_id))

        # 提取图片 URL
        image_urls = _extract_image_urls(answer_text)
        log.info(f"[T2I-Edit] 提取到 {len(image_urls)} 张图片 URL: {image_urls}")

        if not image_urls:
            log.warning(f"[T2I-Edit] 未能提取图片 URL，原始响应: {answer_text[:300]!r}")
            raise HTTPException(
                status_code=500,
                detail=f"Image edit generation succeeded but no URL found. Raw response: {answer_text[:200]}"
            )

        data = [{"url": url, "revised_prompt": prompt} for url in image_urls[:n_limit]]
        return JSONResponse({"created": int(time.time()), "data": data})

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[T2I-Edit] 生成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        client.account_pool.release(acc)
