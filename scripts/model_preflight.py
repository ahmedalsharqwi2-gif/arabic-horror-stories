#!/usr/bin/env python3
"""Discover and validate the active LLM models before production generation.

400 means the configured model/request is invalid and is never retried.
429/5xx means a transient provider problem; the caller may switch provider.
The script writes only validated/discovered model IDs to GITHUB_ENV.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / os.getenv("MODEL_POLICY_FILE", "config/model_policy.json")
DEFAULT_GEMINI = "gemma-4-26b-a4b-it"
DEFAULT_FALLBACK = "openai/gpt-oss-120b"
DEFAULT_OPENROUTER = "google/gemini-2.5-flash"


def log(message: str, warning: bool = False) -> None:
    prefix = "::warning::" if warning else ""
    print(prefix + message)


def configured_list(*names: str) -> list[str]:
    values: list[str] = []
    for name in names:
        values.extend(x.strip() for x in os.getenv(name, "").split(",") if x.strip())
    return list(dict.fromkeys(values))


def request_json(url: str, headers: dict[str, str] | None = None, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    request_headers = dict(headers or {"Accept": "application/json"})
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, headers=request_headers, data=data)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", "replace"))
        except Exception:
            body = {}
        return exc.code, body
    except (urllib.error.URLError, TimeoutError) as exc:
        log(f"model discovery network error: {exc}", warning=True)
        return 503, {}


def load_policy() -> dict:
    try:
        data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        if data.get("schema_version") != 1:
            raise ValueError("unsupported policy schema")
        return data
    except Exception as exc:
        raise SystemExit(f"MODEL_PREFLIGHT_ERROR: cannot read {POLICY_PATH}: {exc}") from exc


def ids_from_openai(payload: dict) -> list[str]:
    return [str(item["id"]) for item in payload.get("data", []) if item.get("id")]


def select(preferred: list[str], configured: list[str], available: list[str], default: str = "",
           excluded: list[str] | tuple[str, ...] = ()) -> tuple[str, list[str]]:
    """Select only IDs confirmed by the provider catalog.

    A configured/preferred ID is not evidence that the provider still serves it.
    Returning an old default when discovery fails was the source of repeated
    404s (notably llama-3.1-8b-instant).  An empty catalog means no safe choice.
    """
    del default  # kept in the signature for backwards-compatible callers
    excluded_set = set(excluded)
    available_set = set(available) - excluded_set
    ordered = [item for item in dict.fromkeys(configured + preferred + available)
               if item not in excluded_set]
    selected = next((item for item in ordered if item in available_set), "")
    fallbacks = [item for item in ordered if item in available_set and item != selected][:5]
    return selected, fallbacks


def discover_gemini(policy: dict) -> tuple[str, list[str]]:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    configured = configured_list("GEMINI_MODEL", "GEMINI_MODELS", "GEMINI_FALLBACK_MODELS")
    preferred = policy["providers"]["gemini"].get("preferred_models", [])
    if not key:
        log("Gemini key is absent; skipping Gemini discovery", warning=True)
        return "", []
    query = urllib.parse.urlencode({"key": key, "pageSize": "100"})
    status, payload = request_json("https://generativelanguage.googleapis.com/v1beta/models?" + query)
    available = []
    for item in payload.get("models", []):
        name = str(item.get("name", "")).removeprefix("models/")
        methods = item.get("supportedGenerationMethods", [])
        if (name and "generateContent" in methods
                and not any(token in name.lower() for token in ("embedding", "tts", "audio"))):
            available.append(name)
    if status == 400:
        raise SystemExit("MODEL_PREFLIGHT_ERROR: Gemini returned HTTP 400; key or request is invalid")
    if status != 200 or not available:
        log(f"Gemini catalog unusable (HTTP {status}, {len(available)} generative models); skipping provider", warning=True)
        return "", []
    # Catalog listings can contain model aliases which the key can no longer
    # invoke (the 2.5 aliases returned 404 for this repository). Prefer only
    # explicitly configured or policy-approved candidates; don't append every
    # advertised model as an implicit fallback.
    approved = list(dict.fromkeys(configured + preferred))
    candidates = [model for model in approved if model in set(available)]
    if not candidates:
        log("Gemini has no policy-approved model in its catalog; skipping provider", warning=True)
        return "", []
    # Detail validation is still needed because restricted keys may list models
    # they cannot invoke.
    selected, fallbacks = select(preferred, configured, candidates)
    verified = []
    for candidate in [selected, *fallbacks]:
        detail_status, detail = request_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(candidate, safe='')}?key={urllib.parse.quote(key)}"
        )
        methods = detail.get("supportedGenerationMethods", []) if isinstance(detail, dict) else []
        if detail_status == 200 and "generateContent" in methods:
            verified.append(candidate)
        else:
            log(f"Gemini model {candidate} failed detail validation (HTTP {detail_status}); skipping", warning=True)
    if not verified:
        log("Gemini has no individually verified generative model; skipping provider", warning=True)
        return "", []
    return verified[0], verified[1:6]


def discover_openai_provider(name: str, endpoint: str, key: str, preferred: list[str],
                             configured_names: tuple[str, ...], default: str,
                             excluded_models: list[str] | tuple[str, ...] = ()) -> tuple[str, list[str]]:
    configured = configured_list(*configured_names)
    excluded = set(excluded_models)
    configured = [model for model in configured if model not in excluded]
    preferred = [model for model in preferred if model not in excluded]
    if not key:
        log(f"{name} key is absent; skipping discovery", warning=True)
        return "", []
    base = endpoint.removesuffix("/chat/completions").removesuffix("/")
    status, payload = request_json(base + "/models", {"Authorization": "Bearer " + key, "Accept": "application/json"})
    available = ids_from_openai(payload)
    if name == "OpenRouter":
        available = [item for item in available if not any(token in item.lower() for token in ("embedding", "whisper", "tts"))]
    if status == 400:
        raise SystemExit(f"MODEL_PREFLIGHT_ERROR: {name} returned HTTP 400 for /models")
    if status == 403 and (configured or preferred):
        verified = []
        for candidate in list(dict.fromkeys(configured + preferred))[:6]:
            probe_status, _ = request_json(endpoint,
                {"Authorization": "Bearer " + key},
                {"model": candidate, "messages": [{"role": "user", "content": "Reply OK."}],
                 "max_tokens": 64},
            )
            if probe_status == 200:
                verified.append(candidate)
        if verified:
            log(f"{name} catalog forbidden; completion probe confirmed {verified[0]}")
            return verified[0], verified[1:]
    if status != 200 or not available:
        log(f"{name} catalog unusable (HTTP {status}, {len(available)} models); skipping provider", warning=True)
        return "", []
    if name == "Fallback":
        # Groq may enumerate legacy/enterprise-only IDs. Only use candidates
        # maintained in policy or explicitly configured, never every catalog ID.
        approved = set(configured + preferred)
        available = [model for model in available if model in approved]
    selected, fallbacks = select(preferred, configured, available, excluded=excluded_models)
    if not selected:
        log(f"{name} catalog has no selectable model; skipping provider (available={available[:8]})", warning=True)
        return "", []
    return selected, fallbacks


def write_env(values: dict[str, str]) -> None:
    path = os.getenv("GITHUB_ENV")
    if not path:
        for key, value in values.items():
            print(f"{key}={value}")
        return
    with open(path, "a", encoding="utf-8") as output:
        # Always write every key, including empty values, so a failed provider
        # discovery cannot leak a stale default into the generation step.
        for key, value in values.items():
            output.write(f"{key}={value}\n")


def main() -> int:
    policy = load_policy()
    gemini, gemini_fallbacks = discover_gemini(policy)
    fallback_endpoint = os.getenv("LLM_FALLBACK_ENDPOINT", "https://api.groq.com/openai/v1/chat/completions")
    fallback, fallback_models = discover_openai_provider(
        "Fallback LLM", fallback_endpoint,
        os.getenv("LLM_FALLBACK_API_KEY", os.getenv("GROQ_API_KEY", "")).strip(),
        policy["providers"]["fallback"].get("preferred_models", []),
        ("LLM_FALLBACK_MODEL", "GROQ_MODEL", "GROQ_MODELS"), DEFAULT_FALLBACK,
        policy["providers"]["fallback"].get("excluded_models", []),
    )
    openrouter, openrouter_fallbacks = discover_openai_provider(
        "OpenRouter", "https://openrouter.ai/api/v1/chat/completions",
        os.getenv("OPENROUTER_API_KEY", "").strip(),
        policy["providers"]["openrouter"].get("preferred_models", []),
        ("OPENROUTER_MODEL", "OPENROUTER_MODELS"), DEFAULT_OPENROUTER,
        policy["providers"]["openrouter"].get("excluded_models", []),
    )
    values = {
        "GEMINI_MODEL": gemini,
        "GEMINI_MODELS": ",".join([x for x in [gemini, *gemini_fallbacks] if x]),
        "GEMINI_FALLBACK_MODELS": ",".join(gemini_fallbacks),
        "LLM_FALLBACK_MODEL": fallback,
        "LLM_FALLBACK_MODELS": ",".join([x for x in [fallback, *fallback_models] if x]),
        "GROQ_MODEL": fallback,
        "GROQ_MODELS": ",".join([x for x in [fallback, *fallback_models] if x]),
        "OPENROUTER_MODEL": openrouter,
        "OPENROUTER_MODELS": ",".join([x for x in [openrouter, *openrouter_fallbacks] if x]),
    }
    if not any(values[key] for key in ("GEMINI_MODEL", "LLM_FALLBACK_MODEL", "OPENROUTER_MODEL")):
        raise SystemExit("MODEL_PREFLIGHT_ERROR: no provider has a usable model")
    write_env(values)
    log("Model preflight passed")
    for provider, key in (("Gemini", "GEMINI_MODEL"), ("Fallback", "LLM_FALLBACK_MODEL"), ("OpenRouter", "OPENROUTER_MODEL")):
        if values[key]:
            log(f"{provider}: {values[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
