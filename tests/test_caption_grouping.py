import unittest
from arabic_speech_core.ass_text import caption_word_groups, render_arabic_caption


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

    def test_empty_punctuation_and_invalid_limit(self):
        self.assertEqual(caption_word_groups([{"text": "...", "offset": 0, "duration": 1}]), [])
        with self.assertRaises(ValueError):
            caption_word_groups([], 0)
