import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from scripts.offline_explainer import render_explainer


class OfflineExplainerTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg required")
    def test_real_video_contains_only_narration_and_correct_streams(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "scene.mp4"
            text = "هذه مدينة قديمة وكانت تستخدم الأدوات الحجرية"
            render_explainer(path, 2.1, {"text": text}, {"width": 360, "height": 640, "fps": 30, "profile": "history"})
            result = subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], text=True)
            data = json.loads(result)
            video = next(stream for stream in data["streams"] if stream["codec_type"] == "video")
            audio = next(stream for stream in data["streams"] if stream["codec_type"] == "audio")
            self.assertEqual((video["width"], video["height"]), (360, 640))
            self.assertEqual(audio["channels"], 2)
            self.assertAlmostEqual(float(data["format"]["duration"]), 2.1, delta=0.15)
            # The replacement is real original artwork, rather than a flat text fallback.
            import io
            from PIL import Image,ImageStat
            png=subprocess.check_output(["ffmpeg","-v","error","-ss","1","-i",str(path),"-frames:v","1","-f","image2pipe","-vcodec","png","-"])
            frame=Image.open(io.BytesIO(png)).convert("RGB")
            self.assertGreater(max(ImageStat.Stat(frame.crop((30,210,330,450))).stddev),10)


    def test_empty_narration_is_never_replaced_with_unrelated_text(self):
        with self.assertRaises(ValueError):
            render_explainer(Path("unused.mp4"), 2, {"text": ""}, {})


if __name__ == "__main__":
    unittest.main()
