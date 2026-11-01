import tempfile
import unittest
from pathlib import Path

from scripts.cinematic_production import captions


class CaptionOverlapTests(unittest.TestCase):
    def test_overlapping_ass_events_do_not_abort(self):
        with tempfile.TemporaryDirectory() as directory:
            ass = Path(directory) / "narration.ass"
            ass.write_text(
                "[Events]\n"
                "Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,أول جملة\n"
                "Dialogue: 0,0:00:01.50,0:00:03.00,Default,,0,0,0,,الجملة الثانية\n"
                "Dialogue: 0,0:00:02.00,0:00:02.01,Default,,0,0,0,,قصيرة\n",
                encoding="utf-8",
            )
            events, method = captions("أول جملة الجملة الثانية قصيرة", 3.0, ass)
            self.assertEqual(method, "existing_audio_timeline")
            self.assertTrue(events)
            self.assertTrue(all(0 <= e["start"] < e["end"] <= 3.0 for e in events))
            self.assertTrue(all(a["end"] <= b["start"] for a, b in zip(events, events[1:])))
            self.assertIn("قصيرة", " ".join(e["text"] for e in events))


if __name__ == "__main__":
    unittest.main()
