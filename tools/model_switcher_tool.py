#!/usr/bin/env python3
"""
Model Switcher Tool — Change the LLM model used by Hermes.

Updates the active profile's ``config.yaml`` using the current Hermes model
schema so the next agent creation picks up the change.
"""

import json
import logging
import os

from hermes_cli.config import load_config, save_config
from hermes_cli.providers import TRANSPORT_TO_API_MODE, get_provider, normalize_provider
from tools.registry import registry

logger = logging.getLogger(__name__)

def _detect_lmstudio_url() -> str:
    """Use LM_STUDIO_BASE_URL or fall back to OPENAI_BASE_URL, else default."""
    lms = os.environ.get("LM_STUDIO_BASE_URL", "").strip()
    if lms:
        url = lms.rstrip("/")
        return url if url.endswith("/v1") else url + "/v1"
    current = os.environ.get("OPENAI_BASE_URL", "")
    if current and ("localhost" in current or "127.0.0.1" in current):
        return current.rstrip("/")
    return "http://localhost:1234/v1"


# Known provider base URLs
_PROVIDER_URLS = {
    "lmstudio": _detect_lmstudio_url(),
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


def switch_model_handler(args: dict, **kwargs) -> str:
    """Switch the active model in the current Hermes profile."""
    model = args.get("model", "").strip()
    if not model:
        return json.dumps({"error": "model parameter is required"})

    provider = (args.get("provider") or "").strip().lower()

    try:
        config = load_config()
        model_config = dict(config.get("model") or {})
        old_model = str(model_config.get("default") or "")
        model_config["default"] = model
        note = "Model updated in config.yaml."

        if provider:
            if provider.startswith(("http://", "https://")):
                target_provider = "custom"
                base_url = provider.rstrip("/")
                api_mode = "chat_completions"
            else:
                target_provider = normalize_provider(provider)
                provider_def = get_provider(target_provider)
                if provider_def is None:
                    return json.dumps({
                        "error": (
                            f"Unknown provider '{provider}'. Use lmstudio, openai, "
                            "openrouter, or a custom base URL."
                        )
                    })
                base_url = _PROVIDER_URLS.get(target_provider) or provider_def.base_url
                api_mode = TRANSPORT_TO_API_MODE.get(
                    provider_def.transport, "chat_completions"
                )

            model_config["provider"] = target_provider
            model_config["base_url"] = base_url
            model_config["api_mode"] = api_mode
            note += f" Provider set to {target_provider}."

        config["model"] = model_config
        save_config(
            config,
            preserve_keys={
                ("model", "default"),
                ("model", "provider"),
                ("model", "base_url"),
                ("model", "api_mode"),
            },
        )
        note += " Click + New Chat to apply."
        logger.info("Switched model from %s to %s", old_model, model)

        return json.dumps({
            "switched": True,
            "model": model,
            "previous_model": old_model,
            "note": note,
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": f"Failed to switch model: {e}"})


# ---------------------------------------------------------------------------
# Schema & Registration
# ---------------------------------------------------------------------------
SWITCH_MODEL_SCHEMA = {
    "name": "switch_model",
    "description": (
        "Switch the LLM model used by Hermes. Updates the active profile's config.yaml. "
        "The change takes effect on the next new chat. "
        "For LM Studio local models, set provider='lmstudio'. "
        "For OpenRouter, set provider='openrouter'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "description": "Model identifier (e.g. 'anthropic/claude-opus-4.6', 'qwen3-30b-a3b').",
            },
            "provider": {
                "type": "string",
                "description": (
                    "Optional provider hint: 'lmstudio', 'openai', 'openrouter', "
                    "or a custom base URL. Sets OPENAI_BASE_URL accordingly."
                ),
            },
        },
        "required": ["model"],
    },
}

registry.register(
    name="switch_model",
    toolset="model_switcher",
    schema=SWITCH_MODEL_SCHEMA,
    handler=switch_model_handler,
    # Always available — no external dependency
)
