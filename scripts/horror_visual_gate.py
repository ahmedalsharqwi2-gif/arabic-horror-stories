from __future__ import annotations
import json
import sys
from pathlib import Path
try:
    from scripts.audio_matching import validate_manifest
except ModuleNotFoundError:
    from audio_matching import validate_manifest

def validate(episode: dict, manifest: list[dict]) -> None:
    approved = {str(item.get("keyword")): item for item in episode.get("visual_match", []) if item.get("status") == "PASS"}
    if len(manifest) < 4: raise ValueError("VISUAL GATE FAILED: fewer than four clips")
    validate_manifest(manifest)
    for index, item in enumerate(manifest, 1):
        key = str(item.get("keyword", ""))
        if key not in approved: raise ValueError(f"VISUAL GATE FAILED: clip {index} has no approved visual plan")
        if item.get("status") != "PASS": raise ValueError(f"VISUAL GATE FAILED: clip {index} status is not PASS")
        if item.get("authenticity") not in {"REAL_ARCHIVE", "REAL_LOCATION", "MAP", "SYMBOLIC", "REENACTMENT", "AI_RECONSTRUCTION"}:
            raise ValueError(f"VISUAL GATE FAILED: clip {index} authenticity missing")

def main() -> None:
    episode = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    manifest = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    validate(episode, manifest)
    print("HORROR_VISUAL_GATE: PASS")

if __name__ == "__main__": main()
