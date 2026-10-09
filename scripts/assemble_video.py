"""
assemble_video.py

ينتج أصلين من نفس الحلقة:

1) فيديو كامل عمودي 9:16:
   output/final_video_full.mp4

2) لا يتم إنشاء ريل؛ المخرج الوحيد هو القصة الكاملة العمودية:

مصدر الحقيقة للصوت والترجمة هو current_episode.json. يدعم الملف الحقول الجديدة:

{
  "final_audio": "downloaded_clips/narration.mp3",
  "subtitles": "downloaded_clips/narration.ass",
  "shorts": [
    {"start_seconds": 0, "end_seconds": 75}
  ]
}

تُهمل أي قائمة shorts قديمة ولا تُنتج ملفات ريل،
مع ترك AUTO_END_MARGIN_SECONDS في نهاية الحلقة حتى لا يصل المقتطف إلى الحل.

مهم: مدة 90 ثانية حد للريل فقط، وليست حدًا للفيديو الكامل.

=== تخطيط النص في المنطقة الآمنة ===
- ترجمة السرد في أصل 16:9 محاذاة أسفل-وسط بهامش سفلي 70px؛ وهذا يضمن
  ظهورها أسفل الشاشة في الفيديو الأفقي بدون التصاقها بالحافة.
- الترجمة يظهر في مسار علوي ثانٍ (هامش 620px في إطار الريل) حتى لا يتداخل
  مع الترجمة أثناء آخر ثوانٍ، مع بقائه في النصف العلوي من الشاشة.
- الخط والحجم للتنويه يظلان مأخوذين من ملف ترجمة الحلقة.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from scripts.media_audio import add_topic_soundtrack

try:
    from scripts.clip_review import review_clip
    from scripts.media_audio import normalized_audio_args, ducking_filters, has_audio
except ModuleNotFoundError:
    from clip_review import review_clip
    from media_audio import normalized_audio_args, ducking_filters, has_audio

SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
STATE_DIR = ROOT_DIR / "state"
CLIPS_DIR = ROOT_DIR / "downloaded_clips"
OUTPUT_DIR = ROOT_DIR / "output"
SFX_DIR = ROOT_DIR / "assets" / "sfx"
HORROR_AMBIENCE_GAIN = 0.045
HORROR_EVENT_GAIN = 0.22

FETCHED_CLIPS_PATH = STATE_DIR / "fetched_clips.json"
EPISODE_PATH = STATE_DIR / "current_episode.json"

# الفيديو الكامل: عمودي 9:16
FULL_WIDTH = 1080
FULL_HEIGHT = 1920

SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920
# Keep one second of headroom below the one-minute reel target so
# container/encoding rounding cannot produce an over-limit upload.
MAX_SHORT_DURATION_SECONDS = 59.0
MAX_FULL_VIDEO_SECONDS = 180.0
AUTO_END_MARGIN_SECONDS = 8.0
# Captions for 9:16 are rendered independently, below the camera/notch safe area.
REEL_CAPTION_TOP_MARGIN = 300
FPS = 30

# خط/حجم افتراضي يُستخدم فقط لو تعذّرت قراءة ستايل السكربت من ملف الترجمة.
FALLBACK_مقتطف_FONT = "Arial"
FALLBACK_مقتطف_SIZE = 62

PLATFORMS = ("youtube", "facebook", "instagram")


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "❌ فشل الأمر:\n"
            + " ".join(command)
            + "\n\n"
            + result.stderr
        )
    return result


def probe_duration(path: Path) -> float:
    result = run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ])
    try:
        return float(result.stdout.strip())
    except ValueError:
        raise RuntimeError(f"❌ تعذر قراءة مدة الملف: {path}")


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    # المسارات القديمة قد تكون نسبية إلى جذر المشروع أو إلى scripts/.
    candidates = [ROOT_DIR / path, SCRIPT_DIR / path]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return ROOT_DIR / path


def normalize_clip(input_path: Path, output_path: Path, duration: float, audio_decision: str = "VOICE ONLY") -> None:
    """Normalize video and preserve approved original audio; never mute by default."""
    decision = str(audio_decision or "VOICE ONLY").upper()
    keep_audio = decision.startswith("ORIGINAL AUDIO")
    extra, mapping = normalized_audio_args(input_path, keep_audio)
    command = [
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(input_path), *extra, "-t", f"{duration:.3f}",
        "-vf", f"scale={FULL_WIDTH}:{FULL_HEIGHT}:force_original_aspect_ratio=increase,crop={FULL_WIDTH}:{FULL_HEIGHT},fps={FPS}",
        "-map", "0:v:0", *mapping,
    ]
    command += ["-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output_path)]
    run(command)


def concat_clips(paths: list[Path], output_path: Path, list_path: Path) -> None:
    if not paths:
        raise RuntimeError("❌ لا توجد مقاطع صالحة لتجميعها.")

    list_path.write_text(
        "\n".join(f"file '{path.resolve().as_posix()}'" for path in paths) + "\n",
        encoding="utf-8",
    )
    run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-c", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ])


def subtitle_filter(subtitles: Path | None) -> str | None:
    if not subtitles or not subtitles.exists():
        return None
    path = str(subtitles.resolve()).replace("\\", "/").replace(":", "\\:")
    return f"subtitles='{path}'"


def build_vertical_subtitles(source: Path | None, output: Path) -> Path | None:
    """Convert the narration ASS track to a 9:16, top-safe caption lane."""
    if not source or not source.exists():
        return None
    text = source.read_text(encoding="utf-8", errors="ignore")
    text = text.replace("PlayResX: 1920", f"PlayResX: {SHORT_WIDTH}")
    text = text.replace("PlayResY: 1080", f"PlayResY: {SHORT_HEIGHT}")
    lines = []
    for line in text.splitlines():
        if line.startswith("Style: Caption,"):
            fields = line.split(",")
            # ASS style fields: Alignment=18, MarginL=19, MarginR=20,
            # MarginV=21. Alignment 8 is top-center.
            if len(fields) >= 22:
                fields[18] = "8"
                fields[19] = "70"
                fields[20] = "70"
                fields[21] = str(REEL_CAPTION_TOP_MARGIN)
                line = ",".join(fields)
        lines.append(line)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def extract_subtitle_style(ass_path: Path | None) -> tuple[str, int]:
    """يقرأ اسم الخط وحجمه من أول Style معرّف في ملف ترجمة السكربت
    (قسم [V4+ Styles])، عشان تنويه الريل (مقتطف) يستخدم نفس خط وحجم
    ترجمة الفيديو نفسها تلقائيًا مهما تغيّر إعداد الخط في
    generate_voice.py مستقبلًا، بدل تثبيت قيمة يدوية هنا قد تختلف عن
    الخط الفعلي المستخدم في الفيديو.
    """
    if not ass_path or not ass_path.exists():
        return FALLBACK_مقتطف_FONT, FALLBACK_مقتطف_SIZE

    try:
        text = ass_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return FALLBACK_مقتطف_FONT, FALLBACK_مقتطف_SIZE

    in_styles = False
    format_fields: list[str] = []
    first_style: tuple[str, int] | None = None
    default_style: tuple[str, int] | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("[") and not line.startswith("[V4"):
            in_styles = False
            continue
        if line.startswith("[V4+ Styles]") or line.startswith("[V4 Styles]"):
            in_styles = True
            continue
        if not in_styles:
            continue
        if line.startswith("Format:"):
            format_fields = [f.strip() for f in line[len("Format:"):].split(",")]
            continue
        if line.startswith("Style:") and format_fields:
            values = [v.strip() for v in line[len("Style:"):].split(",")]
            row = dict(zip(format_fields, values))
            try:
                font_name = row.get("Fontname") or FALLBACK_مقتطف_FONT
                font_size = int(float(row.get("Fontsize", FALLBACK_مقتطف_SIZE)))
            except (TypeError, ValueError):
                continue
            if first_style is None:
                first_style = (font_name, font_size)
            if row.get("Name") == "Default":
                default_style = (font_name, font_size)

    chosen = default_style or first_style
    return chosen or (FALLBACK_مقتطف_FONT, FALLBACK_مقتطف_SIZE)


def mix_horror_audio(final_audio: Path, duration: float, output_path: Path, original_audio: Path | None = None) -> Path:
    """Mix narration with approved original clip audio and restrained effects."""
    ambience = SFX_DIR / "horror_abandoned_room_loop.mp3"
    footsteps = SFX_DIR / "horror_distant_footsteps.mp3"
    reveal = SFX_DIR / "horror_reveal_hit.mp3"
    if not all(p.is_file() for p in (ambience, footsteps, reveal)):
        raise FileNotFoundError("ملفات مؤثرات الرعب ناقصة داخل assets/sfx")
    points = [max(0.8, duration * 0.38), max(1.2, duration * 0.72)]
    inputs = ["-i", str(final_audio)]
    has_original = bool(original_audio and original_audio.exists() and has_audio(original_audio))
    if has_original:
        inputs += ["-i", str(original_audio)]
    inputs += ["-stream_loop", "-1", "-i", str(ambience), "-i", str(reveal)]
    for _ in points:
        inputs += ["-i", str(footsteps)]
    original_index = 1 if has_original else None
    ambience_index = 2 if has_original else 1
    reveal_index = ambience_index + 1
    first_steps_index = reveal_index + 1
    filters = ["[0:a]aresample=48000,volume=1.0[voice]"]
    original_mix = ""
    if has_original:
        filters = ducking_filters("[0:a]", f"[{original_index}:a]")
        original_mix = "[ducked]"
    filters += [f"[{ambience_index}:a]aresample=48000,volume={HORROR_AMBIENCE_GAIN},atrim=duration={duration:.3f}[room]",
                f"[{reveal_index}:a]aresample=48000,volume={HORROR_EVENT_GAIN},adelay=450|450,atrim=duration={duration:.3f}[hit]"]
    labels = []
    for index, point in enumerate(points):
        input_idx = first_steps_index + index
        label = f"steps{index}"
        delay = int(point * 1000)
        filters.append(f"[{input_idx}:a]aresample=48000,volume={HORROR_EVENT_GAIN},adelay={delay}|{delay},atrim=duration={duration:.3f}[{label}]")
        labels.append(f"[{label}]")
    filters.append(f"[voice]{original_mix}[room][hit]{''.join(labels)}amix=inputs={3+len(points)+int(has_original)}:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95:level=disabled[a]")
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "[a]", "-t", f"{duration:.3f}", "-c:a", "libmp3lame", "-b:a", "192k", str(output_path)])
    add_topic_soundtrack(output_path, final_audio, duration, "horror")
    return output_path


def add_audio_and_subtitles(
    video_path: Path,
    final_audio: Path,
    subtitles: Path | None,
    output_path: Path,
) -> None:
    filters = []
    sub_filter = subtitle_filter(subtitles)
    if sub_filter:
        filters.append(sub_filter)

    mixed_audio = output_path.with_suffix(".mixed.mp3")
    mix_horror_audio(final_audio, probe_duration(final_audio), mixed_audio, original_audio=video_path)
    command = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(mixed_audio),
    ]
    if filters:
        command += ["-vf", ";".join(filters), "-c:v", "libx264",
                    "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p"]
    else:
        # Normalized H.264 clips need no second video encode when only audio changes.
        command += ["-c:v", "copy"]
    command += [
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-t", f"{probe_duration(mixed_audio):.3f}",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ]
    try:
        run(command)
    finally:
        mixed_audio.unlink(missing_ok=True)


def build_full_video(
    clips: list[dict],
    final_audio: Path,
    subtitles: Path | None,
    output_path: Path,
    clean_output_path: Path | None = None,
) -> float:
    """يبني الحلقة الكاملة الأفقية دون قصها إلى 90 ثانية."""
    audio_duration = probe_duration(final_audio)
    if audio_duration <= 0:
        raise RuntimeError("❌ مدة الصوت النهائي غير صالحة.")

    duration_per_clip = max(audio_duration / len(clips), 2.0)
    normalized: list[Path] = []
    for index, clip in enumerate(clips):
        source = resolve_path(clip["file"])
        if not source.exists():
            raise RuntimeError(f"❌ الكليب غير موجود: {source}")
        norm_path = CLIPS_DIR / f"norm_full_{index:03d}.mp4"
        normalize_clip(source, norm_path, duration_per_clip, clip.get("audio_decision", "VOICE ONLY"))
        normalized.append(norm_path)

    concatenated = CLIPS_DIR / "concatenated_full.mp4"
    concat_clips(normalized, concatenated, CLIPS_DIR / "concat_list_full.txt")
    if clean_output_path:
        add_audio_and_subtitles(concatenated, final_audio, None, clean_output_path)
    add_audio_and_subtitles(concatenated, final_audio, subtitles, output_path)
    return probe_duration(output_path)



def default_short_specs(full_duration: float) -> list[dict]:
    """ينشئ ريل واحد فقط من أول الفيديو، ويترك هامشًا قبل نهاية القصة
    حتى لا يصل المقتطف إلى الحل."""
    usable_end = max(1.0, full_duration - AUTO_END_MARGIN_SECONDS)
    window = min(MAX_SHORT_DURATION_SECONDS, usable_end)
    if window < 1:
        window = min(full_duration, MAX_SHORT_DURATION_SECONDS)
    return [{"start_seconds": 0.0, "end_seconds": window}]


def load_short_specs(episode: dict, full_duration: float) -> list[dict]:
    raw = episode.get("shorts")
    if not isinstance(raw, list) or not raw:
        return default_short_specs(full_duration)

    specs = []
    safe_end = max(0.0, full_duration - AUTO_END_MARGIN_SECONDS)
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            start = max(0.0, float(item.get("start_seconds", 0)))
            requested_end = float(item.get("end_seconds", start + MAX_SHORT_DURATION_SECONDS))
        except (TypeError, ValueError):
            continue

        end = min(requested_end, start + MAX_SHORT_DURATION_SECONDS, safe_end)
        if end - start >= 1.0:
            specs.append({"start_seconds": start, "end_seconds": end})

    # نستخدم أول ريل معرّف بس (ريل واحد)، حتى لو كان فيه أكتر من عنصر
    # في current_episode.json من نسخة قديمة.
    return specs[:1] or default_short_specs(full_duration)


def finish_reel_at_caption_boundary(spec: dict, subtitles: Path | None) -> dict:
    """Prefer a complete sentence between 45 seconds and the requested cap."""
    if not subtitles or not subtitles.exists():
        return spec
    start, end = spec["start_seconds"], spec["end_seconds"]
    caption_ends, sentence_ends = [], []
    for line in subtitles.read_text(encoding="utf-8-sig").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        fields = line.split(",", 9)
        if len(fields) != 10:
            continue
        try:
            hours, minutes, seconds = fields[2].split(":")
            timestamp = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        except (ValueError, TypeError):
            continue
        if start + 45 <= timestamp <= end:
            caption_ends.append(timestamp)
            text = re.sub(r"\{[^}]*\}", "", fields[9]).strip()
            if text.rstrip('"»”').endswith((".", "!", "؟", "?", "…")):
                sentence_ends.append(timestamp)
    candidates = sentence_ends or caption_ends
    if not candidates:
        return spec
    return {**spec, "end_seconds": max(candidates)}


def create_short(
    source_video: Path,
    spec: dict,
    short_index: int,
    platform: str,
    output_path: Path,
    font_name: str = "Arial",
    font_size: int = 58,
    subtitles: Path | None = None,
) -> float:
    start = float(spec["start_seconds"])
    end = float(spec["end_seconds"])
    duration = min(end - start, MAX_SHORT_DURATION_SECONDS)
    if duration <= 0:
        raise ValueError("مدة الريل يجب أن تكون أكبر من صفر")


    # crop مركزي من 16:9 إلى 9:16، مع الإبقاء على صوت الفيديو الكامل.
    vf = (
        f"scale={SHORT_WIDTH}:{SHORT_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={SHORT_WIDTH}:{SHORT_HEIGHT}"
    )
    narration_subtitle_filter = subtitle_filter(subtitles)
    if narration_subtitle_filter:
        vf += f",{narration_subtitle_filter}"

    run([
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-i", str(source_video),
        "-t", f"{duration:.3f}",
        "-vf", vf,
        "-map", "0:v:0",
        "-map", "0:a:0?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ])
    return probe_duration(output_path)


def _run() -> None:
    from scripts.cinematic_production import enabled, build_episode
    if enabled():
        build_episode(ROOT_DIR)
        return
    for path in (FETCHED_CLIPS_PATH, EPISODE_PATH):
        if not path.exists():
            raise RuntimeError(f"❌ الملف غير موجود: {path}")

    clips = json.loads(FETCHED_CLIPS_PATH.read_text(encoding="utf-8"))
    if not isinstance(clips, list) or not clips:
        raise RuntimeError("❌ fetched_clips.json فارغ أو غير صالح.")

    episode = json.loads(EPISODE_PATH.read_text(encoding="utf-8"))
    for clip in clips:
        reviewed = review_clip(resolve_path(clip["file"]), str(clip.get("keyword", "")), str(episode.get("title", "")), historical=episode.get("historical") is True)
        if reviewed["audio_decision"] != clip.get("audio_decision"):
            raise ValueError("Audio decision differs from byte-bound clip review")
    final_audio_value = episode.get("final_audio")
    subtitles_value = episode.get("subtitles")

    # توافق مع current_episode القديم الذي كان يحفظ المخرجات داخل parts.
    if not final_audio_value:
        parts = episode.get("parts") or []
        if len(parts) == 1:
            final_audio_value = parts[0].get("final_audio")
            subtitles_value = subtitles_value or parts[0].get("subtitles")
        elif len(parts) > 1:
            raise RuntimeError(
                "❌ current_episode.json ما زال يحتوي على أجزاء متعددة. "
                "شغّل generate_voice.py بالنسخة الجديدة لإنتاج صوت كامل واحد."
            )

    if not final_audio_value:
        final_audio_value = str(CLIPS_DIR / "narration.mp3")
    final_audio = resolve_path(final_audio_value)
    subtitles = resolve_path(subtitles_value) if subtitles_value else None

    if not final_audio.exists():
        raise RuntimeError(f"❌ ملف الصوت النهائي غير موجود: {final_audio}")
    if subtitles and not subtitles.exists():
        print(f"⚠️ ملف الترجمة غير موجود؛ سيتم إنتاج الفيديو بدون ترجمة: {subtitles}")
        subtitles = None


    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)

    # لا نترك ملفات أصول قديمة تُفهم على أنها ناتج التشغيل الحالي.
    for old in OUTPUT_DIR.glob("final_video_part*.mp4"):
        old.unlink(missing_ok=True)
    for old in OUTPUT_DIR.glob("short_*.mp4"):
        old.unlink(missing_ok=True)

    full_output = OUTPUT_DIR / "final_video_full.mp4"
    clean_full_output = CLIPS_DIR / "full_video_clean.mp4"
    full_duration = build_full_video(
        clips, final_audio, build_vertical_subtitles(subtitles, CLIPS_DIR / "narration_full_vertical.ass"), full_output,
        clean_output_path=clean_full_output,
    )
    print(f"✅ الفيديو الكامل العمودي: {full_output}")
    if full_duration <= 0 or full_duration > MAX_FULL_VIDEO_SECONDS:
        raise ValueError(f"مدة الفيديو الكامل يجب أن تكون بين 0 و180 ثانية: {full_duration:.2f}s")
    print(f"✅ مدة الفيديو الكامل العمودي: {full_duration:.1f} ثانية")

    print("✅ تم إنتاج قصة كاملة واحدة فقط؛ لن يتم إنشاء أي ريل أو short_*.mp4.")
def main() -> int:
    try:
        _run()
    except Exception as exc:
        print(f"❌ Video assembly failed: {exc}")
        return 1
    return 0
if __name__ == "__main__":
    raise SystemExit(main())

