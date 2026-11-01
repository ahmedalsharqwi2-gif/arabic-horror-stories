import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from arabic_speech_core.ass_text import caption_word_groups, render_active_arabic_caption, render_arabic_caption


class CaptionGroupingTests(unittest.TestCase):
    def test_punctuation_joined_words_obey_display_limit_and_keep_timing(self):
        events = [{"text": "واحد-اثنان/ثلاثة", "offset": 2.0, "duration": 3.0},
                  {"text": "أربعة", "offset": 5.0, "duration": 1.0},
                  {"text": "خمسة ستة سبعة ثمانية", "offset": 6.0, "duration": 4.0}]
        groups = caption_word_groups(events, 6)
        self.assertEqual([len(g) for g in groups], [6, 2])
        self.assertEqual([e["text"] for g in groups for e in g],
                         "واحد اثنان ثلاثة أربعة خمسة ستة سبعة ثمانية".split())
        self.assertEqual(groups[0][0]["offset"], 2.0)
        self.assertEqual(groups[1][0]["offset"], 8.0)
        self.assertEqual(groups[-1][-1]["offset"] + groups[-1][-1]["duration"], 10.0)
        for group in groups:
            self.assertLessEqual(len(render_arabic_caption([e["text"] for e in group]).replace(r"\N", " ").split()), 6)
        self.assertEqual(events[0]["text"], "واحد-اثنان/ثلاثة")

    def test_active_word_payloads_are_individually_positioned_rtl(self):
        words = "الشعاب المرجانية تحمي السواحل".split()
        payloads = render_active_arabic_caption(words, 1, canvas_width=1080, center_y=500)
        self.assertEqual([payload.rsplit("}", 1)[-1] for payload in payloads], words)
        centers = [int(payload.split("pos(", 1)[1].split(",", 1)[0]) for payload in payloads]
        self.assertTrue(all(left > right for left, right in zip(centers, centers[1:])))
        self.assertIn("H000000FF&", payloads[1])
        self.assertTrue(all("H000000FF&" not in payload for i, payload in enumerate(payloads) if i != 1))

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required for visual subtitle rendering")
    def test_ffmpeg_places_the_first_highlighted_arabic_word_on_the_right(self):
        words = "الشعاب المرجانية تحمي السواحل".split()
        payloads = render_active_arabic_caption(words, 0, canvas_width=1080, center_y=960)
        with tempfile.TemporaryDirectory() as folder:
            ass = Path(folder) / "rtl.ass"
            png = Path(folder) / "rtl.png"
            header = (
                "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\n\n"
                "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
                "Style: Caption,Noto Naskh Arabic,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,3,0,8,70,70,300,1\n\n"
                "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            )
            lines = [f"Dialogue: 0,0:00:00.00,0:00:01.00,Caption,,0,0,0,,{payload}" for payload in payloads]
            ass.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=1:r=1", "-vf", f"subtitles={ass}", "-frames:v", "1", str(png)],
                check=True, capture_output=True,
            )
            image = Image.open(png).convert("RGB")
            pixels = image.load()
            left_red = right_red = 0
            for y in range(850, 1070):
                for x in range(80, 1000):
                    red, green, blue = pixels[x, y]
                    if red > 170 and green < 100 and blue < 100:
                        if x < 540:
                            left_red += 1
                        else:
                            right_red += 1
        self.assertGreater(right_red, 0)
        self.assertEqual(left_red, 0)

    def test_empty_punctuation_and_invalid_limit(self):
        self.assertEqual(caption_word_groups([{"text": "...", "offset": 0, "duration": 1}]), [])
        with self.assertRaises(ValueError):
            caption_word_groups([], 0)
