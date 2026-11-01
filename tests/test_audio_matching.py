import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.audio_matching import normalize_decision, validate_manifest


class AudioMatchingTests(unittest.TestCase):
    def test_no_audio_forces_voice_only(self):
        self.assertEqual(normalize_decision("ORIGINAL AUDIO + VOICE", False), "VOICE ONLY")

    def test_unknown_decision_is_rejected_when_audio_exists(self):
        with self.assertRaises(ValueError):
            normalize_decision("ADD SCARY SOUND", True)

    def test_mute_requires_reason(self):
        with self.assertRaises(ValueError):
            validate_manifest([{"audio_status": "PASS", "audio_decision": "MUTE", "audio_match": "PASS"}])

    def test_original_audio_requires_match_pass(self):
        with self.assertRaises(ValueError):
            validate_manifest([{"audio_status": "PASS", "audio_decision": "ORIGINAL AUDIO + VOICE", "audio_match": "REJECT"}])

    def test_reviewed_mute_is_preserved_for_a_silent_source(self):
        self.assertEqual(normalize_decision("MUTE", False), "MUTE")


if __name__ == "__main__":
    unittest.main()
