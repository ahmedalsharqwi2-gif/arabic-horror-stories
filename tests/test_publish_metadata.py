import unittest

from scripts.publish_buffer import build_post_text, ensure_caption_hashtags


class PublishMetadataTests(unittest.TestCase):
    def test_empty_caption_gets_horror_defaults(self):
        text = ensure_caption_hashtags("قصة في الظلام", "")
        self.assertIn("قصة في الظلام", text)
        self.assertIn("#رعب", text)
        self.assertIn("#قصص_رعب", text)

    def test_full_video_removes_shorts_but_keeps_relevant_tags(self):
        text = build_post_text("youtube", "full_video", "عنوان", "#Shorts")
        self.assertNotIn("#Shorts", text)
        self.assertIn("#رعب", text)


if __name__ == "__main__":
    unittest.main()
