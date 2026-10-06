"""Generate and validate one horror episode using the shared LLM gateway."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from arabic_guard import format_feedback, validate_narration
try:
    from scripts.horror_verification import validate_episode as validate_horror_episode
except ModuleNotFoundError:
    from horror_verification import validate_episode as validate_horror_episode
from llm_gateway import (
    EPISODE_SCHEMA,
    OutputError,
    WORDS_MAX,
    WORDS_MIN,
    generate_episode as gateway_generate_episode,
    make_validator,
)
try:
    from scripts.topic_history import DuplicateTopicError, TopicHistory, clean_text
except ModuleNotFoundError:
    from topic_history import DuplicateTopicError, TopicHistory, clean_text

SCRIPT_DIR = Path(__file__).parent
ROOT = SCRIPT_DIR.parent
PROMPT_PATH = ROOT / "prompts" / "horror_system_prompt.md"
OUTPUT_PATH = ROOT / "state" / "current_episode.json"
HISTORY_PATH = ROOT / "state" / "used_clips.json"
TOPIC_HISTORY_PATH = ROOT / "state" / "topic_history.json"
TOPIC_PERFORMANCE_FILE = ROOT / os.getenv("TOPIC_PERFORMANCE_FILE", "state/topic_performance.json")
HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT", "8"))
REGION_HISTORY_LIMIT = int(os.getenv("REGION_HISTORY_LIMIT", "6"))

CONTENT_RED_FLAGS = ("السيلينس", "الشهرات الجوية", "المحتلة بالدقيق", "البركان الثلجي")


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def performance_hint() -> str:
    """Read optional view/retention aggregates; never make generation depend on them."""
    if not TOPIC_PERFORMANCE_FILE.exists():
        return "لا توجد بيانات مشاهدة موثوقة؛ اعتمد على هوية قناة الرعب والتنوع."
    try:
        data = json.loads(TOPIC_PERFORMANCE_FILE.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else data.get("topics", [])
        ranked = []
        for row in rows:
            if isinstance(row, dict) and (row.get("title") or row.get("topic")):
                views = float(row.get("views") or row.get("view_count") or 0)
                retention = float(row.get("retention") or row.get("watch_percentage") or 0)
                ranked.append((views * (1 + retention / 100), row.get("title") or row.get("topic")))
        if ranked:
            return "أنماط الأعلى أداءً (استلهمها دون نسخ): " + json.dumps([x[1] for x in sorted(ranked, reverse=True)[:5]], ensure_ascii=False)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return "لا توجد بيانات مشاهدة موثوقة؛ اعتمد على هوية قناة الرعب والتنوع."


def _history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data.get("history", []) if isinstance(data, dict) else []


def load_used_history(limit: int = HISTORY_LIMIT) -> list[str]:
    local = [x.get("title", "") for x in _history() if x.get("title")]
    permanent = [entry.get("title", "") for entry in TopicHistory(TOPIC_HISTORY_PATH).entries]
    values = list(dict.fromkeys(clean_text(value, 180) for value in local + permanent if value))
    return values[-max(limit, 100):]


def load_used_regions(limit: int = REGION_HISTORY_LIMIT) -> list[str]:
    return [x.get("region", "") for x in _history() if x.get("region")][-limit:]


def load_used_hooks(limit: int = HISTORY_LIMIT) -> list[str]:
    local = [x.get("hook", "") for x in _history() if x.get("hook")]
    permanent = [entry.get("hook", "") for entry in TopicHistory(TOPIC_HISTORY_PATH).entries]
    values = list(dict.fromkeys(clean_text(value, 240) for value in local + permanent if value))
    return values[-max(limit, 100):]


def find_content_red_flag(text: str) -> str | None:
    plain = re.sub(r"[\u064B-\u065F\u0670]", "", text or "")
    return next((flag for flag in CONTENT_RED_FLAGS if flag in plain), None)


def looks_truncated(narration: str) -> bool:
    stripped = narration.strip()
    return not stripped or not stripped.endswith((".", "!", "؟", "?", "…", '"', "”", "»"))


def looks_open_ended(narration: str) -> bool:
    """Catch a narration whose final sentence is only an unanswered question."""
    last = re.split(r"(?<=[.!؟?…])\s+", narration.strip())[-1].strip()
    return last.endswith(("؟", "?")) and len(last.split()) >= 4


def to_gemini_schema(schema: dict) -> dict:
    """Convert the local JSON schema to the Gemini SDK's schema format."""
    result = {"type": schema["type"].upper()}
    if "enum" in schema:
        result["enum"] = schema["enum"]
    for bound in ("minimum", "maximum", "minItems", "maxItems"):
        if bound in schema:
            result[bound] = schema[bound]
    if result["type"] == "OBJECT":
        result["properties"] = {
            key: to_gemini_schema(value)
            for key, value in schema.get("properties", {}).items()
        }
        if schema.get("required"):
            result["required"] = schema["required"]
    elif result["type"] == "ARRAY":
        result["items"] = to_gemini_schema(schema["items"])
    return result


def build_user_message(recent_titles: list[str], recent_regions: list[str], recent_hooks: list[str]) -> str:
    message = (
        "اكتب حلقة رعب حقيقي/تحقيق مرعب جديدة تمامًا وأخرج JSON واحدًا فقط.\n\n"
        "التزم ببرومبت Dark Documentary وبوابات التحقق والمطابقة البصرية. لا تكتب معلومات عامة أو خيالًا سطحيًا أو jumpscare رخيصًا.\n"
        f"طول narration المطلوب من {WORDS_MIN} إلى {WORDS_MAX} كلمة.\n"
        "قيمة tension في كل صف عدد صحيح من 1 إلى 5، وليست من 1 إلى 10.\n"
        "production_table يجب أن يحتوي على سبعة صفوف مشاهد على الأقل، تغطي السرد كاملًا.\n"
        "قبل السرد أنشئ verification_report وproduction_table، وصنف القصة بصدق إلى true_case أو unexplained_event أو urban_legend.\n"
        "لا تختلق تفاصيل أو حوارات أو رسائل أو أدلة. كل لقطة يجب أن ترتبط بجملة ومكان ومصدر ونوع أصالة واضح.\n"
        "ابن التوتر تدريجيًا من الصمت والغموض والتفاصيل، واجعل final_checks كلها PASS. القوائم التالية بيانات لتجنب التكرار فقط."
    )
    if recent_titles:
        message += "\n\nالعناوين السابقة (JSON بيانات):\n" + json.dumps(recent_titles[-100:], ensure_ascii=False)
    if recent_hooks:
        message += "\n\nالهوكات/القضايا السابقة (JSON بيانات):\n" + json.dumps(recent_hooks[-100:], ensure_ascii=False)
    if recent_regions:
        message += "\n\nالمناطق السابقة (JSON بيانات):\n" + json.dumps(recent_regions[-20:], ensure_ascii=False)
    return message


def validate_episode(episode: dict) -> None:
    """Project-specific checks layered on top of the gateway's structural checks."""
    narration = str(episode.get("narration", "")).strip()
    arabic_issues = validate_narration(narration)
    foreign_issues = [issue for issue in arabic_issues if issue.kind == "foreign_script"]
    # LLMs sometimes leak an English place/model token into an otherwise
    # valid Arabic narration. Remove Latin tokens and continue; the separate
    # Arabic-density guard still rejects genuinely non-Arabic scripts.
    has_foreign_noise = bool(foreign_issues)
    blocking_issues = [
        issue for issue in arabic_issues
        if issue.kind not in {"digit"}
        and issue.kind != "foreign_script"
    ]
    digit_issues = [issue for issue in arabic_issues if issue.kind == "digit"]
    foreign_noise = foreign_issues
    if digit_issues:
        print(f"⚠️ أرقام داخل narration ({len(digit_issues)})؛ سيتم نطقها كما هي")
    if foreign_noise:
        narration = re.sub(r"(?<!\w)[A-Za-z][A-Za-z'-]*(?!\w)", "", narration)
        episode["narration"] = re.sub(r"\s{2,}", " ", narration).strip()
        print(f"⚠️ رموز لاتينية قصيرة داخل narration ({len(foreign_noise)})؛ تم حذفها")
    if blocking_issues:
        raise OutputError(format_feedback(blocking_issues))
    red_flag = find_content_red_flag(narration)
    if red_flag:
        raise OutputError(f"النص يحتوي مصطلحًا مرفوضًا: {red_flag}")
    if not str(episode.get("hook", "")).strip():
        raise OutputError("حقل hook فاضي")
    if not episode.get("visual_keywords"):
        raise OutputError("حقل visual_keywords فاضي")
    if looks_truncated(narration):
        raise OutputError("نص narration شكله متقطوع", truncated=True)
    if looks_open_ended(narration):
        raise OutputError("النهاية سؤال مفتوح بلا كشف أو خاتمة")


def generate_episode() -> dict:
    system_prompt = load_system_prompt()
    topic_history = TopicHistory(TOPIC_HISTORY_PATH)
    user_message = build_user_message(
        load_used_history(), load_used_regions(), load_used_hooks()
    )
    if not any(os.getenv(key, "").strip() for key in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY")):
        sys.exit("خطأ: أضف GEMINI_API_KEY أو GROQ_API_KEY أو OPENROUTER_API_KEY إلى GitHub Secrets")

    validator = make_validator(
        find_content_red_flag=find_content_red_flag,
        looks_truncated=looks_truncated,
    )

    def combined_validator(episode: dict) -> None:
        validator(episode)
        validate_episode(episode)
        try:
            validate_horror_episode(episode)
        except ValueError as exc:
            if os.getenv("QUALITY_GATES_BLOCKING", "true").lower() == "true":
                raise
            print(f"WARNING: horror editorial review: {exc}")
        try:
            topic_history.check_unique(episode)
        except DuplicateTopicError as exc:
            raise OutputError(str(exc)) from exc

    budget = int(os.getenv("LLM_INITIAL_BUDGET", "6000"))
    print("🎬 بوابة التوليد: Gemini بالتتابع ثم Groq ثم OpenRouter")
    try:
        episode = gateway_generate_episode(
            system_prompt=system_prompt,
            user_message=user_message,
            budget=budget,
            validate=combined_validator,
            to_gemini_schema=to_gemini_schema,
            used_hooks=load_used_hooks(),
            recent_regions=load_used_regions(),
            rounds=int(os.getenv("LLM_ROUNDS", "3")),
            cooldown=int(os.getenv("LLM_ROUND_COOLDOWN", "30")),
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        raise SystemExit(f"❌ فشل توليد حلقة سليمة: {exc}") from exc
    return episode


if __name__ == "__main__":
    episode = generate_episode()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ اتكتبت الحلقة: {episode['title']}")
    print(f"   النوع: {episode.get('story_type', 'غير محدد')}")
    print(f"   المنطقة: {episode.get('region', 'غير محدد')}")
    print(f"   الهوك: {episode.get('hook', '')[:80]}")
