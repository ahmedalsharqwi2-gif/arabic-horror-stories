"""Safe Arabic ASS caption rendering shared by the speech pipeline."""
from __future__ import annotations

import re
from .rtl_caption_layout import layout_word_centers

# Bidi controls are presentation metadata, not word content.  Passing them
# through to libass can split an Arabic shaping run in some renderers.
BIDI_CONTROLS = re.compile(r"[\u061C\u200E\u200F\u202A-\u202E\u2066-\u2069]")
ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u08D3-\u08FF]")
DISPLAY_PUNCTUATION = str.maketrans(".,،؛:!?؟…-—_()[]{}\"«»/\\", " " * 23)


def display_word(word: str) -> str:
    """Return a clean display token while preserving Arabic joining."""
    word = BIDI_CONTROLS.sub("", str(word or ""))
    return ARABIC_DIACRITICS.sub("", word).translate(DISPLAY_PUNCTUATION).strip()


def _clean_words(words: list[str]) -> list[str]:
    return [token for word in words for token in display_word(word).split()]

def render_arabic_caption(words: list[str]) -> str:
    """Render a single RTL caption line; callers limit it to four words."""
    return " ".join(_clean_words(words))

def render_active_arabic_caption(
    words: list[str], active_index: int, *, canvas_width: int = 1080,
    center_y: int = 1821, font_size: int = 58,
    font_name: str = "Noto Naskh Arabic", side_margin: int = 70,
    extra_ass_tags: str = "",
) -> list[str]:
    """Return one positioned ASS text payload per word, in logical RTL order.

    Callers must write each returned payload as its own Dialogue event; this
    keeps color overrides from making libass reorder Arabic words.
    """
    clean_words = _clean_words(words)
    if not clean_words:
        return []
    if not 0 <= active_index < len(clean_words):
        raise ValueError("active_index is outside the displayed caption words")
    centers, scale = layout_word_centers(
        clean_words, canvas_width, font_size, font_name=font_name,
        side_margin=side_margin,
    )
    rendered = []
    for index, (word, center_x) in enumerate(zip(clean_words, centers)):
        color = r"\c&H000000FF&" if index == active_index else ""
        payload = f"{{\\an5\\pos({center_x},{center_y})\\fscx{scale}{extra_ass_tags}{color}}}"
        rendered.append(payload + word.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}"))
    return rendered

def caption_word_groups(events: list[dict], max_words: int = 4) -> list[list[dict]]:
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
