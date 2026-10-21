"""Generate full Charon narration and measured Arabic captions."""
from __future__ import annotations
import difflib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
ROOT_DIR=Path(__file__).resolve().parents[1]
SCRIPT_DIR=Path(__file__).parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0,str(ROOT_DIR))
from arabic_speech_core.ass_text import render_active_arabic_caption, render_arabic_caption, caption_word_groups, display_word
from scripts.arabic_guard import validate_narration
from voice_provider.client import generate
from scripts.spoken_numbers import spoken_numbers
STATE_DIR = ROOT_DIR / "state"
CLIPS_DIR = ROOT_DIR / "downloaded_clips"
EPISODE_PATH = STATE_DIR / "current_episode.json"
WORDS_PER_CAPTION_CHUNK = int(os.getenv("WORDS_PER_CAPTION_CHUNK", "4"))
VIDEO_W = 1080
VIDEO_H = 1920
FULL_CAPTION_BOTTOM_MARGIN = 70
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
ASR_MIN_MATCH_RATIO = float(os.getenv("ASR_MIN_MATCH_RATIO", "0.82"))
ASR_FALLBACK_MODEL_SIZE = os.getenv("ASR_FALLBACK_MODEL", "small").strip() or "small"
VOICE_AUDIO = CLIPS_DIR / "narration_voice.mp3"
FINAL_AUDIO = CLIPS_DIR / "narration.mp3"
SUBTITLES = CLIPS_DIR / "narration.ass"
ARABIC_DIACRITICS_PATTERN = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u08D3-\u08E1\u08E3-\u08FF]")
DISPLAY_PUNCTUATION = str.maketrans(".,،؛:!?؟…-—_()[]{}\"«»/\\", " " * 23)
MIN_MIN_PRONUNCIATION = "مِين مِين"
_TRANSCRIPT_CACHE: dict[tuple, list] = {}

def normalize_min_min_pronunciation(text: str) -> str:
    """Canonicalize all common diacritic variants of Min Min for TTS."""
    variants = ("مين مين", "مِين مِين", "مِينَ مِين", "مِين مِينَ", "مِينَ مِينَ")
    for variant in variants:
        text = text.replace(variant, MIN_MIN_PRONUNCIATION)
    return text

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

def probe_duration(path: Path) -> float:
    result = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ])
    return float(result.stdout.strip())

def _norm_arabic_words(text: str) -> list[str]:
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text or "")
    text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text, flags=re.UNICODE)
    return [w for w in text.lower().split() if w]

def _cached_whisper_segments(audio_path: Path, model_size: str | None = None) -> list:
    """Reuse one word-timed transcript; invalidate it when audio is rewritten."""
    from faster_whisper import WhisperModel
    model_size = model_size or WHISPER_MODEL_SIZE
    stat = audio_path.stat()
    key = (str(audio_path.resolve()), stat.st_size, stat.st_mtime_ns, model_size)
    if key not in _TRANSCRIPT_CACHE:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        result = model.transcribe(str(audio_path), language="ar",
                                  word_timestamps=True, vad_filter=False)
        segments = result[0] if isinstance(result, (tuple, list)) else result
        _TRANSCRIPT_CACHE[key] = list(segments)
    return _TRANSCRIPT_CACHE[key]

def _transcribe_arabic_words(audio_path: Path, model_size: str | None = None) -> list[str]:
    """Return normalized Arabic words across faster-whisper API variants."""
    segments = _cached_whisper_segments(audio_path, model_size)
    return _norm_arabic_words(" ".join(getattr(seg, "text", "") or "" for seg in segments))

def assert_audio_matches_script(audio_path: Path, script_text: str) -> float:
    """Check with the configured ASR, then a stronger independent model on a miss."""
    expected = _norm_arabic_words(script_text)
    if not expected:
        raise RuntimeError("بوابة ASR لم تحصل على كلمات عربية من النص أو الصوت")
    models = list(dict.fromkeys([WHISPER_MODEL_SIZE, ASR_FALLBACK_MODEL_SIZE]))
    ratios = []
    failures = []
    for model_size in models:
        try:
            heard = _transcribe_arabic_words(audio_path, model_size)
            if not heard:
                failures.append(f"{model_size}: no Arabic words recognized")
                continue
            matcher = difflib.SequenceMatcher(None, expected, heard, autojunk=False)
            matched = sum(block.size for block in matcher.get_matching_blocks())
            ratio = matched / len(expected)
            ratios.append((model_size, matched, ratio))
            print(f"🎧 بوابة ASR العربية ({model_size}): {matched}/{len(expected)} كلمة مطابقة ({ratio:.1%})")
            if ratio >= ASR_MIN_MATCH_RATIO:
                if model_size != WHISPER_MODEL_SIZE:
                    print(f"✓ تأكد تطابق الصوت بالنموذج الاحتياطي {model_size} بعد انخفاض نتيجة النموذج الأساسي.")
                return ratio
        except Exception as exc:
            failures.append(f"{model_size}: {type(exc).__name__}: {str(exc)[:160]}")
    details = "; ".join(f"{name}={ratio:.1%}" for name, _, ratio in ratios)
    if failures:
        details += ("; " if details else "") + "; ".join(failures)
    raise RuntimeError(
        f"تطابق النطق العربي منخفض أو تعذّر التحقق: {details or 'لم يُستخرج نص'}؛ "
        f"المطلوب {ASR_MIN_MATCH_RATIO:.1%}"
    )

def ass_time(seconds: float) -> str:
    centiseconds = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"

def two_lines(words: list[str]) -> str:
    return render_arabic_caption(words)

def build_ass_header() -> str:
    style = f"Style: Caption,Noto Naskh Arabic,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,3,0,2,70,70,{FULL_CAPTION_BOTTOM_MARGIN},1"
    return (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {VIDEO_W}\nPlayResY: {VIDEO_H}\n"
        "WrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
        "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        + style + "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

def align_words_with_whisper(audio_path: Path, script_words: list[str]) -> list[dict]:
    """يحاذي script_words مع الصوت الفعلي المُنتَج باستخدام faster-whisper،
    بدل الوثوق بتوقيت edge-tts الذاتي. النص المعروض/المستخدم دائمًا هو
    script_words نفسها؛ ناتج Whisper (بلا تشكيل، وقد يحوي أخطاء تعرّف
    بسيطة) يُستخدم فقط لاستخراج التوقيت الحقيقي، عبر مطابقة الفروقات
    (difflib) بين الكلمتين بعد تطبيع كل منهما. أي كلمة من السكريبت لم
    يتعرّف عليها Whisper بثقة تأخذ توقيتًا تقريبيًا من أقرب كلمتين
    متطابقتين قبلها وبعدها، بدل أن تُفقد."""
    # Prefer the stronger ASR transcript for timing when the base model misses
    # Arabic words; both models are already cached by the pronunciation gate.
    segments = _cached_whisper_segments(audio_path, ASR_FALLBACK_MODEL_SIZE)

    whisper_words: list[tuple[str, float, float]] = []
    for segment in segments:
        for w in (segment.words or []):
            text = (w.word or "").strip()
            if text:
                whisper_words.append((text, float(w.start), float(w.end)))
    if not whisper_words:
        raise RuntimeError("Whisper لم يرجع أي توقيت على مستوى الكلمة")

    def _norm(w: str) -> str:
        return strip_diacritics(w).translate(DISPLAY_PUNCTUATION).strip().lower().translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ؤ":"و","ئ":"ي"}))

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

    from scripts.asr_token_boundaries import recover_token_boundaries
    recover_token_boundaries(script_norm,whisper_norm,whisper_words,script_words,timings)
    known_indices = [i for i, t in enumerate(timings) if t is not None]
    # The independent audio-vs-script ASR gate already passed before this
    # function. Allow limited Whisper word-boundary misses (Arabic clitics,
    # spelling variants), but never fabricate timing for more than 20%.
    if not known_indices or len(known_indices) < len(script_words) * 0.80:
        from scripts.forced_caption_alignment import forced_word_alignment
        return forced_word_alignment(audio_path,script_words)

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
    if not voice_text.strip():
        raise ValueError("Empty narration")
    generate(voice_text,VOICE_AUDIO)
    display_words=strip_diacritics(voice_text).split()
    assert_audio_matches_script(VOICE_AUDIO,voice_text)
    all_word_events=align_words_with_whisper(VOICE_AUDIO,display_words)
    if not all_word_events:
        sys.exit("❌ تعذر إنشاء توقيت الترجمة.")
    dialogue_lines = []
    for group in caption_word_groups(all_word_events, WORDS_PER_CAPTION_CHUNK):
        start = group[0]["offset"]
        end = group[-1]["offset"] + group[-1]["duration"]
        words = [e["text"] for e in group]
        for active_index in range(len(words)):
            word_start = group[active_index]["offset"]
            word_end = group[active_index]["offset"] + group[active_index]["duration"]
            for payload in render_active_arabic_caption(
                words, active_index, canvas_width=VIDEO_W,
                center_y=VIDEO_H - FULL_CAPTION_BOTTOM_MARGIN - 29,
            ):
                dialogue_lines.append(
                    f"Dialogue: 0,{ass_time(word_start)},{ass_time(max(word_end, word_start + 0.12))},Caption,,0,0,0,,{payload}"
                )
    SUBTITLES.write_text(build_ass_header() + "\n".join(dialogue_lines) + "\n", encoding="utf-8")


def prepare_final_audio() -> None:
    """Preserve the verified MP3 bytes without another lossy conversion."""
    shutil.copyfile(VOICE_AUDIO,FINAL_AUDIO)


def main() -> None:
    if os.getenv("TTS_ENGINE","gemini").lower()!="gemini":
        raise ValueError("Production requires Gemini Charon")
    episode=json.loads(EPISODE_PATH.read_text(encoding="utf-8"))
    narration=spoken_numbers(normalize_text(str(episode.get("narration",""))))
    if not narration or validate_narration(narration):
        raise ValueError("Invalid or empty narration")
    CLIPS_DIR.mkdir(parents=True,exist_ok=True)
    spoken=apply_phonetic_hints(narration,episode.get("phonetic_hints") or [])
    synthesize_voice(spoken)
    prepare_final_audio()
    episode.pop("parts",None)
    episode.update(narration=narration,voice_profile="gemini:Charon",voice_audio=str(VOICE_AUDIO),final_audio=str(FINAL_AUDIO),subtitles=str(SUBTITLES))
    EPISODE_PATH.write_text(json.dumps(episode,ensure_ascii=False,indent=2),encoding="utf-8")
    save_voice_to_history(episode,"gemini:Charon")
    print(f"Complete Charon narration and captions: {FINAL_AUDIO}",flush=True)

if __name__=="__main__":
    main()
