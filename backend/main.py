import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

# Windows UTF-8 输出修复
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 将项目根目录加入到 sys.path，解决直接运行 main.py 时找不到 backend 模块的问题
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.config import settings
from backend.core.database import AsyncJsonDB
from backend.core.browser_engine import BrowserEngine
from backend.core.httpx_engine import HttpxEngine
from backend.core.hybrid_engine import HybridEngine
from backend.core.account_pool import AccountPool
from backend.services.qwen_client import QwenClient
from backend.services.account_health import count_healthy_accounts
from backend.services.auto_registrar import QwenAutoRegistrar
from backend.api import admin, v1_chat, probes, anthropic, gemini, embeddings, images
from backend.services.garbage_collector import garbage_collect_chats

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("qwen2api")


async def sleep_or_wake(delay_seconds: float, wake_event: asyncio.Event | None = None):
    if delay_seconds <= 0:
        return
    if wake_event is None:
        await asyncio.sleep(delay_seconds)
        return
    try:
        await asyncio.wait_for(wake_event.wait(), timeout=delay_seconds)
    except asyncio.TimeoutError:
        pass
    finally:
        wake_event.clear()


async def background_auto_refill_task(pool, wake_event: asyncio.Event | None = None):
    registrar = QwenAutoRegistrar()
    
    while True:
        try:
            target_min_accounts = max(0, int(getattr(settings, "AUTO_REFILL_TARGET_MIN_ACCOUNTS", 3) or 0))
            if target_min_accounts <= 0:
                await sleep_or_wake(300, wake_event)
                continue

            # Count healthy accounts (status=200, not rate limited)
            healthy_count = count_healthy_accounts(pool.accounts)
            
            if healthy_count < target_min_accounts:
                log.info(f"[Daemon] Healthy accounts ({healthy_count}) < target ({target_min_accounts}). Starting auto-refill...")
                try:
                    new_acc = await registrar.register_account()
                    await pool.add(new_acc)
                    log.info(f"[Daemon] Auto-refill successful. Added {new_acc.email}.")
                    # Wait a bit before registering another one to avoid suspicion
                    await sleep_or_wake(10, wake_event)
                except Exception as e:
                    log.error(f"[Daemon] Auto-refill failed: {e}. Backing off for 5 minutes.")
                    await sleep_or_wake(300, wake_event) # 5 minutes backoff on failure
            else:
                # Pool is healthy, check again in 5 minutes
                await sleep_or_wake(300, wake_event)
                
        except asyncio.CancelledError:
            log.info("[Daemon] Auto-refill task cancelled.")
            break
        except Exception as e:
            log.error(f"[Daemon] Unexpected error in auto-refill task: {e}")
            await sleep_or_wake(60, wake_event)

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting qwen2API v2.0 Enterprise Gateway...")

    app.state.accounts_db = AsyncJsonDB(settings.ACCOUNTS_FILE, default_data=[])
    app.state.users_db = AsyncJsonDB(settings.USERS_FILE, default_data=[])
    app.state.captures_db = AsyncJsonDB(settings.CAPTURES_FILE, default_data=[])

    browser_engine = BrowserEngine(pool_size=settings.BROWSER_POOL_SIZE)
    httpx_engine = HttpxEngine(base_url="https://chat.qwen.ai")

    if settings.ENGINE_MODE == "httpx":
        engine = httpx_engine
        log.info("引擎模式: httpx 直连")
    elif settings.ENGINE_MODE == "hybrid":
        engine = HybridEngine(browser_engine, httpx_engine)
        log.info("引擎模式: Hybrid (api_call=httpx优先, fetch_chat=browser)")
    else:
        engine = browser_engine
        log.info("引擎模式: Camoufox 浏览器")

    app.state.browser_engine = browser_engine
    app.state.httpx_engine = httpx_engine
    app.state.gateway_engine = engine
    app.state.account_pool = AccountPool(app.state.accounts_db, max_inflight=settings.MAX_INFLIGHT_PER_ACCOUNT)
    app.state.qwen_client = QwenClient(engine, app.state.account_pool)

    await app.state.account_pool.load()
    await engine.start()

    asyncio.create_task(garbage_collect_chats(app.state.qwen_client))
    
    # Start daemon
    app.state.auto_refill_wakeup = asyncio.Event()
    refill_task = asyncio.create_task(background_auto_refill_task(app.state.account_pool, app.state.auto_refill_wakeup))

    yield

    log.info("Shutting down gateway...")
    refill_task.cancel()
    await app.state.gateway_engine.stop()

app = FastAPI(title="qwen2API Enterprise Gateway", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
app.include_router(v1_chat.router, tags=["OpenAI Compatible"])
app.include_router(images.router, tags=["Image Generation"])
app.include_router(anthropic.router, tags=["Claude Compatible"])
app.include_router(gemini.router, tags=["Gemini Compatible"])
app.include_router(embeddings.router, tags=["Embeddings"])
app.include_router(probes.router, tags=["Probes"])
app.include_router(admin.router, prefix="/api/admin", tags=["Dashboard Admin"])

@app.get("/api", tags=["System"])
async def root():
    return {
        "status": "qwen2API Enterprise Gateway is running",
        "docs": "/docs",
        "version": "2.0.0"
    }

# 托管前端构建产物（仅当 dist 存在时，即生产打包模式）
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=settings.PORT, workers=1)
