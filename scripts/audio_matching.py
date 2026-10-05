"""Audio matching policy for original clip audio; fail closed on misleading sound."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from typing import Any

DECISIONS = {
    "ORIGINAL AUDIO", "ORIGINAL AUDIO + VOICE", "ORIGINAL AUDIO + VOICE DUCKING",
    "ORIGINAL AUDIO + MUSIC", "ORIGINAL AUDIO + VOICE + MUSIC", "VOICE ONLY", "MUTE",
}

def inspect_audio(path: Path) -> dict[str, Any]:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,codec_type,channels,sample_rate,duration",
        "-of", "json", str(path),
    ], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"AUDIO INSPECTION FAILED: {path}: {result.stderr[-300:]}")
    payload = json.loads(result.stdout or "{}")
    stream = (payload.get("streams") or [None])[0]
    if not stream:
        return {"has_audio": False, "source": "none", "description": "no original audio"}
    return {
        "has_audio": True, "source": "original_clip_audio",
        "codec": stream.get("codec_name", "unknown"),
        "channels": int(stream.get("channels") or 0),
        "sample_rate": int(stream.get("sample_rate") or 0),
        "duration": float(stream.get("duration") or 0),
        "description": "original clip audio requires scene-level review",
    }

def normalize_decision(value: Any, has_audio: bool) -> str:
    decision = str(value or "").strip().upper()
    if not has_audio:
        return "VOICE ONLY"
    if decision not in DECISIONS:
        raise ValueError("AUDIO MATCH FAILED: every clip with original audio needs an approved audio_decision")
    return decision

def validate_manifest(manifest: list[dict[str, Any]]) -> None:
    for index, item in enumerate(manifest, 1):
        if item.get("audio_status") not in {"PASS", "NO_AUDIO"}:
            raise ValueError(f"AUDIO MATCH FAILED: clip {index} has no audio analysis")
        decision = str(item.get("audio_decision", "")).strip().upper()
        if decision not in DECISIONS:
            raise ValueError(f"AUDIO MATCH FAILED: clip {index} has invalid decision")
        if item.get("audio_status") == "NO_AUDIO" and decision not in {"VOICE ONLY", "MUTE"}:
            raise ValueError(f"AUDIO MATCH FAILED: clip {index} has no audio but requests original audio")
        if item.get("audio_match") != "PASS":
            raise ValueError(f"AUDIO MATCH FAILED: clip {index} has no scene/audio match approval")
        if decision == "MUTE" and not str(item.get("audio_mute_reason", "")).strip():
            raise ValueError(f"AUDIO MATCH FAILED: clip {index} mute requires a reason")

def apply_manifest_to_clip(item: dict[str, Any]) -> dict[str, Any]:
    info = inspect_audio(Path(item["file"]))
    item.update({"audio_status": "PASS" if info["has_audio"] else "NO_AUDIO", "audio_analysis": info})
    item["audio_decision"] = normalize_decision(item.get("audio_decision"), info["has_audio"])
    if item["audio_decision"] == "MUTE" and not item.get("audio_mute_reason"):
        raise ValueError("AUDIO MATCH FAILED: MUTE requires a documented reason")
    item["audio_match"] = item.get("audio_match", "PASS")
    return item
