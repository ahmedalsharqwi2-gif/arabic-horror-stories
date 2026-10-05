"""Safe Arabic ASS caption rendering shared by the speech pipeline."""
from __future__ import annotations

import re

# Bidi controls are presentation metadata, not word content.  Passing them
# through to libass can split an Arabic shaping run in some renderers.
BIDI_CONTROLS = re.compile(r"[\u061C\u200E\u200F\u202A-\u202E\u2066-\u2069]")
ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u08D3-\u08FF]")
DISPLAY_PUNCTUATION = str.maketrans(".,،؛:!?؟…-—_()[]{}\"«»/\\", " " * 23)


def display_word(word: str) -> str:
    """Return a clean display token while preserving Arabic joining."""
    word = BIDI_CONTROLS.sub("", str(word or ""))
    return ARABIC_DIACRITICS.sub("", word).translate(DISPLAY_PUNCTUATION).strip()


def render_arabic_caption(words: list[str]) -> str:
    """Render a short Arabic caption using ASS ``\\N`` for the line break.

    Direction controls are deliberately omitted: libass shapes the Arabic
    text, and hidden U+200F markers can split joining on some renderers.
    """
    clean_words = [token for word in words for token in display_word(word).split()]
    if len(clean_words) <= 3:
        return " ".join(clean_words)
    midpoint = (len(clean_words) + 1) // 2
    return " ".join(clean_words[:midpoint]) + r"\N" + " ".join(clean_words[midpoint:])


def caption_word_groups(events: list[dict], max_words: int = 6) -> list[list[dict]]:
    """Split by displayed words, preserving the span of each aligned event.

    An ASR event can contain several words or punctuation-joined words.
    Subdivide that event's duration before grouping so caption limits apply
    to what libass displays, rather than to the number of ASR records.
    """
    if max_words < 1:
        raise ValueError("max_words must be positive")
    words = []
    for event in events:
        tokens = display_word(event.get("text", "")).split()
        if not tokens:
            continue
        duration = float(event["duration"]) / len(tokens)
        for index, token in enumerate(tokens):
            words.append({**event, "text": token,
                          "offset": float(event["offset"]) + index * duration,
                          "duration": duration})
    return [words[index:index + max_words]
            for index in range(0, len(words), max_words)]
