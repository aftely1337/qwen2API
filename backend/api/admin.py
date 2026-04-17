import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from backend.core.config import settings, save_runtime_config
from backend.core.database import AsyncJsonDB
from backend.core.account_pool import AccountPool, Account
from backend.services.auto_registrar import QwenAutoRegistrar

router = APIRouter()


def wake_auto_refill_task(request: Request):
    wake_event = getattr(request.app.state, "auto_refill_wakeup", None)
    if wake_event is not None:
        wake_event.set()

class GenerateAccountsRequest(BaseModel):
    count: int = 1

def verify_admin(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split("Bearer ", 1)[1]

    from backend.core.config import API_KEYS, settings as backend_settings
    if token != backend_settings.ADMIN_KEY and token not in API_KEYS:
        raise HTTPException(status_code=403, detail="Forbidden: Admin Key Mismatch")
    return token


class UserCreate(BaseModel):
    name: str
    quota: int = 1000000


def build_account_export_payload(accounts: list[Account]) -> dict:
    return {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "count": len(accounts),
        "accounts": [account.to_dict() for account in accounts],
    }


def _coerce_float(value, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def _coerce_int(value, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _build_import_account(raw: dict) -> Account:
    if not isinstance(raw, dict):
        raise ValueError("Each imported account must be an object")

    email = str(raw.get("email", "") or "").strip()
    token = str(raw.get("token", "") or "").strip()

    if not email:
        raise ValueError("Each imported account must include email")
    if not token:
        raise ValueError(f"Imported account {email} is missing token")

    return Account(
        email=email,
        password=str(raw.get("password", "") or ""),
        token=token,
        cookies=str(raw.get("cookies", "") or ""),
        username=str(raw.get("username", "") or ""),
        activation_pending=bool(raw.get("activation_pending", False)),
        status_code=str(raw.get("status_code", "") or ""),
        last_error=str(raw.get("last_error", "") or ""),
        valid=bool(raw.get("valid", raw.get("is_valid", True))),
        rate_limited_until=_coerce_float(raw.get("rate_limited_until", 0.0)),
        last_request_started=_coerce_float(raw.get("last_request_started", 0.0)),
        last_request_finished=_coerce_float(raw.get("last_request_finished", 0.0)),
        consecutive_failures=_coerce_int(raw.get("consecutive_failures", 0)),
        rate_limit_strikes=_coerce_int(raw.get("rate_limit_strikes", 0)),
    )


def parse_account_import_payload(payload) -> list[Account]:
    if isinstance(payload, dict):
        rows = payload.get("accounts")
    elif isinstance(payload, list):
        rows = payload
    else:
        raise ValueError("Import payload must be a JSON array or an object with an accounts field")

    if not isinstance(rows, list):
        raise ValueError("Import payload must contain an accounts array")

    deduped: dict[str, Account] = {}
    for raw in rows:
        account = _build_import_account(raw)
        deduped[account.email] = account
    return list(deduped.values())


@router.get("/status", dependencies=[Depends(verify_admin)])
async def get_system_status(request: Request):
    pool = request.app.state.account_pool
    engine = getattr(request.app.state, "gateway_engine", request.app.state.browser_engine)
    browser_engine = getattr(request.app.state, "browser_engine", None)
    httpx_engine = getattr(request.app.state, "httpx_engine", None)

    if hasattr(engine, "status"):
        engine_info = engine.status()
    elif hasattr(engine, "_pages") and hasattr(engine, "pool_size"):
        free_pages = engine._pages.qsize()
        in_use = engine.pool_size - free_pages
        engine_info = {
            "started": engine._started,
            "mode": "browser",
            "pool_size": engine.pool_size,
            "free_pages": free_pages,
            "queue": in_use if in_use > 0 else 0,
        }
    else:
        engine_info = {
            "started": getattr(engine, "_started", False),
            "mode": "httpx",
            "pool_size": 0,
            "free_pages": 0,
            "queue": 0,
        }

    browser_info = {
        "started": getattr(browser_engine, "_started", False),
        "pool_size": getattr(browser_engine, "pool_size", 0),
        "free_pages": browser_engine._pages.qsize() if getattr(browser_engine, "_pages", None) is not None else 0,
        "queue": max(0, getattr(browser_engine, "pool_size", 0) - (browser_engine._pages.qsize() if getattr(browser_engine, "_pages", None) is not None else 0)),
    } if browser_engine else {"started": False, "pool_size": 0, "free_pages": 0, "queue": 0}

    httpx_info = {
        "started": getattr(httpx_engine, "_started", False),
        "mode": "httpx",
    } if httpx_engine else {"started": False, "mode": "httpx"}

    return {
        "accounts": pool.status(),
        "engine_mode": settings.ENGINE_MODE,
        "browser_engine": browser_info,
        "httpx_engine": httpx_info,
        "hybrid_engine": engine_info if settings.ENGINE_MODE == "hybrid" else None,
    }


@router.get("/users", dependencies=[Depends(verify_admin)])
async def list_users(request: Request):
    db: AsyncJsonDB = request.app.state.users_db
    return {"users": await db.get()}


@router.post("/users", dependencies=[Depends(verify_admin)])
async def create_user(user: UserCreate, request: Request):
    import uuid
    db: AsyncJsonDB = request.app.state.users_db
    data = await db.get()
    new_user = {
        "id": f"sk-{uuid.uuid4().hex}",
        "name": user.name,
        "quota": user.quota,
        "used_tokens": 0,
    }
    data.append(new_user)
    await db.save(data)
    return new_user


@router.post("/accounts", dependencies=[Depends(verify_admin)])
async def add_account(request: Request):
    import time
    from backend.services.qwen_client import QwenClient

    pool: AccountPool = request.app.state.account_pool
    client: QwenClient = request.app.state.qwen_client

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON body")

    token = data.get("token", "")
    if not token:
        raise HTTPException(400, detail="token is required")

    acc = Account(
        email=data.get("email", f"manual_{int(time.time())}@qwen"),
        password=data.get("password", ""),
        token=token,
        cookies=data.get("cookies", ""),
        username=data.get("username", ""),
    )

    is_valid = await client.verify_token(token)
    if not is_valid:
        acc.valid = False
        acc.status_code = "auth_error"
        acc.last_error = "Token ??????"
        return {"ok": False, "error": acc.last_error, "message": acc.last_error}

    acc.valid = True
    acc.activation_pending = False
    acc.status_code = "valid"
    acc.last_error = ""
    await pool.add(acc)
    return {"ok": True, "email": acc.email, "message": "????????"}


@router.post("/reload", dependencies=[Depends(verify_admin)])
async def reload_accounts(request: Request):
    """从磁盘重新加载账号数据"""
    pool: AccountPool = request.app.state.account_pool
    await pool.load()
    for acc in pool.accounts:
        acc.valid = True
        acc.activation_pending = False
        acc.status_code = "valid"
        acc.last_error = ""
        acc.consecutive_failures = 0
        acc.rate_limit_strikes = 0
        acc.rate_limited_until = 0.0
    await pool.save()
    return {"ok": True, "count": len(pool.accounts)}

@router.get("/accounts", dependencies=[Depends(verify_admin)])
async def list_accounts(request: Request):
    pool: AccountPool = request.app.state.account_pool
    accounts = []
    for a in pool.accounts:
        item = a.to_dict()
        item["valid"] = a.valid
        item["inflight"] = a.inflight
        item["rate_limited_until"] = a.rate_limited_until
        item["status_code"] = a.get_status_code()
        item["status_text"] = a.get_status_text()
        item["last_error"] = a.last_error
        accounts.append(item)
    return {"accounts": accounts}


@router.get("/accounts/export", dependencies=[Depends(verify_admin)])
async def export_accounts(request: Request):
    pool: AccountPool = request.app.state.account_pool
    payload = build_account_export_payload(pool.accounts)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="accounts-export-{timestamp}.json"'},
    )


@router.post("/accounts/import", dependencies=[Depends(verify_admin)])
async def import_accounts(request: Request):
    pool: AccountPool = request.app.state.account_pool

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    try:
        imported_accounts = parse_account_import_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not imported_accounts:
        raise HTTPException(status_code=400, detail="No accounts found in import payload")

    async with pool._lock:
        existing_by_email = {account.email: account for account in pool.accounts}
        replaced = sum(1 for account in imported_accounts if account.email in existing_by_email)
        for account in imported_accounts:
            existing_by_email[account.email] = account
        pool.accounts = list(existing_by_email.values())

    await pool.save()
    wake_auto_refill_task(request)
    return {
        "ok": True,
        "imported": len(imported_accounts),
        "replaced": replaced,
        "total": len(pool.accounts),
    }


@router.post("/accounts/generate", dependencies=[Depends(verify_admin)])
async def generate_accounts(req: GenerateAccountsRequest, request: Request):
    """Generate N new accounts automatically via TempMail and Qwen Registration."""
    count = max(1, min(req.count, 10)) # Limit to 10 at a time
    registrar = QwenAutoRegistrar()
    pool: AccountPool = request.app.state.account_pool
    
    results = []
    errors = []
    
    # Process sequentially to avoid aggressive IP bans from Qwen
    for i in range(count):
        try:
            new_acc = await registrar.register_account()
            await pool.add(new_acc)
            results.append(new_acc.email)
        except Exception as e:
            import traceback
            traceback.print_exc()
            errors.append(str(e))
            
    return {
        "success_count": len(results),
        "error_count": len(errors),
        "emails": results,
        "errors": errors
    }


@router.post("/verify", dependencies=[Depends(verify_admin)])
async def verify_all_accounts(request: Request):
    """?????????"""
    import asyncio
    import logging
    from backend.services.qwen_client import QwenClient
    from backend.core.config import settings as backend_settings

    log = logging.getLogger("qwen2api.admin")
    pool: AccountPool = request.app.state.account_pool
    client: QwenClient = request.app.state.qwen_client

    concurrency = max(1, min(len(pool.accounts) or 1, max(2, backend_settings.BROWSER_POOL_SIZE)))
    sem = asyncio.Semaphore(concurrency)

    async def verify_one(acc: Account):
        async with sem:
            is_valid = await client.verify_token(acc.token)
            refreshed = False
            if not is_valid and acc.password:
                log.info(f"[??] {acc.email} Token ?????????...")
                refreshed = await client.auth_resolver.refresh_token(acc)
                is_valid = refreshed or is_valid

            acc.valid = is_valid
            if is_valid:
                acc.activation_pending = False
                acc.status_code = "valid"
                acc.last_error = ""
            elif acc.activation_pending:
                acc.status_code = "pending_activation"
            elif acc.get_status_code() != "rate_limited":
                acc.status_code = acc.status_code or "auth_error"
                if not acc.last_error:
                    acc.last_error = "???????????"

            return {
                "email": acc.email,
                "valid": is_valid,
                "refreshed": refreshed,
                "status_code": acc.get_status_code(),
                "status_text": acc.get_status_text(),
                "error": acc.last_error,
            }

    results = await asyncio.gather(*(verify_one(acc) for acc in pool.accounts))
    await pool.save()
    return {"ok": True, "results": results, "concurrency": concurrency}


@router.post("/accounts/{email}/activate", dependencies=[Depends(verify_admin)])
async def activate_account(email: str, request: Request):
    """?????????"""
    from backend.services.auth_resolver import activate_account as activate_logic

    pool: AccountPool = request.app.state.account_pool
    acc = next((a for a in pool.accounts if a.email == email), None)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")

    started_at = float(getattr(acc, "_activation_started_at", 0) or 0)
    if getattr(acc, "_is_activating", False):
        if started_at and (time.time() - started_at) < 90:
            return {"ok": True, "pending": True, "message": "账号正在激活中，请稍后刷新"}
        setattr(acc, "_is_activating", False)
        setattr(acc, "_activation_started_at", 0)

    try:
        setattr(acc, "_is_activating", True)
        success = await activate_logic(acc)
        if success:
            acc.valid = True
            acc.activation_pending = False
            acc.status_code = "valid"
            acc.last_error = ""
            await pool.add(acc)
            return {"ok": True, "message": "??????"}

        if acc.activation_pending:
            acc.status_code = "pending_activation"
        elif acc.status_code not in ("banned", "rate_limited"):
            acc.status_code = acc.status_code or "auth_error"
        if not acc.last_error:
            acc.last_error = "????????????"
        await pool.save()
        return {"ok": False, "error": acc.last_error, "message": acc.last_error}
    finally:
        setattr(acc, "_is_activating", False)


@router.post("/accounts/{email}/verify", dependencies=[Depends(verify_admin)])
async def verify_account(email: str, request: Request):
    """?????????"""
    import logging
    from backend.services.qwen_client import QwenClient

    log = logging.getLogger("qwen2api.admin")
    pool: AccountPool = request.app.state.account_pool
    client: QwenClient = request.app.state.qwen_client

    acc = next((a for a in pool.accounts if a.email == email), None)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")

    is_valid = await client.verify_token(acc.token)
    refreshed = False
    if not is_valid and acc.password:
        log.info(f"[??] {acc.email} Token ?????????...")
        refreshed = await client.auth_resolver.refresh_token(acc)
        is_valid = refreshed or is_valid

    acc.valid = is_valid
    if is_valid:
        acc.activation_pending = False
        acc.status_code = "valid"
        acc.last_error = ""
    elif acc.activation_pending:
        acc.status_code = "pending_activation"
        if not acc.last_error:
            acc.last_error = "??????"
    elif acc.get_status_code() != "rate_limited":
        acc.status_code = acc.status_code or "auth_error"
        if not acc.last_error:
            acc.last_error = "???????????"

    await pool.save()
    return {
        "email": acc.email,
        "valid": is_valid,
        "refreshed": refreshed,
        "status_code": acc.get_status_code(),
        "status_text": acc.get_status_text(),
        "error": acc.last_error,
    }


@router.delete("/accounts/{email}", dependencies=[Depends(verify_admin)])
async def delete_account(email: str, request: Request):
    pool: AccountPool = request.app.state.account_pool
    await pool.remove(email)
    return {"ok": True}


@router.get("/settings", dependencies=[Depends(verify_admin)])
async def get_settings():
    from backend.core.config import MODEL_MAP
    from backend.core.config import settings as backend_settings

    return {
        "version": "2.0.0",
        "max_inflight_per_account": backend_settings.MAX_INFLIGHT_PER_ACCOUNT,
        "auto_refill_target_min_accounts": backend_settings.AUTO_REFILL_TARGET_MIN_ACCOUNTS,
        "engine_mode": backend_settings.ENGINE_MODE,
        "model_aliases": {k: v for k, v in MODEL_MAP.items()},
    }


@router.put("/settings", dependencies=[Depends(verify_admin)])
async def update_settings(data: dict, request: Request):
    from backend.core.config import MODEL_MAP
    if "max_inflight_per_account" in data:
        value = int(data["max_inflight_per_account"])
        settings.MAX_INFLIGHT_PER_ACCOUNT = value
        request.app.state.account_pool.set_max_inflight(value)
    if "auto_refill_target_min_accounts" in data:
        settings.AUTO_REFILL_TARGET_MIN_ACCOUNTS = max(0, int(data["auto_refill_target_min_accounts"]))
    if "engine_mode" in data and data["engine_mode"] in ("httpx", "browser", "hybrid"):
        settings.ENGINE_MODE = data["engine_mode"]
    if "model_aliases" in data:
        MODEL_MAP.clear()
        MODEL_MAP.update(data["model_aliases"])
    save_runtime_config()
    wake_auto_refill_task(request)
    return {"ok": True}


@router.get("/keys", dependencies=[Depends(verify_admin)])
async def get_keys():
    from backend.core.config import API_KEYS
    return {"keys": list(API_KEYS)}


@router.post("/keys", dependencies=[Depends(verify_admin)])
async def generate_key():
    import uuid
    from backend.core.config import API_KEYS, save_api_keys
    new_key = f"sk-qwen-{uuid.uuid4().hex[:20]}"
    API_KEYS.add(new_key)
    save_api_keys(API_KEYS)
    return {"ok": True, "key": new_key}


@router.delete("/keys/{key}", dependencies=[Depends(verify_admin)])
async def delete_key(key: str):
    from backend.core.config import API_KEYS, save_api_keys
    if key in API_KEYS:
        API_KEYS.remove(key)
        save_api_keys(API_KEYS)
    return {"ok": True}
