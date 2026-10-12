"""Free last-resort visual: this narration's text, never an invented scene."""
from pathlib import Path
import re
import subprocess


def render_explainer(output: Path, seconds: float, scene: dict, cfg: dict) -> None:
    text = re.sub(r"[\\{}\u0000-\u001f]", "", scene["text"]).strip()
    if not text or seconds <= 0:
        raise ValueError("Empty explainer scene")
    def stamp(value):
        cs = round(value * 100)
        hour, cs = divmod(cs, 360000)
        minute, cs = divmod(cs, 6000)
        second, cs = divmod(cs, 100)
        return f"{hour}:{minute:02d}:{second:02d}.{cs:02d}"
    words = text.split()
    groups = [" ".join(words[i:i + 4]) for i in range(0, len(words), 4)]
    w, h = cfg["width"], cfg["height"]
    ass = output.with_suffix(".explainer.ass")
    ass.parent.mkdir(parents=True, exist_ok=True)
    header = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\n"
              "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
              f"Style: Text,Noto Naskh Arabic,{max(24, round(w / 15))},&H00FFFFFF,&H00FFFFFF,&H0010182B,&HAA000000,1,0,0,0,100,100,0,0,1,2,0,5,30,30,30,1\n"
              f"Style: Label,Noto Naskh Arabic,{max(16, round(w / 38))},&H00FFFFFF,&H00FFFFFF,&H0010182B,&HAA000000,0,0,0,0,100,100,0,0,1,2,0,2,30,30,{round(h / 5)},1\n"
              "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    lines = [header]
    for i, group in enumerate(groups):
        lines.append(f"Dialogue: 0,{stamp(i * seconds / len(groups))},{stamp((i + 1) * seconds / len(groups))},Text,,0,0,0,,{group}\n")
    lines.append(f"Dialogue: 1,0:00:00.00,{stamp(seconds)},Label,,0,0,0,,شرح نصي توضيحي\n")
    ass.write_text("".join(lines), encoding="utf-8")
    escaped = str(ass.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    color = {"history": "0x30291f", "horror": "0x162033", "science": "0x15324c"}[cfg["profile"]]
    vf = (f"drawgrid=width={max(1, w // 3)}:height={max(1, h // 6)}:thickness=1:color=white@0.07,"
          f"eq=brightness='0.012*sin(t)':eval=frame,subtitles='{escaped}'")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c={color}:s={w}x{h}:r={cfg['fps']}",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{seconds:.3f}", "-vf", vf,
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(output)],
                   check=True, capture_output=True, timeout=180)
