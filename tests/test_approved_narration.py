"""The approved narration must stay complete and must never switch voices."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import generate_voice as voice

class ApprovedNarrationTests(unittest.TestCase):
    def test_timing_failure_does_not_invent_uniform_captions_or_switch_voice(self):
        with patch.object(voice,'generate') as generate, patch.object(voice,'assert_audio_matches_script'), patch.object(voice,'align_words_with_whisper',side_effect=RuntimeError('no measured timing')):
            with self.assertRaisesRegex(RuntimeError,'no measured timing'):
                voice.synthesize_voice("أول جملة. آخر جملة.")
            self.assertEqual(generate.call_count,1)
            self.assertEqual(generate.call_args.args[0],"أول جملة. آخر جملة.")

    def test_final_voice_preserves_every_verified_byte(self):
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/'verified.mp3';dst=Path(folder)/'final.mp3'
            src.write_bytes(b'complete-verified-audio-including-tail')
            with patch.object(voice,'VOICE_AUDIO',src),patch.object(voice,'FINAL_AUDIO',dst):
                voice.prepare_final_audio()
            self.assertEqual(src.read_bytes(),dst.read_bytes())
