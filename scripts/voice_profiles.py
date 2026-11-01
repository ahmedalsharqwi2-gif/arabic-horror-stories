"""Resolve reference-audio voice profiles bundled under assets/voices."""

from __future__ import annotations

import json
import hashlib
import os
import re
from pathlib import Path
from typing import Any


def choose_auto_profile(profiles: dict[str, Any], root: Path) -> str:
    """Select a suitable bundled voice and avoid the last few selections."""
    episode_path = root / "state" / "current_episode.json"
    episode: dict[str, Any] = {}
    if episode_path.is_file():
        try:
            episode = json.loads(episode_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    configured = [p.strip() for p in os.getenv("AUTO_VOICE_PROFILES", "").split(",") if p.strip()]
    candidates = [p for p in configured if p in profiles] or list(profiles)
    # الرعب يستخدم أصواتًا ذكورية فقط، حتى لو احتوى النص على شخصية نسائية.
    candidates = [p for p in candidates if p != "egyptian_female"]
    if not candidates:
        candidates = [p for p in profiles if p != "egyptian_female"]
    history_path = root / "state" / "used_clips.json"
    recent: list[str] = []
    if history_path.is_file():
        try:
            data = json.loads(history_path.read_text(encoding="utf-8"))
            recent = [str(item.get("voice_profile", "")) for item in data.get("history", [])[-3:]]
        except (OSError, json.JSONDecodeError):
            pass
    available = [p for p in candidates if p not in recent] or candidates
    seed = f"{episode.get('title', '')}|{episode.get('region', '')}".encode()
    return available[int.from_bytes(hashlib.sha256(seed).digest()[:4], "big") % len(available)]


def resolve_reference_profile(
    profile: str = "",
    config_path: str | Path = "assets/voices/voice_profiles.json",
    base_dir: str | Path | None = None,
) -> tuple[str, str, Path, str]:
    """Return (key, label, WAV path, transcript) for a configured profile."""
    root = Path(base_dir) if base_dir is not None else Path.cwd()
    catalog_path = Path(config_path)
    if not catalog_path.is_absolute():
        catalog_path = root / catalog_path
    if not catalog_path.is_file():
        raise FileNotFoundError(f"Voice profiles catalog is missing: {catalog_path}")

    data: dict[str, Any] = json.loads(catalog_path.read_text(encoding="utf-8"))
    profiles = data.get("profiles") or {}
    requested = profile.strip()
    selected = choose_auto_profile(profiles, root) if requested.lower() == "auto" else (
        requested or str(data.get("default", "")).strip()
    )
    if selected not in profiles:
        available = ", ".join(sorted(profiles)) or "none"
        raise ValueError(f"Unknown voice profile '{selected}'. Available: {available}")

    entry = profiles[selected]
    wav = Path(str(entry["wav"]))
    transcript_path = Path(str(entry["text"]))
    if not wav.is_absolute():
        wav = root / wav
    if not transcript_path.is_absolute():
        transcript_path = root / transcript_path
    if not wav.is_file():
        raise FileNotFoundError(f"Voice profile '{selected}' WAV is missing: {wav}")
    if not transcript_path.is_file():
        raise FileNotFoundError(f"Voice profile '{selected}' transcript is missing: {transcript_path}")

    transcript = transcript_path.read_text(encoding="utf-8").strip()
    if not transcript:
        raise ValueError(f"Voice profile '{selected}' transcript is empty: {transcript_path}")
    return selected, str(entry.get("label", selected)), wav, transcript
