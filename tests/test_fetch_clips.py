from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from scripts.fetch_clips import has_excessive_black_frames


class FetchClipQualityTests(TestCase):
    @patch("scripts.fetch_clips.subprocess.run")
    def test_rejects_clip_with_black_intervals_over_gate_budget(self, run):
        run.return_value = SimpleNamespace(
            returncode=0,
            stderr="[blackdetect] black_start:0.000 black_end:0.200\n"
            "[blackdetect] black_start:1.000 black_end:1.201\n",
        )
        self.assertTrue(has_excessive_black_frames("clip.mp4"))

    @patch("scripts.fetch_clips.subprocess.run")
    def test_accepts_clip_with_no_material_black_intervals(self, run):
        run.return_value = SimpleNamespace(returncode=0, stderr="")
        self.assertFalse(has_excessive_black_frames("clip.mp4"))

    @patch("scripts.fetch_clips.subprocess.run")
    def test_inspection_error_fails_closed(self, run):
        run.return_value = SimpleNamespace(returncode=1, stderr="invalid media")
        with self.assertRaises(RuntimeError):
            has_excessive_black_frames("clip.mp4")
