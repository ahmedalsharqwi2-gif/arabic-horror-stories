import sys
import types
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.modules.setdefault("edge_tts", types.ModuleType("edge_tts"))

import assemble_video  # noqa: E402
import generate_voice  # noqa: E402


class ReelSafeAreaTests(unittest.TestCase):
    def test_narration_captions_use_bottom_safe_lane_for_horizontal_master(self):
        style = next(line for line in generate_voice.build_ass_header().splitlines() if line.startswith("Style: Caption,"))
        self.assertIn(",2,70,70,70,1", style)

    def test_vertical_narration_captions_are_below_notch(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "narration.ass"
            target = Path(directory) / "narration_vertical.ass"
            source.write_text(generate_voice.build_ass_header(), encoding="utf-8")
            assemble_video.build_vertical_subtitles(source, target)
            rendered = target.read_text(encoding="utf-8")
        self.assertIn("PlayResX: 1080", rendered)
        self.assertIn("PlayResY: 1920", rendered)
        self.assertIn(",8,70,70,300,1", rendered)


if __name__ == "__main__":
    unittest.main()
