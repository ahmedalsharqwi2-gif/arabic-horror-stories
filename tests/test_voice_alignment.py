import sys
import types
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("edge_tts", types.ModuleType("edge_tts"))
import scripts.generate_voice as voice
from scripts.generate_voice import align_words_with_whisper, two_lines


class VoiceAlignmentTests(unittest.TestCase):
    def test_caption_renderer_never_emits_bidi_controls(self):
        rendered = two_lines(["هذا\u200f", "نص", "عربي", "سليم"])

        self.assertNotIn("\u200f", rendered)
        self.assertNotIn("\u200e", rendered)
        self.assertEqual(rendered, "هذا نص عربي سليم")

    def test_six_words_are_split_three_and_three(self):
        rendered = two_lines(["واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة"])
        self.assertNotIn(r"\N", rendered)
        self.assertEqual(rendered, "واحد اثنان ثلاثة أربعة خمسة ستة")

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

    def test_stronger_fallback_asr_can_confirm_audio_without_lowering_threshold(self):
        def transcript(_path, model_size):
            return ["واحد", "اثنان"] if model_size == "base" else ["واحد", "اثنان", "ثلاثة", "أربعة"]

        with patch.object(voice, "_transcribe_arabic_words", side_effect=transcript), \
             patch.object(voice, "WHISPER_MODEL_SIZE", "base"), \
             patch.object(voice, "ASR_FALLBACK_MODEL_SIZE", "small"), \
             patch.object(voice, "ASR_MIN_MATCH_RATIO", 0.60), \
             patch("builtins.print"):
            ratio = voice.assert_audio_matches_script(Path("unused.mp3"), "واحد اثنان ثلاثة أربعة")
        self.assertEqual(ratio, 1.0)

    def test_audio_still_fails_when_primary_and_fallback_asr_are_below_threshold(self):
        with patch.object(voice, "_transcribe_arabic_words", return_value=["واحد", "اثنان"]), \
             patch.object(voice, "WHISPER_MODEL_SIZE", "base"), \
             patch.object(voice, "ASR_FALLBACK_MODEL_SIZE", "small"), \
             patch.object(voice, "ASR_MIN_MATCH_RATIO", 0.60), \
             patch("builtins.print"):
            with self.assertRaisesRegex(RuntimeError, "base=50.0%.*small=50.0%"):
                voice.assert_audio_matches_script(Path("unused.mp3"), "واحد اثنان ثلاثة أربعة")


if __name__ == "__main__":
    unittest.main()
