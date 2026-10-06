"""توليد صوت الحلقة كاملة وترجمة ASS متزامنة، بلا موسيقى خلفية.

هذا الملف لا يقسم القصة إلى أجزاء. ينتج:
- downloaded_clips/narration_voice.mp3
- downloaded_clips/narration.mp3
- downloaded_clips/narration.ass
ويحدّث current_episode.json بالمسارات الجديدة.

مزامنة الترجمة: بدل الاعتماد فقط على توقيت "WordBoundary" الذي يرجعه
edge-tts ذاتيًا لكل جملة، ثم تجميعه يدويًا مع مدد السكتات بين الجمل (طريقة
عرضة للانحراف التراكمي—أي خطأ بسيط في تقدير مدة جملة أو سكتة يتضخم مع كل
جملة تالية)، يُشغَّل الآن Whisper (faster-whisper) على الصوت النهائي
الكامل بعد تجميعه فعليًا، ويُطابَق ناتجه (توقيت حقيقي مبني على الموجة
الصوتية الفعلية) مع كلمات القصة نفسها. هذا يزيل مصدر عدم اليقين بالكامل:
Whisper "يسمع" الصوت الحقيقي المنشور فعلاً، بما فيه السكتات، فلا حاجة
لحساب تراكمي يدوي لمواضعها. توقيت edge-tts الذاتي (القديم) يبقى فقط
كخطة احتياطية إذا تعذّر تشغيل Whisper لأي سبب.
"""

from __future__ import annotations

import asyncio
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Direct execution (python scripts/generate_voice.py) must see the repository root.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import edge_tts
from arabic_speech_core.ass_text import render_arabic_caption, caption_word_groups
try:
    from .voice_profiles import resolve_reference_profile
except ImportError:  # direct `python scripts/generate_voice.py`
    from voice_profiles import resolve_reference_profile

SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
STATE_DIR = ROOT_DIR / "state"
CLIPS_DIR = ROOT_DIR / "downloaded_clips"
ASSETS_DIR = ROOT_DIR / "assets"
EPISODE_PATH = STATE_DIR / "current_episode.json"

VOICE = os.getenv("EDGE_TTS_VOICE", "").strip()
VOICE_CANDIDATES = list(dict.fromkeys(
    item.strip() for item in os.getenv(
        "EDGE_TTS_VOICES",
        "ar-EG-ShakirNeural,ar-SA-HamedNeural",
    ).split(",") if item.strip()
))
TTS_ENGINE = os.getenv("TTS_ENGINE", "silma").strip().lower()
SILMA_REFERENCE_WAV = Path(os.getenv("SILMA_REFERENCE_WAV", "assets/voice_reference_synthetic.wav"))
SILMA_REFERENCE_PROFILE = os.getenv("SILMA_REFERENCE_PROFILE", "auto").strip()
SILMA_VOICE_PROFILES_FILE = Path(os.getenv("SILMA_VOICE_PROFILES_FILE", "assets/voices/voice_profiles.json"))
SILMA_REFERENCE_TEXT = os.getenv(
    "SILMA_REFERENCE_TEXT",
    "في عام 1943، بدأت خطة خداع عسكرية بوثيقة صغيرة، لكنها غيرت مسار معركة كاملة.",
).strip()
SILMA_SPEED = float(os.getenv("SILMA_SPEED", "1.15"))
SILMA_GUARD_ENABLED = os.getenv("SILMA_GUARD_ENABLED", "true").lower() == "true"
SILMA_GUARD_MIN_MATCH_WORDS = int(os.getenv("SILMA_GUARD_MIN_MATCH_WORDS", "2"))
RATE = os.getenv("EDGE_TTS_RATE", "-8%")
PITCH = os.getenv("EDGE_TTS_PITCH", "-5Hz")
VOLUME = "+0%"
WORDS_PER_CAPTION_CHUNK = int(os.getenv("WORDS_PER_CAPTION_CHUNK", "6"))
VIDEO_W = 1920
VIDEO_H = 1080
# The horizontal 16:9 master keeps narration captions bottom-centered.  The
# same master is the source for reels, so leave a safe lower margin for app UI.
FULL_CAPTION_BOTTOM_MARGIN = 70

# نموذج Whisper المستخدم لمحاذاة الترجمة مع الصوت الفعلي (انظر
# align_words_with_whisper أدناه). "base" اختيار متوازن بين السرعة
# والدقة على معالج عادي؛ يمكن رفعه لـ "small" لدقة أعلى مقابل وقت أطول
# عبر متغير البيئة WHISPER_MODEL.
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
ASR_MIN_MATCH_RATIO = float(os.getenv("ASR_MIN_MATCH_RATIO", "0.82"))

VOICE_AUDIO = CLIPS_DIR / "narration_voice.mp3"
FINAL_AUDIO = CLIPS_DIR / "narration.mp3"
SUBTITLES = CLIPS_DIR / "narration.ass"

PAUSE_AFTER_ELLIPSIS = 1.3
PAUSE_AFTER_QUESTION_EXCLAIM = 0.75
PAUSE_AFTER_PERIOD = 0.45
DEFAULT_PAUSE = 0.5

ARABIC_DIACRITICS_PATTERN = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u08D3-\u08E1\u08E3-\u08FF]")
_WORD_TOKEN_PATTERN = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)
# علامات تُحذف من النص المرئي فقط حتى يبدو طبيعيًا وغير آلي. نص الراوي
# الأصلي يظل محتفظًا بها لأن edge-tts يستخدمها لصناعة الوقفات الصحيحة.
DISPLAY_PUNCTUATION = str.maketrans(".,،؛:!?؟…-—_()[]{}\"«»/\\", " " * 23)

# قاموس تشكيل انتقائي: كل كلمة هنا لها أكثر من قراءة ممكنة بلا تشكيل، لكن
# قراءة واحدة منها فقط هي المسيطرة فعليًا في سياق سرد قصص الرعب — تمامًا
# مثل مشكلة "زر" (زِرّ الضغط مقابل فعل الزيارة) في مشروع آخر: كلمة بلا
# تشكيل ممكن يقرأها المحرك بمعنى مختلف تمامًا عن المقصود. أي كلمة يُضاف
# تشكيلها هنا يجب أن يكون لها قراءة واحدة غالبة بوضوح في هذا السياق؛
# كلمات فيها احتمالان متقاربان في الاستخدام الفعلي (مثل "قفل" بين "القُفْل"
# كاسم و"قَفَلَ" كفعل، وكلاهما شائع بنفس القدر في السرد) استُبعدت عمدًا
# حتى لا تفرض قراءة قد تكون خاطئة في نصف الحالات.
HARD_WORDS_DIACRITICS = {
    "عدة": "عِدّة", "قلبه": "قَلْبه", "لعنة": "لَعنة", "مسكون": "مَسكون",
    "جثة": "جُثّة", "همس": "هَمْس", "أشباح": "أَشباح", "ظل": "ظِلّ",
    "رعب": "رُعب", "صرخة": "صَرخة",
    "خطى": "خُطى", "شبح": "شَبَح", "صراخ": "صُراخ", "دفن": "دَفَن",
}
MIN_MIN_PRONUNCIATION = "مِين مِين"


def normalize_min_min_pronunciation(text: str) -> str:
    """Canonicalize all common diacritic variants of Min Min for TTS."""
    variants = ("مين مين", "مِين مِين", "مِينَ مِين", "مِين مِينَ", "مِينَ مِينَ")
    for variant in variants:
        text = text.replace(variant, MIN_MIN_PRONUNCIATION)
    return text


def select_edge_voice(episode: dict) -> str:
    """Choose a different suitable Edge voice for each episode.

    An explicit EDGE_TTS_VOICE always wins. Otherwise female-led stories prefer
    the female Arabic voice; other stories rotate deterministically by title and
    region while avoiding the most recently used voice when possible.
    """
    global VOICE
    if VOICE:
        return VOICE
    if not VOICE_CANDIDATES:
        raise RuntimeError("EDGE_TTS_VOICES لا يحتوي على أي صوت")
    searchable = f"{episode.get('title', '')} {episode.get('narration', '')}"
    female_story = bool(re.search(r"(امرأة|فتاة|طفلة|ممرضة|سيدة|أم|زوجة)", searchable))
    preferred = [v for v in VOICE_CANDIDATES if "Zariyah" in v] if female_story else [
        v for v in VOICE_CANDIDATES if "Zariyah" not in v
    ]
    pool = preferred or VOICE_CANDIDATES
    history_path = STATE_DIR / "used_clips.json"
    recent = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
            recent = [h.get("voice_profile") for h in history.get("history", [])[-3:]]
        except (OSError, json.JSONDecodeError):
            recent = []
    available = [v for v in pool if v not in recent] or pool
    seed = f"{episode.get('title', '')}|{episode.get('region', '')}".encode()
    VOICE = available[int.from_bytes(hashlib.sha256(seed).digest()[:4], "big") % len(available)]
    return VOICE


def save_voice_to_history(episode: dict, selected_voice: str) -> None:
    history_path = STATE_DIR / "used_clips.json"
    if not history_path.exists():
        return
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
        for item in reversed(data.get("history", [])):
            if item.get("title") == episode.get("title"):
                item["voice_profile"] = selected_voice
                break
        history_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, json.JSONDecodeError):
        print("⚠️ تعذر حفظ اختيار الصوت في سجل الحلقات")


def configure_silma_voice_profile() -> str:
    """Resolve the selected horror-appropriate reference WAV and transcript."""
    global SILMA_REFERENCE_WAV, SILMA_REFERENCE_TEXT
    selected, label, wav, transcript = resolve_reference_profile(
        SILMA_REFERENCE_PROFILE,
        SILMA_VOICE_PROFILES_FILE,
        ROOT_DIR,
    )
    SILMA_REFERENCE_WAV = wav
    SILMA_REFERENCE_TEXT = transcript
    print(f"🎙️ ملف صوت الرعب المختار: {label} ({selected})")
    return selected


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit("❌ فشل الأمر:\n" + " ".join(command) + "\n\n" + result.stderr)
    return result


def strip_diacritics(text: str) -> str:
    return ARABIC_DIACRITICS_PATTERN.sub("", text)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", strip_diacritics(text)).strip()


def apply_phonetic_hints(text: str, hints: list[dict]) -> str:
    """يستبدل كل مدخل من phonetic_hints (كلمة أو عبارة أجنبية كما وردت
    بالضبط في narration) بنسختها المشكّلة، قبل أي تشكيل عام. بترتب
    المدخلات من الأطول للأقصر أولاً عشان عبارة من كذا كلمة (زي اسم مدينة
    مركّب) تتستبدل كوحدة واحدة قبل ما أي كلمة مفردة جواها تتستبدل غلط لو
    ظهرت في مدخل تاني. المفروض phonetic تكون نفس الكلمة بالحروف الأساسية
    بالظبط مع إضافة تشكيل بس (شوف horror_system_prompt.md)، فـ
    strip_diacritics() بترجّعها زي الأصل تمامًا في الترجمة."""
    text = normalize_min_min_pronunciation(text)
    for hint in sorted(hints, key=lambda h: len(str(h.get("word", ""))), reverse=True):
        word = str(hint.get("word", "")).strip()
        phonetic = str(hint.get("phonetic", "")).strip()
        if word and phonetic:
            text = text.replace(word, phonetic)
    return text


def apply_light_diacritics(text: str) -> str:
    def replace(match: re.Match) -> str:
        word = match.group(0)
        return HARD_WORDS_DIACRITICS.get(word, word)
    return _WORD_TOKEN_PATTERN.sub(replace, text)


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!؟…])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def pause_duration_for(sentence: str) -> float:
    stripped = sentence.strip()
    if stripped.endswith("…") or stripped.endswith("..."):
        return PAUSE_AFTER_ELLIPSIS
    if stripped.endswith("؟") or stripped.endswith("!"):
        return PAUSE_AFTER_QUESTION_EXCLAIM
    if stripped.endswith("."):
        return PAUSE_AFTER_PERIOD
    return DEFAULT_PAUSE


def probe_duration(path: Path) -> float:
    result = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ])
    return float(result.stdout.strip())


def build_silence_clip(duration: float, path: Path) -> None:
    run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", f"{duration:.3f}", "-c:a", "libmp3lame", "-b:a", "192k", str(path),
    ])


def _norm_arabic_words(text: str) -> list[str]:
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text or "")
    text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text, flags=re.UNICODE)
    return [w for w in text.lower().split() if w]



_TRANSCRIPT_CACHE: dict[tuple, list] = {}

def _cached_whisper_segments(audio_path: Path) -> list:
    """Reuse one word-timed transcript; invalidate it when audio is rewritten."""
    from faster_whisper import WhisperModel
    stat = audio_path.stat()
    key = (str(audio_path.resolve()), stat.st_size, stat.st_mtime_ns, WHISPER_MODEL_SIZE)
    if key not in _TRANSCRIPT_CACHE:
        model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
        result = model.transcribe(str(audio_path), language="ar",
                                  word_timestamps=True, vad_filter=False)
        segments = result[0] if isinstance(result, (tuple, list)) else result
        _TRANSCRIPT_CACHE.clear()
        _TRANSCRIPT_CACHE[key] = list(segments)
    return _TRANSCRIPT_CACHE[key]

def _transcribe_arabic_words(audio_path: Path) -> list[str]:
    """Return normalized Arabic words across faster-whisper API variants."""
    segments = _cached_whisper_segments(audio_path)
    return _norm_arabic_words(" ".join(getattr(seg, "text", "") or "" for seg in segments))


def assert_audio_matches_script(audio_path: Path, script_text: str) -> float:
    """Fail closed when ASR cannot hear the Arabic script that was generated."""
    expected = _norm_arabic_words(script_text)
    heard = _transcribe_arabic_words(audio_path)
    if not expected or not heard:
        raise RuntimeError("بوابة ASR لم تحصل على كلمات عربية من النص أو الصوت")
    matcher = difflib.SequenceMatcher(None, expected, heard, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    ratio = matched / len(expected)
    print(f"🎧 بوابة ASR العربية: {matched}/{len(expected)} كلمة مطابقة ({ratio:.1%})")
    if ratio < ASR_MIN_MATCH_RATIO:
        raise RuntimeError(
            f"تطابق النطق العربي منخفض: {ratio:.1%}، المطلوب {ASR_MIN_MATCH_RATIO:.1%}"
        )
    return ratio


def detect_silma_reference_leak(audio_path: Path) -> str | None:
    """Transcribe audio and reject a contiguous phrase copied from SILMA reference."""
    if not SILMA_GUARD_ENABLED or not SILMA_REFERENCE_TEXT:
        return None
    from faster_whisper import WhisperModel
    model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(audio_path), language="ar", word_timestamps=False, vad_filter=False)
    heard = _norm_arabic_words(" ".join(seg.text or "" for seg in segments))
    ref = _norm_arabic_words(SILMA_REFERENCE_TEXT)
    minimum = max(2, min(SILMA_GUARD_MIN_MATCH_WORDS, len(ref)))
    for size in range(len(ref), minimum - 1, -1):
        phrase = ref[-size:]
        for i in range(len(heard) - size + 1):
            if heard[i:i + size] == phrase:
                return " ".join(phrase)
    return None


def synthesize_sentences_silma(sentences: list[str]) -> list[dict]:
    reference = SILMA_REFERENCE_WAV if SILMA_REFERENCE_WAV.is_absolute() else ROOT_DIR / SILMA_REFERENCE_WAV
    if not reference.exists():
        raise RuntimeError(f"SILMA reference is missing: {reference}")
    from silma_tts.api import SilmaTTS
    print(f"🟣 Loading SILMA TTS v1 (speed={SILMA_SPEED})...")
    silma = SilmaTTS()
    segments = []
    for index, sentence in enumerate(sentences):
        sentence = re.sub(r"\s+", " ", sentence).strip()
        wav_path = CLIPS_DIR / f"_seg_full_{index:03d}.wav"
        silma.infer(ref_file=str(reference), ref_text=SILMA_REFERENCE_TEXT or None,
                    gen_text=sentence, file_wave=str(wav_path), seed=None, speed=SILMA_SPEED)
        duration = probe_duration(wav_path)
        segments.append({"path": wav_path, "duration": duration, "events": None,
                         "sentence": sentence, "is_silence": False})
        if index < len(sentences) - 1:
            pause = pause_duration_for(sentence)
            pause_path = CLIPS_DIR / f"_pause_full_{index:03d}.mp3"
            build_silence_clip(pause, pause_path)
            segments.append({"path": pause_path, "duration": pause, "events": None,
                             "sentence": None, "is_silence": True})
    return segments


async def synthesize_sentences(sentences: list[str], engine_override: str | None = None) -> list[dict]:
    engine = engine_override or TTS_ENGINE
    if engine == "silma":
        try:
            return synthesize_sentences_silma(sentences)
        except Exception as exc:
            if engine_override is None and os.getenv("SILMA_FALLBACK_TO_EDGE", "true").lower() == "true":
                print(f"⚠️ تعذر SILMA ({exc}) — الرجوع إلى Edge TTS.")
                return await synthesize_sentences(sentences, "edge")
            raise
    segments = []
    for index, sentence in enumerate(sentences):
        seg_path = CLIPS_DIR / f"_seg_full_{index:03d}.mp3"
        events = []
        communicate = edge_tts.Communicate(sentence, VOICE, rate=RATE, pitch=PITCH, volume=VOLUME)
        with seg_path.open("wb") as audio_file:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    events.append(chunk)
        duration = probe_duration(seg_path)
        segments.append({"path": seg_path, "duration": duration, "events": events, "sentence": sentence, "is_silence": False})
        if index < len(sentences) - 1:
            pause = pause_duration_for(sentence)
            pause_path = CLIPS_DIR / f"_pause_full_{index:03d}.mp3"
            build_silence_clip(pause, pause_path)
            segments.append({"path": pause_path, "duration": pause, "events": None, "sentence": None, "is_silence": True})
    return segments


def ass_time(seconds: float) -> str:
    centiseconds = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def two_lines(words: list[str]) -> str:
    return render_arabic_caption(words)


def build_ass_header() -> str:
    style = f"Style: Caption,Noto Sans Arabic,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,3,0,2,70,70,{FULL_CAPTION_BOTTOM_MARGIN},1"
    return (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {VIDEO_W}\nPlayResY: {VIDEO_H}\n"
        "WrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
        "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        + style + "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


# ---------------------------------------------------------------------------
# مزامنة الترجمة: محاذاة حقيقية بالصوت الفعلي (Whisper) — مع خطة احتياطية
# ---------------------------------------------------------------------------

def _build_word_events_from_edge_tts(segments: list[dict]) -> list[dict]:
    """توقيت احتياطي فقط: يعتمد على "WordBoundary" الذي يرجعه edge-tts
    لكل جملة على حدة، مجمّعًا يدويًا مع مدد السكتات المُدرَجة بينها. لا
    يُستخدم إلا إذا تعذّرت محاذاة Whisper (انظر align_words_with_whisper)
    — توقيت edge-tts الذاتي للعربية غير موثوق بما يكفي ليكون المصدر
    الأساسي، خصوصًا مع تراكم خطأ كل جملة على التي بعدها."""
    events: list[dict] = []
    cumulative_seconds = 0.0
    for segment in segments:
        if segment["is_silence"]:
            cumulative_seconds += segment["duration"]
            continue
        if segment["events"]:
            for event in segment["events"]:
                events.append({
                    "text": strip_diacritics(event["text"]),
                    "offset": cumulative_seconds + event["offset"] / 10_000_000,
                    "duration": event["duration"] / 10_000_000,
                })
        else:
            words = re.findall(r"\S+", segment["sentence"] or "")
            per_word = segment["duration"] / max(len(words), 1)
            for word_index, word in enumerate(words):
                events.append({
                    "text": strip_diacritics(word),
                    "offset": cumulative_seconds + word_index * per_word,
                    "duration": per_word,
                })
        cumulative_seconds += segment["duration"]
    return events


def align_words_with_whisper(audio_path: Path, script_words: list[str]) -> list[dict]:
    """يحاذي script_words مع الصوت الفعلي المُنتَج باستخدام faster-whisper،
    بدل الوثوق بتوقيت edge-tts الذاتي. النص المعروض/المستخدم دائمًا هو
    script_words نفسها؛ ناتج Whisper (بلا تشكيل، وقد يحوي أخطاء تعرّف
    بسيطة) يُستخدم فقط لاستخراج التوقيت الحقيقي، عبر مطابقة الفروقات
    (difflib) بين الكلمتين بعد تطبيع كل منهما. أي كلمة من السكريبت لم
    يتعرّف عليها Whisper بثقة تأخذ توقيتًا تقريبيًا من أقرب كلمتين
    متطابقتين قبلها وبعدها، بدل أن تُفقد."""
    segments = _cached_whisper_segments(audio_path)

    whisper_words: list[tuple[str, float, float]] = []
    for segment in segments:
        for w in (segment.words or []):
            text = (w.word or "").strip()
            if text:
                whisper_words.append((text, float(w.start), float(w.end)))
    if not whisper_words:
        raise RuntimeError("Whisper لم يرجع أي توقيت على مستوى الكلمة")

    def _norm(w: str) -> str:
        return strip_diacritics(w).translate(DISPLAY_PUNCTUATION).strip().lower()

    script_norm = [_norm(w) for w in script_words]
    whisper_norm = [_norm(w) for w, _, _ in whisper_words]

    matcher = difflib.SequenceMatcher(None, script_norm, whisper_norm, autojunk=False)
    timings: list[dict | None] = [None] * len(script_words)
    for block in matcher.get_matching_blocks():
        i1, i2 = block.a, block.a + block.size
        j1 = block.b
        for k in range(block.size):
            if i1 + k >= len(script_words) or j1 + k >= len(whisper_words):
                continue
            _, start, end = whisper_words[j1 + k]
            timings[i1 + k] = {
                "text": script_words[i1 + k],
                "offset": start,
                "duration": max(end - start, 0.05),
            }

    known_indices = [i for i, t in enumerate(timings) if t is not None]
    if not known_indices or len(known_indices) < len(script_words) * 0.5:
        raise RuntimeError(
            f"تطابق ضعيف جدًا: {len(known_indices)}/{len(script_words)} كلمة فقط"
        )

    for i in range(len(timings)):
        if timings[i] is not None:
            continue
        prev_i = max((k for k in known_indices if k < i), default=None)
        next_i = min((k for k in known_indices if k > i), default=None)
        if prev_i is None:
            base = timings[next_i]
            # وزّع الكلمات غير المتعرّف عليها من الصفر إلى أول كلمة مسموعة؛
            # لا تعطها نفس offset حتى لا تبقى أول جملة ثابتة.
            step = max(base["offset"] / (next_i + 1), 0.08)
            offset = step * i
        elif next_i is None:
            base = timings[prev_i]
            offset = base["offset"] + base["duration"] * (i - prev_i)
        else:
            prev_end = timings[prev_i]["offset"] + timings[prev_i]["duration"]
            next_start = timings[next_i]["offset"]
            span = max(next_start - prev_end, 0.05)
            offset = prev_end + span * (i - prev_i) / (next_i - prev_i)
        timings[i] = {"text": script_words[i], "offset": offset, "duration": 0.3}

    previous_end = 0.0
    for timing in timings:
        timing["offset"] = max(float(timing["offset"]), previous_end)
        timing["duration"] = max(float(timing["duration"]), 0.06)
        previous_end = timing["offset"] + timing["duration"]
    print(
        f"🎯 محاذاة Whisper: {len(known_indices)}/{len(script_words)} كلمة مطابقة مباشرة، "
        f"{len(script_words) - len(known_indices)} بالتقريب"
    )
    return timings


def synthesize_voice(voice_text: str) -> None:
    sentences = split_sentences(voice_text)
    if not sentences:
        sys.exit("❌ النص فارغ ولا يمكن إنشاء صوت.")
    segments = asyncio.run(synthesize_sentences(sentences))
    inputs: list[str] = []
    for segment in segments:
        inputs += ["-i", str(segment["path"])]
    concat_filter = "".join(f"[{i}:a]" for i in range(len(segments))) + f"concat=n={len(segments)}:v=0:a=1[aout]"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", concat_filter, "-map", "[aout]", "-c:a", "libmp3lame", "-b:a", "192k", str(VOICE_AUDIO)])
    if TTS_ENGINE == "silma":
        try:
            leak = detect_silma_reference_leak(VOICE_AUDIO)
        except Exception as exc:  # Whisper unavailable/download failure: fail safe to Edge.
            print(f"⚠️ تعذر فحص صوت SILMA عبر Whisper ({exc}) — إعادة التوليد بـEdge TTS.")
            leak = "whisper_guard_error"
        if leak:
            print(f"⚠️ تسرّب/خلل في صوت SILMA ({leak}) — إعادة التوليد بـEdge TTS.")
            for segment in segments:
                Path(segment["path"]).unlink(missing_ok=True)
            segments = asyncio.run(synthesize_sentences(sentences, "edge"))
            inputs = []
            for segment in segments:
                inputs += ["-i", str(segment["path"])]
            concat_filter = "".join(f"[{i}:a]" for i in range(len(segments))) + f"concat=n={len(segments)}:v=0:a=1[aout]"
            run(["ffmpeg", "-y", *inputs, "-filter_complex", concat_filter, "-map", "[aout]", "-c:a", "libmp3lame", "-b:a", "192k", str(VOICE_AUDIO)])

    # نفس ترتيب/شكل الكلمات المعروضة كما كانت قبل التعديل (بلا تشكيل،
    # وبعلامات الترقيم لا تزال ملتصقة — two_lines() تحذفها وقت العرض).
    display_words = strip_diacritics(voice_text).split()

    assert_audio_matches_script(VOICE_AUDIO, voice_text)
    try:
        all_word_events = align_words_with_whisper(VOICE_AUDIO, display_words)
    except Exception as exc:  # noqa: BLE001
        # Whisper can under-recognize Arabic even when the ASR gate confirms
        # the audio is valid. Keep the run alive with Edge WordBoundary timing
        # instead of dropping an otherwise publishable episode.
        print(f"⚠️ تعذرت محاذاة Whisper ({exc}) — استخدام توقيت Edge الاحتياطي.")
        all_word_events = _build_word_events_from_edge_tts(segments)
        if not all_word_events:
            duration = probe_duration(VOICE_AUDIO)
            per_word = duration / max(len(display_words), 1)
            all_word_events = [
                {"text": word, "offset": index * per_word, "duration": per_word}
                for index, word in enumerate(display_words)
            ]

    if not all_word_events:
        sys.exit("❌ تعذر إنشاء توقيت الترجمة.")
    dialogue_lines = []
    for group in caption_word_groups(all_word_events, WORDS_PER_CAPTION_CHUNK):
        start = group[0]["offset"]
        end = group[-1]["offset"] + group[-1]["duration"]
        dialogue_lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(max(end, start + 0.25))},Caption,,0,0,0,,{two_lines([e['text'] for e in group])}")
    SUBTITLES.write_text(build_ass_header() + "\n".join(dialogue_lines) + "\n", encoding="utf-8")
    for segment in segments:
        Path(segment["path"]).unlink(missing_ok=True)


def prepare_final_audio() -> None:
    """Publish narration as a clean voice-only track; no background music."""
    run([
        "ffmpeg", "-y", "-i", str(VOICE_AUDIO),
        "-c:a", "libmp3lame", "-b:a", "192k", str(FINAL_AUDIO),
    ])

def main() -> None:
    if not EPISODE_PATH.exists():
        sys.exit("❌ state/current_episode.json غير موجود.")
    episode = json.loads(EPISODE_PATH.read_text(encoding="utf-8"))
    selected_voice = (
        configure_silma_voice_profile()
        if TTS_ENGINE == "silma"
        else select_edge_voice(episode)
    )
    narration = normalize_text(str(episode.get("narration", "")))
    if not narration:
        sys.exit("❌ حقل narration غير موجود أو فارغ.")

    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    phonetic_hints = episode.get("phonetic_hints") or []
    voice_text = apply_phonetic_hints(narration, phonetic_hints)
    voice_text = apply_light_diacritics(voice_text)
    synthesize_voice(voice_text)
    prepare_final_audio()

    episode.pop("parts", None)
    episode["narration"] = narration
    episode["voice_profile"] = selected_voice
    episode["voice_audio"] = str(VOICE_AUDIO)
    episode["final_audio"] = str(FINAL_AUDIO)
    episode["subtitles"] = str(SUBTITLES)
    EPISODE_PATH.write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
    save_voice_to_history(episode, selected_voice)
    print(f"✅ صوت كامل: {FINAL_AUDIO}")
    print(f"✅ ترجمة أفقية متزامنة: {SUBTITLES}")
    print(f"✅ تلميحات نطق مُطبّقة: {len(phonetic_hints)}")


if __name__ == "__main__":
    main()
