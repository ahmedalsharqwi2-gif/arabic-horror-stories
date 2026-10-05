# -*- coding: utf-8 -*-
"""
بوابة توليد الحلقات (LLM Gateway)

الفكرة الأساسية:
  - كل مزوّد (موديل) ياخد فرصة حقيقية قبل ما ننتقل للي بعده.
  - الفحص جزء من معنى "النجاح": أي رد بايظ (JSON ناقص، نص مقطوع، مخالف للقواعد)
    يُحسب فشل وننتقل للمرشح التالي، ومش بنعتبره رد سليم.
  - الأخطاء بتتصنف: مؤقتة (نستنى ونعيد)، حصة/دائمة (نتخطى المزوّد فورًا)،
    ورد غير صالح (نعيد مع ملاحظة بالمشكلة، ولو مقطوع نزوّد الميزانية).

الترتيب:  موديلات Gemini بالتتابع  ->  Groq (مخرجات منظّمة صارمة)  ->  OpenRouter (احتياطي أخير)
"""

import json
import os
import random
import re
import signal
import time
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Optional

# ───────────────────────── الإعدادات ─────────────────────────
LLM_RETRIES = max(1, int(os.getenv("LLM_RETRIES", "3")))                  # محاولات لكل مزوّد عند الأخطاء المؤقتة
LLM_INVALID_RETRIES = max(1, int(os.getenv("LLM_INVALID_RETRIES", "2")))  # محاولات لكل مزوّد عند الرد غير الصالح
LLM_DEADLINE_SECONDS = int(os.getenv("LLM_DEADLINE_SECONDS", "480"))      # سقف زمني كلي لكل جولة
BACKOFF_BASE = float(os.getenv("LLM_BACKOFF_BASE", "4"))
BACKOFF_MAX = float(os.getenv("LLM_BACKOFF_MAX", "40"))
BUDGET_STEP = float(os.getenv("LENGTH_ESCALATION", "1.5"))                # مضاعف الميزانية عند القطع
MAX_BUDGET = int(os.getenv("LLM_MAX_BUDGET", "16000"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.9"))
REQUEST_TIMEOUT = int(os.getenv("LLM_REQUEST_TIMEOUT", "120"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
# سلسلة موديلات Gemini: الأساسي ثم بدائل أخف وأكثر توفرًا (بدون تكرار)
GEMINI_MODELS = list(dict.fromkeys(
    m.strip() for m in os.getenv(
        "GEMINI_MODELS", f"{GEMINI_MODEL}"
    ).split(",") if m.strip()
))
# التفكير الداخلي بيستهلك من max_output_tokens وبيسبب قطع الرد؛ الصفر يقفله (-1 يتركه للموديل)
GEMINI_THINKING_BUDGET = int(os.getenv("GEMINI_THINKING_BUDGET", "0"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_MODELS = list(dict.fromkeys(
    m.strip() for m in os.getenv("GROQ_MODELS", GROQ_MODEL).split(",") if m.strip()
))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "")
OPENROUTER_MODELS = list(dict.fromkeys(
    m.strip() for m in os.getenv("OPENROUTER_MODELS", OPENROUTER_MODEL).split(",") if m.strip()
))

# حدود طول السرد بالكلمات (الموديل بيقدّر الكلمات أدق بكثير من الثواني)
WORDS_MIN = int(os.getenv("NARRATION_WORDS_MIN", "230"))
WORDS_MAX = int(os.getenv("NARRATION_WORDS_MAX", "320"))

STORY_TYPES = ("true_case", "unexplained_event", "urban_legend")

REQUIRED_KEYS = {
    "title", "hook", "region", "story_type", "basis", "narration",
    "visual_keywords", "visual_match", "caption", "phonetic_hints",
    "verification_report", "production_table", "authenticity_label", "final_checks",
}

# ───────────────────────── مخطط الحلقة ─────────────────────────
EPISODE_SCHEMA = {
    "name": "episode",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "hook": {"type": "string"},
            "region": {"type": "string"},
            "story_type": {"type": "string", "enum": list(STORY_TYPES)},
            "basis": {"type": "string"},
            "narration": {"type": "string"},
            "visual_keywords": {"type": "array", "items": {"type": "string"}},
            "visual_match": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string"},
                        "scene": {"type": "string"},
                        "place": {"type": "string"},
                        "source_type": {"type": "string"},
                        "authenticity": {"type": "string", "enum": [
                            "REAL_ARCHIVE", "REAL_LOCATION", "MAP", "SYMBOLIC",
                            "REENACTMENT", "AI_RECONSTRUCTION",
                        ]},
                        "status": {"type": "string", "enum": ["PASS"]},
                        "audio_decision": {"type": "string", "enum": [
                            "ORIGINAL AUDIO", "ORIGINAL AUDIO + VOICE",
                            "ORIGINAL AUDIO + VOICE DUCKING", "ORIGINAL AUDIO + MUSIC",
                            "ORIGINAL AUDIO + VOICE + MUSIC", "VOICE ONLY", "MUTE",
                        ]},
                        "audio_match": {"type": "string", "enum": ["PASS"]},
                        "label": {"type": "string"},
                    },
                    "required": [
                        "keyword", "scene", "place", "source_type", "authenticity",
                        "status", "audio_decision", "audio_match", "label",
                    ],
                    "additionalProperties": False,
                },
            },
            "caption": {"type": "string"},
            "verification_report": {
                "type": "object",
                "properties": {
                    "case_name": {"type": "string"},
                    "classification": {"type": "string", "enum": list(STORY_TYPES)},
                    "period": {"type": "string"},
                    "location": {"type": "string"},
                    "people": {"type": "array", "items": {"type": "string"}},
                    "facts": {"type": "array", "items": {"type": "string"}},
                    "sources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "publisher_or_author": {"type": "string"},
                                "date": {"type": "string"},
                                "url": {"type": "string"},
                                "tier": {"type": "string", "enum": [
                                    "primary", "official", "reputable_press", "academic",
                                    "archive", "interview", "public_reference",
                                ]},
                                "supports": {"type": "string"},
                            },
                            "required": [
                                "title", "publisher_or_author", "date", "url", "tier", "supports",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "confirmed_claims": {"type": "array", "items": {"type": "string"}},
                    "disputed_claims": {"type": "array", "items": {"type": "string"}},
                    "excluded_claims": {"type": "array", "items": {"type": "string"}},
                    "verified_quotes": {"type": "array", "items": {"type": "string"}},
                    "decision": {"type": "string", "enum": ["APPROVED"]},
                },
                "required": [
                    "case_name", "classification", "period", "location", "people",
                    "facts", "sources", "confirmed_claims", "disputed_claims",
                    "excluded_claims", "verified_quotes", "decision",
                ],
                "additionalProperties": False,
            },
            "production_table": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "time": {"type": "string"},
                        "narration": {"type": "string"},
                        "scene": {"type": "string"},
                        "scene_source": {"type": "string"},
                        "sound_effect": {"type": "string"},
                        "music": {"type": "string"},
                        "subtitle": {"type": "string"},
                        "tension": {"type": "integer"},
                    },
                    "required": [
                        "time", "narration", "scene", "scene_source", "sound_effect",
                        "music", "subtitle", "tension",
                    ],
                    "additionalProperties": False,
                },
            },
            "authenticity_label": {"type": "string", "enum": ["REAL_EVENT", "UNEXPLAINED_EVENT", "URBAN_LEGEND"]},
            "final_checks": {
                "type": "object",
                "properties": {
                    key: {"type": "string", "enum": ["PASS"]}
                    for key in (
                        "fact_check", "visual_check", "horror_check", "authenticity_check",
                        "audio_check", "subtitle_check", "sensitivity_check",
                    )
                },
                "required": [
                    "fact_check", "visual_check", "horror_check", "authenticity_check",
                    "audio_check", "subtitle_check", "sensitivity_check",
                ],
                "additionalProperties": False,
            },
            "phonetic_hints": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "word": {"type": "string"},
                        "phonetic": {"type": "string"},
                    },
                    "required": ["word", "phonetic"],
                    "additionalProperties": False,
                },
            },
        },
        "required": sorted(REQUIRED_KEYS),
        "additionalProperties": False,
    },
}


# ───────────────────────── الأخطاء وتصنيفها ─────────────────────────
class OutputError(Exception):
    """رد وصل من المزوّد لكنه غير صالح (JSON بايظ أو مقطوع أو مخالف للقواعد)."""

    def __init__(self, problem: str, truncated: bool = False):
        super().__init__(problem)
        self.problem = problem
        self.truncated = truncated


class ProviderTimeout(TimeoutError):
    """A provider call exceeded the hard wall-clock limit."""


def _run_with_timeout(fn: Callable, timeout_seconds: int, label: str):
    """Run a blocking provider call with a real process-level wall clock.

    The Gemini SDK call previously had no timeout at all: the outer deadline was
    checked only before entering the SDK, so a stuck socket could keep Actions
    alive indefinitely. GitHub runners are Linux and execute this CLI on the
    main thread, making SIGALRM a reliable last-resort circuit breaker. If a
    caller embeds the gateway in a non-main thread, we still execute normally;
    the workflow-level timeout remains the final guard in that unusual case.
    """
    if timeout_seconds <= 0:
        return fn()
    try:
        previous_handler = signal.getsignal(signal.SIGALRM)
        previous_timer = signal.getitimer(signal.ITIMER_REAL)

        def _alarm_handler(_signum, _frame):
            raise ProviderTimeout(f"{label} timed out after {timeout_seconds}s")

        signal.signal(signal.SIGALRM, _alarm_handler)
    except (ValueError, AttributeError):
        # Signals are unavailable outside the main interpreter thread.
        return fn()

    signal.setitimer(signal.ITIMER_REAL, float(timeout_seconds))
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


QUOTA_MARKERS = (
    "PerDay", "per day", "daily limit", "insufficient_quota",
    "free-models-per-day", "exceeded your current quota", "RESOURCE_EXHAUSTED",
)
_CREDIT_MARKERS = ("402", "insufficient credit", "requires more credits", "not enough credits")
RATE_MARKERS = ("429", "RESOURCE_EXHAUSTED", "rate limit", "rate_limit")
TRANSIENT_MARKERS = ("500", "502", "503", "504", "UNAVAILABLE", "overloaded",
                     "timed out", "timeout", "temporarily", "connection")
PERMANENT_MARKERS = ("400", "401", "402", "403", "404", "PERMISSION_DENIED",
                     "INVALID_ARGUMENT", "NOT_FOUND", "API key", "is not set")


def _has(msg: str, markers) -> bool:
    for m in markers:
        pattern = rf"\b{re.escape(m)}\b" if m.isdigit() else re.escape(m)
        if re.search(pattern, msg, flags=re.I):
            return True
    return False


def classify(exc: Exception) -> str:
    """يرجّع: invalid | quota | rate | transient | permanent | unknown"""
    if isinstance(exc, ProviderTimeout):
        return "transient"
    if isinstance(exc, OutputError):
        return "invalid"
    status = getattr(exc, "status_code", None)
    message = str(exc)
    response = getattr(exc, "response", None)
    body = getattr(response, "text", "") if response is not None else ""
    details = f"{message} {body}"
    if status == 402 or _has(details, _CREDIT_MARKERS):
        return "quota"
    if status == 429:
        return "quota" if _has(details, QUOTA_MARKERS) else "rate"
    if status == 408:
        return "rate"
    if status in (500, 502, 503, 504):
        return "transient"
    if status == 400 and "max completion tokens reached" in details.lower():
        return "invalid"
    if status in (400, 401, 402, 403, 404):
        return "permanent"
    if _has(details, QUOTA_MARKERS):
        return "quota"      # حصة يومية خلصت: مفيش فايدة من الإعادة
    if _has(details, RATE_MARKERS):
        return "rate"
    if _has(details, TRANSIENT_MARKERS):
        return "transient"
    if _has(details, PERMANENT_MARKERS):
        return "permanent"  # مفتاح ناقص/صلاحية/معامل غير مدعوم
    return "unknown"


def _backoff(attempt: int) -> float:
    base = min(BACKOFF_BASE * 2 ** (attempt - 1), BACKOFF_MAX)
    return base * random.uniform(0.75, 1.25)  # عشوائية بسيطة عشان مانضربش الخدمة في نفس اللحظة


MAX_RETRY_AFTER_SECONDS = 60


def _retry_after_seconds(exc: Exception) -> float | None:
    """Parse Retry-After seconds/date and cap waits so one provider cannot stall the run."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) if response is not None else {}
    raw = (headers.get("Retry-After") or headers.get("retry-after")) if headers else None
    if not raw:
        return None
    try:
        delay = float(raw)
    except (TypeError, ValueError):
        try:
            retry_at = parsedate_to_datetime(str(raw))
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            delay = retry_at.timestamp() - time.time()
        except (TypeError, ValueError, OverflowError):
            return None
    return max(0.0, min(delay, MAX_RETRY_AFTER_SECONDS))


# ───────────────────────── تحليل الرد ─────────────────────────
def parse_episode_json(raw: str) -> dict:
    """محلل متسامح: يشيل الـ think والأسوار البرمجية ويستخرج أول كائن JSON."""
    text = (raw or "").strip()
    if not text:
        raise OutputError("الرد فاضي", truncated=True)
    if "<think>" in text and "</think>" not in text:
        raise OutputError("الرد اتقطع أثناء التفكير", truncated=True)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I).strip()

    start, end = text.find("{"), text.rfind("}")
    if start == -1:
        raise OutputError("مفيش JSON في الرد")
    if end <= start:
        raise OutputError("JSON مقطوع (مفيش قوس إغلاق)", truncated=True)

    body = text[start:end + 1]
    try:
        return json.loads(body)
    except json.JSONDecodeError as first:
        # إصلاح خفيف: فواصل زائدة قبل الأقواس
        fixed = re.sub(r",\s*([}\]])", r"\1", body)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            raise OutputError(f"JSON بايظ: {first.msg} عند الموضع {first.pos}") from first


# ───────────────────────── فحص الحلقة ─────────────────────────
_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")


def strip_tashkeel(s: str) -> str:
    return _DIACRITICS.sub("", s)


BANNED_OPENERS = ("في ليلة مظلمة", "هذه قصة حقيقية", "لن تصدق", "استعد لسماع",
                  "قصة حقيقية حدثت", "هل تعلم")
# عبارات ممنوعة في نمط الخيال العلمي لأنها بتقدّم الخيال كحقيقة
REAL_CLAIMS = ("قصة حقيقية", "حدثت فعلا", "وقعت فعلا", "موثقة رسميا", "حادثة حقيقية")
EVIDENCE_MARKERS = ("مصدر", "تقرير", "سجل", "صحيفة", "أرشيف", "وثيقة", "موثق", "متداول", "شهادة")


def make_validator(find_content_red_flag: Optional[Callable] = None,
                   looks_truncated: Optional[Callable] = None) -> Callable:
    """يبني دالة فحص. مرّر دوالك الحالية من main.py (اختياري)."""

    def validate(ep) -> None:
        if not isinstance(ep, dict):
            raise OutputError("الرد مش كائن JSON")
        missing = REQUIRED_KEYS - set(ep.keys())
        if missing:
            raise OutputError(f"حقول ناقصة: {sorted(missing)}")
        if ep["story_type"] not in STORY_TYPES:
            raise OutputError("قيمة story_type لازم تكون true_case أو unexplained_event أو urban_legend")

        hook = str(ep["hook"]).strip()
        narration = str(ep["narration"]).strip()
        plain = strip_tashkeel(narration)

        if not hook:
            raise OutputError("hook فاضي")
        if len(hook.split()) > 25:
            raise OutputError("hook أطول من اللازم (الحد الأقصى 25 كلمة)")
        for opener in BANNED_OPENERS:
            if hook.startswith(opener) or narration.startswith(opener):
                raise OutputError(f"افتتاحية مستهلكة ممنوعة: {opener}")

        words = len(narration.split())
        cut = bool(looks_truncated and looks_truncated(narration))
        if cut:
            raise OutputError("نص narration مقطوع", truncated=True)
        if words < WORDS_MIN:
            raise OutputError(f"narration قصير: {words} كلمة والمطلوب من {WORDS_MIN} إلى {WORDS_MAX}")
        if words > WORDS_MAX:
            raise OutputError(f"narration طويل: {words} كلمة والمطلوب من {WORDS_MIN} إلى {WORDS_MAX}")

        if find_content_red_flag:
            flag = find_content_red_flag(narration)
            if flag:
                raise OutputError(f"النص يحتوي مصطلحًا مرفوضًا: {flag}")

        if not str(ep["basis"]).strip():
            raise OutputError("basis فاضي")

        kws = ep["visual_keywords"]
        if not isinstance(kws, list) or not (7 <= len(kws) <= 8):
            raise OutputError("visual_keywords لازم يكون من 7 إلى 8 كلمات بحث")
        for k in kws:
            if not isinstance(k, str) or not re.fullmatch(r"[A-Za-z0-9 ,'\-]+", k.strip()):
                raise OutputError(f"كلمة بحث لازم تكون إنجليزية فقط: {k!r}")
            count = len(k.split())
            if not 3 <= count <= 5:
                raise OutputError(f"كلمة البحث يجب أن تكون من 3 إلى 5 كلمات: {k!r}")

        if "#" not in str(ep["caption"]):
            raise OutputError("caption من غير هاشتاجات")

        valid_hints = []
        for h in ep["phonetic_hints"]:
            if not isinstance(h, dict) or "word" not in h or "phonetic" not in h:
                print("⚠️ phonetic_hints غير صالحة؛ سيتم تجاهلها والمتابعة بالنص الطبيعي")
                continue
            word, phonetic = str(h["word"]).strip(), str(h["phonetic"]).strip()
            if not word or not phonetic or strip_tashkeel(phonetic) != word or word not in plain:
                print(f"⚠️ تلميح نطق غير قابل للتحقق ({word or 'فارغ'})؛ سيتم تجاهله")
                continue
            valid_hints.append({"word": word, "phonetic": phonetic})
        ep["phonetic_hints"] = valid_hints

    return validate


# ───────────────────────── المزوّدون ─────────────────────────
@dataclass
class Provider:
    label: str
    fn: Callable[[str, str, int], str]
    dead: bool = False  # لو true نتخطاه لباقي التشغيل
    family: str = ""    # models sharing credentials/quota (e.g. all OpenRouter models)


def _gemini_completion(system_prompt, user_message, budget, model, gemini_schema) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)

    def _call(with_thinking: bool):
        cfg = dict(
            system_instruction=system_prompt,
            temperature=TEMPERATURE,
            max_output_tokens=budget,
            response_mime_type="application/json",
            response_schema=gemini_schema,
        )
        if with_thinking:
            cfg["thinking_config"] = types.ThinkingConfig(thinking_budget=GEMINI_THINKING_BUDGET)
        return client.models.generate_content(
            model=model, contents=user_message,
            config=types.GenerateContentConfig(**cfg),
        )

    try:
        response = _run_with_timeout(
            lambda: _call(GEMINI_THINKING_BUDGET >= 0),
            REQUEST_TIMEOUT,
            f"Gemini {model}",
        )
    except Exception as exc:  # noqa: BLE001
        # بعض الموديلات ما بتقبلش إعداد التفكير: نعيد بدونه بدل ما نخسر الموديل كله
        if "thinking" in str(exc).lower() and not isinstance(exc, ProviderTimeout):
            response = _run_with_timeout(
                lambda: _call(False), REQUEST_TIMEOUT, f"Gemini {model}"
            )
        else:
            raise

    finish = ""
    try:
        finish = str(response.candidates[0].finish_reason)
    except Exception:  # noqa: BLE001
        pass
    if "MAX_TOKENS" in finish:
        raise OutputError(f"Gemini {model} قطع الرد (MAX_TOKENS)", truncated=True)
    text = (response.text or "").strip()
    if not text:
        raise OutputError(f"Gemini {model} رجّع رد فاضي (finish={finish or '?'})")
    return text


def _post_chat(url, key, payload, label, extra_headers=None) -> str:
    import requests

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    r = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        error = RuntimeError(f"{label} HTTP {r.status_code}: {r.text[:200]}")
        # ProviderPool uses this metadata to avoid retrying invalid 400/404
        # requests and to retry/reroute transient 429/5xx responses.
        error.status_code = r.status_code
        error.response = r
        if r.status_code == 400 and "max completion tokens reached" in r.text.lower():
            raise OutputError(f"{label} قطع JSON قبل اكتماله", truncated=True) from error
        raise error
    choice = (r.json().get("choices") or [{}])[0]
    if choice.get("finish_reason") == "length":
        raise OutputError(f"{label} قطع الرد (length)", truncated=True)
    text = ((choice.get("message") or {}).get("content") or "").strip()
    if not text:
        raise OutputError(f"{label} رجّع رد فاضي")
    return text


def _groq_completion_for_model(system_prompt, user_message, budget, schema, model) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": TEMPERATURE,
        "max_completion_tokens": budget,
        "reasoning_effort": "low",  # عشان التفكير مايأكلش الميزانية
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "episode", "strict": True, "schema": schema},
        },
    }
    return _post_chat("https://api.groq.com/openai/v1/chat/completions",
                      GROQ_API_KEY, payload, f"Groq {model}")

def _groq_completion(system_prompt, user_message, budget, schema) -> str:
    """Backward-compatible wrapper for callers that use the primary model."""
    return _groq_completion_for_model(system_prompt, user_message, budget, schema, GROQ_MODEL)


def _openrouter_completion(system_prompt, user_message, budget, keys_hint, model=None) -> str:
    # json_object مش بيفرض مخطط، فبنكتب المفاتيح المطلوبة صراحة داخل التعليمات
    payload = {
        "model": model or OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt + "\n\n" + keys_hint},
            {"role": "user", "content": user_message},
        ],
        "temperature": TEMPERATURE,
        "max_tokens": budget,
        "response_format": {"type": "json_object"},
        "reasoning": {"effort": "low"},
    }
    return _post_chat("https://openrouter.ai/api/v1/chat/completions",
                      OPENROUTER_API_KEY, payload, "OpenRouter")


def build_providers(episode_schema=EPISODE_SCHEMA, to_gemini_schema=None):
    """يبني السلسلة حسب المفاتيح المتاحة فقط (مفيش مزوّد بدون مفتاح)."""
    schema = episode_schema["schema"]
    gemini_schema = to_gemini_schema(schema) if to_gemini_schema else schema
    keys_hint = ("أخرج كائن JSON واحدًا فقط، بدون أي نص قبله أو بعده، وبهذه المفاتيح بالضبط: "
                 + ", ".join(sorted(REQUIRED_KEYS)))

    providers = []
    prefer_openrouter = os.getenv("PREFER_OPENROUTER", "false").lower() == "true"

    def add_openrouter() -> None:
        if OPENROUTER_API_KEY:
            for m in OPENROUTER_MODELS:
                providers.append(Provider(
                    f"openrouter:{m}",
                    lambda sp, um, b, m=m: _openrouter_completion(sp, um, b, keys_hint, model=m),
                    family="openrouter"))

    if prefer_openrouter:
        add_openrouter()
    if GEMINI_API_KEY:
        for m in GEMINI_MODELS:
            providers.append(Provider(
                f"gemini:{m}",
                lambda sp, um, b, m=m: _gemini_completion(sp, um, b, m, gemini_schema),
                family="gemini"))
    if GROQ_API_KEY:
        for m in GROQ_MODELS:
            providers.append(Provider(
                f"groq:{m}",
                lambda sp, um, b, m=m: _groq_completion_for_model(sp, um, b, schema, m),
                family="groq"))
    if not prefer_openrouter:
        add_openrouter()
    if not providers:
        raise RuntimeError("مفيش أي مفتاح API متضبط (GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY)")
    return providers


# ───────────────────────── القلب: توليد حلقة سليمة ─────────────────────────
def generate_valid_episode(system_prompt, user_message, budget, providers, validate,
                           sleep=time.sleep, clock=time.monotonic):
    """يرجّع (الحلقة، اسم المزوّد). يرفع RuntimeError لو فشل الجميع."""
    deadline = clock() + LLM_DEADLINE_SECONDS
    errors = []
    provider_feedback = ""

    for prov in providers:
        if prov.dead:
            continue
        cur_budget = budget
        # لا نرسل نفس الموضوع للمزوّد التالي بعد رفضه كتكرار.
        feedback = provider_feedback
        transient_tries = 0
        invalid_tries = 0

        while True:
            if clock() > deadline:
                errors.append("تجاوزنا الحد الزمني الكلي للجولة")
                raise RuntimeError(" | ".join(errors[-8:]))
            call_started = clock()
            print(
                f"⏳ بدء طلب {prov.label} | المحاولة المؤقتة {transient_tries + 1}/"
                f"{LLM_RETRIES} | مضى {int(call_started - (deadline - LLM_DEADLINE_SECONDS))}ث"
            )
            episode = None
            try:
                raw = prov.fn(system_prompt, user_message + feedback, cur_budget)
                print(f"✅ وصل رد {prov.label} خلال {clock() - call_started:.1f}ث")
                episode = parse_episode_json(raw)
                validate(episode)  # الفحص جزء من النجاح
                return episode, prov.label
            except Exception as exc:  # noqa: BLE001
                kind = classify(exc)
                errors.append(f"{prov.label} [{kind}]: {str(exc)[:150]}")
                print(f"⚠️ {errors[-1]}")

                status = getattr(exc, "status_code", None)
                if kind == "quota" or status in (401, 402, 403):
                    # Billing/quota/auth failures apply to the credential, not
                    # just one model; skip all siblings to avoid repeated 402s.
                    for candidate in providers:
                        if candidate is prov or (prov.family and candidate.family == prov.family):
                            candidate.dead = True
                    break

                if kind == "permanent":
                    # 400/404 is usually model/request-specific: skip this model
                    # but preserve other candidates in the same provider family.
                    prov.dead = True
                    break

                if kind == "invalid":
                    invalid_tries += 1
                    if invalid_tries >= LLM_INVALID_RETRIES:
                        break
                    if getattr(exc, "truncated", False) or "قصير" in str(exc):
                        cur_budget = min(max(cur_budget + 256, int(cur_budget * BUDGET_STEP)), MAX_BUDGET)
                    problem = getattr(exc, "problem", str(exc))
                    prior = ""
                    if isinstance(episode, dict):
                        prior_narration = str(episode.get("narration", "")).strip()
                        prior_words = len(prior_narration.split())
                        missing_words = max(0, WORDS_MIN - prior_words)
                        missing_keys = sorted(REQUIRED_KEYS - set(episode.keys()))
                        prior = (
                            f"\nالناتج السابق كان يحتوي {prior_words} كلمة في narration؛ "
                            f"أضف {missing_words} كلمة جديدة على الأقل، وانسخ السرد السابق ثم أكمله "
                            "بمعلومات ومشاهد جديدة من دون تكرار المقدمة.\n"
                            f"النarration السابق:\n{prior_narration}\n"
                            f"الحقول الناقصة التي يجب إرجاعها: {missing_keys or 'لا يوجد'}."
                        )
                    feedback = (
                        f"\n\n[تصحيح إلزامي: {problem}. أعد كائن JSON كاملًا بالمفاتيح كلها. "
                        f"يجب أن يكون narration بين {WORDS_MIN} و{WORDS_MAX} كلمة فعلية."
                        f"{prior}\nلا تكتب أي شرح خارج JSON.]"
                    )
                    if any(marker in problem.lower() for marker in ("مكرر", "قريب جدًا", "duplicate", "similar")):
                        feedback += (
                            "\nهذا الموضوع مرفوض نهائيًا؛ اختر حادثة أو فكرة أو منطقة مختلفة جذريًا، "
                            "ولا تعِد صياغة أي عنوان أو واقعة من القائمة السابقة."
                        )
                    provider_feedback = feedback
                    continue

                if kind == "rate":
                    transient_tries += 1
                    if transient_tries >= LLM_RETRIES:
                        prov.dead = True
                        break
                    delay = _retry_after_seconds(exc)
                    if delay is None:
                        delay = _backoff(transient_tries)
                    print(f"⏳ {prov.label} rate-limited; retrying in {delay:.1f}s")
                    sleep(delay)
                    continue

                # transient / unknown: انتظار تصاعدي ثم إعادة
                transient_tries += 1
                if transient_tries >= LLM_RETRIES:
                    break
                sleep(_backoff(transient_tries))

    raise RuntimeError("فشل كل المزوّدين: " + " | ".join(errors[-8:]))


# ───────────────────────── اختيار النمط ورسالة المستخدم ─────────────────────────
def pick_story_type() -> str:
    """تبديل تلقائي بين النمطين حسب رقم التشغيل في GitHub Actions، أو فرض نمط عبر STORY_TYPE."""
    forced = os.getenv("STORY_TYPE", "").strip()
    if forced in STORY_TYPES:
        return forced
    try:
        run = int(os.getenv("GITHUB_RUN_NUMBER", "0") or 0)
    except ValueError:
        run = 0
    return STORY_TYPES[run % 2]


def build_user_message(story_type, used_hooks=(), recent_regions=()) -> str:
    kind_line = {
        "true_case": "النمط المطلوب: story_type = true_case (حادثة أو قضية حقيقية موثقة).",
        "unexplained_event": "النمط المطلوب: story_type = unexplained_event (واقعة موثقة لم يحسم تفسيرها).",
        "urban_legend": "النمط المطلوب: story_type = urban_legend (قصة متداولة موسومة بوضوح وليست حقيقة مثبتة).",
    }[story_type]
    hooks = "\n".join(f"- {h}" for h in list(used_hooks)[-40:]) or "- (لا يوجد)"
    regions = "، ".join(list(recent_regions)[-5:]) or "لا يوجد"
    return (
        f"{kind_line}\n\n"
        f"الهوكات المستخدمة سابقًا (ممنوع تكرار نفس الواقعة أو الفكرة بأي زاوية):\n{hooks}\n\n"
        f"مناطق الحلقات الأخيرة (اختر منطقة مختلفة): {regions}\n\n"
        "اكتب حلقة جديدة تمامًا وأخرج JSON فقط."
    )


def generate_episode(system_prompt, budget, validate, to_gemini_schema=None,
                     used_hooks=(), recent_regions=(), rounds=3, cooldown=30,
                     user_message=None):
    """Generate an episode, refreshing the topic prompt after duplicate rejection."""
    story_type = pick_story_type()
    user_message = build_user_message(story_type, used_hooks, recent_regions) + "\n" + (user_message or "")
    user_message += (
        f"\nقواعد الإخراج الإلزامية: narration من {WORDS_MIN} إلى {WORDS_MAX} كلمة عربية فعلية. "
        "hook لا يتجاوز 25 كلمة. visual_keywords من 7 إلى 8 عبارات بحث إنجليزية، "
        "كل عبارة من 3 إلى 5 كلمات محددة للمكان والنشاط. "
        "اربط كل عبارة بصف visual_match مطابق. أنهِ narration بخلاصة واقعية مكتملة "
        "توضح ما ثبت وما بقي مجهولًا؛ لا تنه السرد بسؤال. "
        "أعد verification_report وproduction_table وبقية الحقول كاملة دون اختلاق تفاصيل."
    )

    def _validate(ep):
        validate(ep)
        if ep.get("story_type") != story_type:
            raise OutputError(f"story_type لازم يساوي {story_type}")

    last_error = ""
    # Keep quota/auth/billing exclusions across all rounds of this run.
    providers = build_providers(to_gemini_schema=to_gemini_schema)
    for rnd in range(1, rounds + 1):
        round_message = user_message
        if rnd > 1:
            # A duplicate is a content-selection failure, not a reason to stop
            # the pipeline. Explicitly invalidate the previous candidate and
            # require a different incident, hook, and region in the next round.
            round_message += (
                "\n\n[تصحيح المحاولة السابقة] عالج سبب الرفض الوارد أدناه مع الالتزام بكل القواعد. "
                "إذا كان السبب تكرار الموضوع، اختر واقعة مختلفة تمامًا."
            )
            if any(marker in last_error.lower() for marker in ("مكرر", "duplicate", "similar")):
                round_message += "\n[إعادة اختيار إلزامية] اختر واقعة جديدة ولا تعِد صياغة الموضوع المرفوض."
            if last_error:
                round_message += f"\nسبب الرفض السابق: {last_error[:500]}"
        if providers and all(provider.dead for provider in providers):
            break
        try:
            episode, label = generate_valid_episode(
                system_prompt, round_message, budget, providers, _validate)
            print(f"✅ الحلقة اتولّدت عبر {label} (النمط: {story_type})")
            return episode
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            print(f"⚠️ الجولة {rnd}/{rounds} فشلت: {last_error}")
            if rnd < rounds:
                time.sleep(cooldown)
    raise RuntimeError(last_error)
