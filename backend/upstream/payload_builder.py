import time
import uuid


CUSTOM_TOOL_COMPAT_FEATURE_CONFIG = {
    "thinking_enabled": True,
    "output_schema": "phase",
    "research_mode": "normal",
    "auto_thinking": True,
    "thinking_mode": "Auto",
    "thinking_format": "summary",
    "auto_search": False,
    "code_interpreter": False,
    "plugins_enabled": False,
}

CUSTOM_TOOL_LOW_LATENCY_OVERRIDES = {
    "thinking_enabled": False,
    "auto_thinking": False,
}


def build_chat_payload(chat_id: str, model: str, content: str, has_custom_tools: bool = False, files: list[dict] | None = None, chat_type: str = "t2t") -> dict:
    ts = int(time.time())
    feature_config = {
        **CUSTOM_TOOL_COMPAT_FEATURE_CONFIG,
        **(CUSTOM_TOOL_LOW_LATENCY_OVERRIDES if has_custom_tools else {}),
        # Our Anthropic/OpenAI bridge relies on textual JSON/XML tool directives
        # that are parsed locally. Enabling Qwen native function_calling here causes
        # upstream interception such as `Tool Read/Bash does not exists.` for custom
        # local tools that only exist in the bridge layer.
        "function_calling": False,
        # Additional safeguards to prevent tool call interception
        "enable_tools": False,
        "enable_function_call": False,
        "tool_choice": "none",
    }
    if chat_type in ("t2i", "image_edit") or (files and any("image" in str(f.get("file_type", "")).lower() for f in files)):
        # For image generation or editing, we must enable tools
        feature_config["enable_tools"] = True
        feature_config["plugins_enabled"] = True
        # For text to image: tool is image_gen. For image to image: tool is image_edit_tool
        feature_config["tool_choice"] = "auto"
        feature_config["image_generation"] = True
        # Ensure we don't disable function calling totally if we need native tools
        # We can let Qwen use its native tools for image processing

    return {
        "stream": True,
        "version": "2.1",
        "incremental_output": True,
        "chat_id": chat_id,
        "chat_mode": "normal",
        "model": model,
        "parent_id": None,
        "messages": [
            {
                "fid": str(uuid.uuid4()),
                "parentId": None,
                "childrenIds": [str(uuid.uuid4())],
                "role": "user",
                "content": content,
                "user_action": "chat",
                "files": files or [],
                "timestamp": ts,
                "models": [model],
                "chat_type": chat_type,
                "feature_config": feature_config,
                "extra": {"meta": {"subChatType": chat_type, "mode": chat_type}},
                "sub_chat_type": chat_type,
                "parent_id": None,
            }
        ],
        "timestamp": ts,
    }
