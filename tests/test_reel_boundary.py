import tempfile
import unittest
from pathlib import Path
from scripts.assemble_video import finish_reel_at_caption_boundary

class ReelBoundaryTests(unittest.TestCase):
    def test_prefers_sentence_end_over_later_incomplete_caption(self):
        with tempfile.TemporaryDirectory() as directory:
            subtitles = Path(directory) / "captions.ass"
            subtitles.write_text("Dialogue: 0,0:00:49.00,0:00:51.20,Default,,0,0,0,,نتيجة كاملة.\nDialogue: 0,0:00:55.00,0:00:58.30,Default,,0,0,0,,جملة لم تنته\nDialogue: 0,0:00:59.00,0:01:01.00,Default,,0,0,0,,خارج الحد.\n")
            result = finish_reel_at_caption_boundary({"start_seconds": 0, "end_seconds": 59}, subtitles)
            self.assertEqual(result["end_seconds"], 51.2)

    def test_missing_captions_preserve_requested_window(self):
        spec = {"start_seconds": 0, "end_seconds": 59}
        self.assertEqual(finish_reel_at_caption_boundary(spec, None), spec)
