import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
_edge_tts = types.ModuleType("edge_tts")
_edge_tts.Communicate = lambda *args, **kwargs: None
sys.modules.setdefault("edge_tts", _edge_tts)

spec = importlib.util.spec_from_file_location(
    "horror_hybrid_caption_rtl_test", ROOT / "scripts" / "hybrid_vertical_pipeline.py"
)
pipeline = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pipeline
spec.loader.exec_module(pipeline)


class HorrorHybridCaptionRTLTests(unittest.TestCase):
    def test_words_are_positioned_right_to_left_and_highlighted_individually(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "captions.ass"
            pipeline.write_ass(
                [{"text": "أين اختفت هذه؟", "start": 0.0, "end": 1.5}], target
            )
            content = target.read_text(encoding="utf-8")

        dialogue = [line for line in content.splitlines() if line.startswith("Dialogue:")]
        payloads = [line.split(",", 9)[9] for line in dialogue]
        self.assertEqual(len(dialogue), 9)
        first_interval = payloads[:3]
        self.assertEqual(
            [payload.rsplit("}", 1)[-1] for payload in first_interval],
            ["أين", "اختفت", "هذه"],
        )
        centers = [int(payload.split("pos(", 1)[1].split(",", 1)[0]) for payload in first_interval]
        self.assertTrue(all(left > right for left, right in zip(centers, centers[1:])))
        self.assertIn("H000000FF&", first_interval[0])
        self.assertNotIn("H000000FF&", first_interval[1])


if __name__ == "__main__":
    unittest.main()
