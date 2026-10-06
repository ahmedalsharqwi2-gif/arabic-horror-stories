import sys
import types
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("edge_tts", types.ModuleType("edge_tts"))
from scripts.generate_voice import align_words_with_whisper, two_lines


class VoiceAlignmentTests(unittest.TestCase):
    def test_caption_renderer_never_emits_bidi_controls(self):
        rendered = two_lines(["هذا\u200f", "نص", "عربي", "سليم"])

        self.assertNotIn("\u200f", rendered)
        self.assertNotIn("\u200e", rendered)
        self.assertEqual(rendered, "هذا نص\\Nعربي سليم")

    def test_six_words_are_split_three_and_three(self):
        rendered = two_lines(["واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة"])
        self.assertIn(r"\N", rendered)
        self.assertIn("واحد اثنان ثلاثة", rendered)
        self.assertIn("أربعة خمسة ستة", rendered)

    def test_three_words_stay_on_one_line(self):
        self.assertNotIn(r"\N", two_lines(["واحد", "اثنان", "ثلاثة"]))

    def test_alignment_normalizes_diacritics_but_preserves_display_text(self):
        class Word:
            def __init__(self, text, start, end):
                self.word = text
                self.start = start
                self.end = end

        class Segment:
            words = [
                Word("مَرْحَبًا", 0.0, 0.4),
                Word("بِكُمْ", 0.4, 0.8),
            ]

        fake_module = types.ModuleType("faster_whisper")
        fake_module.WhisperModel = lambda *args, **kwargs: types.SimpleNamespace(
            transcribe=lambda *args, **kwargs: ([Segment()], object())
        )
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {"faster_whisper": fake_module}):
            audio = Path(directory) / "audio.mp3"
            audio.write_bytes(b"mock audio fixture")
            result = align_words_with_whisper(
                audio, ["مَرْحَبًا", "بِكُمْ"]
            )

        self.assertEqual([event["text"] for event in result], ["مَرْحَبًا", "بِكُمْ"])
        self.assertEqual(result[0]["offset"], 0.0)
        self.assertEqual(result[1]["offset"], 0.4)


if __name__ == "__main__":
    unittest.main()
