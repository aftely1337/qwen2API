import json
import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    PORT: int = int(os.getenv("PORT", 7860))
    WORKERS: int = int(os.getenv("WORKERS", 3))
    ADMIN_KEY: str = os.getenv("ADMIN_KEY", "admin")

    ENGINE_MODE: str = os.getenv("ENGINE_MODE", "httpx")
    NATIVE_TOOL_PASSTHROUGH: bool = os.getenv("NATIVE_TOOL_PASSTHROUGH", "true").lower() in ("1", "true", "yes", "on")
    BROWSER_POOL_SIZE: int = int(os.getenv("BROWSER_POOL_SIZE", 2))
    MAX_INFLIGHT_PER_ACCOUNT: int = int(os.getenv("MAX_INFLIGHT", 1))
    AUTO_REFILL_TARGET_MIN_ACCOUNTS: int = int(os.getenv("AUTO_REFILL_TARGET_MIN_ACCOUNTS", os.getenv("AUTO_REFILL_TARGET", 3)))
    BROWSER_STREAM_TIMEOUT_SECONDS: int = int(os.getenv("BROWSER_STREAM_TIMEOUT_SECONDS", 1800))
    STREAM_KEEPALIVE_INTERVAL: int = int(os.getenv("STREAM_KEEPALIVE_INTERVAL", 5))

    MAX_RETRIES: int = 3
    TOOL_MAX_RETRIES: int = 2
    EMPTY_RESPONSE_RETRIES: int = 1
    RATE_LIMIT_COOLDOWN: int = 600
    ACCOUNT_MIN_INTERVAL_MS: int = int(os.getenv("ACCOUNT_MIN_INTERVAL_MS", 0))
    REQUEST_JITTER_MIN_MS: int = int(os.getenv("REQUEST_JITTER_MIN_MS", 0))
    REQUEST_JITTER_MAX_MS: int = int(os.getenv("REQUEST_JITTER_MAX_MS", 0))
    RATE_LIMIT_BASE_COOLDOWN: int = int(os.getenv("RATE_LIMIT_BASE_COOLDOWN", 600))
    RATE_LIMIT_MAX_COOLDOWN: int = int(os.getenv("RATE_LIMIT_MAX_COOLDOWN", 3600))

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    ACCOUNTS_FILE: str = os.getenv("ACCOUNTS_FILE", str(DATA_DIR / "accounts.json"))
    USERS_FILE: str = os.getenv("USERS_FILE", str(DATA_DIR / "users.json"))
    CAPTURES_FILE: str = os.getenv("CAPTURES_FILE", str(DATA_DIR / "captures.json"))
    CONFIG_FILE: str = os.getenv("CONFIG_FILE", str(DATA_DIR / "config.json"))

    CONTEXT_INLINE_MAX_CHARS: int = int(os.getenv("CONTEXT_INLINE_MAX_CHARS", 4000))
    CONTEXT_FORCE_FILE_MAX_CHARS: int = int(os.getenv("CONTEXT_FORCE_FILE_MAX_CHARS", 10000))
    CONTEXT_ATTACHMENT_TTL_SECONDS: int = int(os.getenv("CONTEXT_ATTACHMENT_TTL_SECONDS", 1800))
    CONTEXT_UPLOAD_PARSE_TIMEOUT_SECONDS: int = int(os.getenv("CONTEXT_UPLOAD_PARSE_TIMEOUT_SECONDS", 60))
    CONTEXT_GENERATED_DIR: str = os.getenv("CONTEXT_GENERATED_DIR", str(DATA_DIR / "context_files"))
    CONTEXT_CACHE_FILE: str = os.getenv("CONTEXT_CACHE_FILE", str(DATA_DIR / "context_cache.json"))
    UPLOADED_FILES_FILE: str = os.getenv("UPLOADED_FILES_FILE", str(DATA_DIR / "uploaded_files.json"))
    CONTEXT_AFFINITY_FILE: str = os.getenv("CONTEXT_AFFINITY_FILE", str(DATA_DIR / "session_affinity.json"))
    CONTEXT_ALLOWED_GENERATED_EXTS: str = os.getenv("CONTEXT_ALLOWED_GENERATED_EXTS", "txt,md,json,log")
    CONTEXT_ALLOWED_USER_EXTS: str = os.getenv("CONTEXT_ALLOWED_USER_EXTS", "txt,md,json,log,xml,yaml,yml,csv,html,css,py,js,ts,java,c,cpp,cs,php,go,rb,sh,zsh,ps1,bat,cmd,pdf,doc,docx,ppt,pptx,xls,xlsx,png,jpg,jpeg,webp,gif,tiff,bmp,svg")

    class Config:
        env_file = ".env"


API_KEYS_FILE = DATA_DIR / "api_keys.json"


def load_api_keys() -> set:
    if API_KEYS_FILE.exists():
        try:
            with open(API_KEYS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("keys", []))
        except Exception:
            pass
    return set()


def save_api_keys(keys: set):
    API_KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(API_KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump({"keys": list(keys)}, f, indent=2)


API_KEYS = load_api_keys()

VERSION = "2.0.0"

settings = Settings()

MODEL_MAP = {
    "gpt-4o": "qwen3.6-plus",
    "gpt-4o-mini": "qwen3.6-plus",
    "gpt-4-turbo": "qwen3.6-plus",
    "gpt-4": "qwen3.6-plus",
    "gpt-4.1": "qwen3.6-plus",
    "gpt-4.1-mini": "qwen3.6-plus",
    "gpt-3.5-turbo": "qwen3.6-plus",
    "gpt-5": "qwen3.6-plus",
    "o1": "qwen3.6-plus",
    "o1-mini": "qwen3.6-plus",
    "o3": "qwen3.6-plus",
    "o3-mini": "qwen3.6-plus",
    "claude-opus-4-6": "qwen3.6-plus",
    "claude-sonnet-4-6": "qwen3.6-plus",
    "claude-sonnet-4-5": "qwen3.6-plus",
    "claude-3-opus": "qwen3.6-plus",
    "claude-3.5-sonnet": "qwen3.6-plus",
    "claude-3-5-sonnet": "qwen3.6-plus",
    "claude-3-5-sonnet-latest": "qwen3.6-plus",
    "claude-3-sonnet": "qwen3.6-plus",
    "claude-3-haiku": "qwen3.6-plus",
    "claude-3-5-haiku": "qwen3.6-plus",
    "claude-3-5-haiku-latest": "qwen3.6-plus",
    "claude-haiku-4-5": "qwen3.6-plus",
    "gemini-2.5-pro": "qwen3.6-plus",
    "gemini-2.5-flash": "qwen3.6-plus",
    "gemini-1.5-pro": "qwen3.6-plus",
    "gemini-1.5-flash": "qwen3.6-plus",
    "qwen": "qwen3.6-plus",
    "qwen-max": "qwen3.6-plus",
    "qwen-plus": "qwen3.6-plus",
    "qwen-turbo": "qwen3.6-plus",
    "deepseek-chat": "qwen3.6-plus",
    "deepseek-reasoner": "qwen3.6-plus",
}

IMAGE_MODEL_DEFAULT = "qwen3.6-plus"


def load_runtime_config() -> dict:
    path = Path(settings.CONFIG_FILE)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def apply_runtime_config(data: dict):
    if not isinstance(data, dict):
        return

    try:
        if "max_inflight_per_account" in data:
            settings.MAX_INFLIGHT_PER_ACCOUNT = max(1, int(data["max_inflight_per_account"]))
    except (TypeError, ValueError):
        pass

    try:
        if "auto_refill_target_min_accounts" in data:
            settings.AUTO_REFILL_TARGET_MIN_ACCOUNTS = max(0, int(data["auto_refill_target_min_accounts"]))
    except (TypeError, ValueError):
        pass

    engine_mode = str(data.get("engine_mode", "") or "").strip().lower()
    if engine_mode in {"httpx", "browser", "hybrid"}:
        settings.ENGINE_MODE = engine_mode

    aliases = data.get("model_aliases")
    if isinstance(aliases, dict):
        MODEL_MAP.clear()
        MODEL_MAP.update({str(key): str(value) for key, value in aliases.items()})


def build_runtime_config_payload() -> dict:
    return {
        "max_inflight_per_account": int(settings.MAX_INFLIGHT_PER_ACCOUNT),
        "auto_refill_target_min_accounts": int(settings.AUTO_REFILL_TARGET_MIN_ACCOUNTS),
        "engine_mode": str(settings.ENGINE_MODE),
        "model_aliases": {key: value for key, value in MODEL_MAP.items()},
    }


def save_runtime_config():
    path = Path(settings.CONFIG_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_runtime_config_payload()
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


apply_runtime_config(load_runtime_config())


def resolve_model(name: str) -> str:
    return MODEL_MAP.get(name, name)
