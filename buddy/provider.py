"""Nebius configuration and a small live capability check. Never log credentials."""

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from openai import OpenAI


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"


def settings() -> dict:
    load_dotenv(ROOT / ".env", override=False)
    base_url = os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    parsed = urlparse(base_url)
    # Do not accidentally send the Nebius credential to an unrelated host.
    if parsed.scheme != "https" or parsed.hostname not in {"api.tokenfactory.nebius.com", "api.studio.nebius.com"}:
        raise ValueError("Use an HTTPS Nebius Token Factory or legacy AI Studio base URL.")
    return {"api_key": os.environ.get("NEBIUS_API_KEY", "").strip(),
            "model": os.environ.get("NEBIUS_MODEL", "").strip(), "base_url": base_url}


def live_model():
    config = settings()
    if not config["api_key"] or not config["model"]:
        raise ValueError("Set NEBIUS_API_KEY and NEBIUS_MODEL in the repository's .env file. See .env.example.")
    return ChatOpenAI(api_key=config["api_key"], model=config["model"], base_url=config["base_url"],
                      temperature=0, timeout=30, max_retries=1, max_tokens=1500,
                      use_responses_api=False, model_kwargs={"parallel_tool_calls": False})


def doctor(*, list_models: bool = False, probe: bool = False) -> int:
    config = settings()
    print("NEBIUS_API_KEY:", "present (hidden)" if config["api_key"] else "missing")
    print("NEBIUS_MODEL:", config["model"] or "not selected")
    if not config["api_key"]:
        print("Account access and tool calling are unverified. Add the key locally; do not paste it into chat.")
        return 1
    if not (list_models or probe):
        print("Configuration found. Use --list-models for access, then --probe for a small inference/tool test.")
        return 0
    client = OpenAI(api_key=config["api_key"], base_url=config["base_url"], timeout=30, max_retries=1)
    try:
        models = {model.id for model in client.models.list()}
        print(f"Authenticated model-list request succeeded ({len(models)} models).")
        if list_models:
            for model_id in sorted(models):
                print(model_id)
        if not probe:
            return 0
        if not config["model"] or config["model"] not in models:
            print("Choose NEBIUS_MODEL from this account's model list before probing.")
            return 1
        response = client.chat.completions.create(
            model=config["model"], messages=[{"role": "user", "content": "Call capability_probe with value ready."}],
            tools=[{"type": "function", "function": {"name": "capability_probe", "description": "Test tool calling.",
                     "parameters": {"type": "object", "properties": {"value": {"type": "string"}},
                                    "required": ["value"]}}}],
            tool_choice={"type": "function", "function": {"name": "capability_probe"}}, max_tokens=128)
        import json
        calls = response.choices[0].message.tool_calls or []
        works = any(call.function.name == "capability_probe" and
                    json.loads(call.function.arguments).get("value") == "ready" for call in calls)
        print("Live inference/tool-call probe:", "passed" if works else "failed; no valid probe call returned")
        print("This checks one call; it does not certify workflow quality or remaining credit balance.")
        return 0 if works else 1
    except Exception as error:
        # SDK exception bodies may include request information. Report only the type/status.
        status = getattr(error, "status_code", None)
        print(f"Nebius check failed ({type(error).__name__}, HTTP {status or 'unavailable'}).")
        return 1
    finally:
        client.close()
