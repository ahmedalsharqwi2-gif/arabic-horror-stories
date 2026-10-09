import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.modules.setdefault("edge_tts", types.ModuleType("edge_tts"))

import generate_script  # noqa: E402
from generate_voice import normalize_min_min_pronunciation  # noqa: E402


class GenerateScriptTests(unittest.TestCase):
    def test_prompt_requires_complete_vertical_story_under_three_minutes(self):
        prompt = (ROOT / "prompts" / "horror_system_prompt.md").read_text(encoding="utf-8")
        self.assertIn("لا تقسّم القصة إلى أجزاء", prompt)
        self.assertIn("180 ثانية", prompt)
        self.assertIn("150 إلى 240 كلمة", prompt)
        self.assertNotIn("مقتطف الريل", prompt)
        runtime_prompt = generate_script.build_user_message([], [], [])
        self.assertIn("لا يتجاوز 180 ثانية", runtime_prompt)
        self.assertIn("150 إلى 240 كلمة", runtime_prompt)
        self.assertNotIn("مقتطف الريل", runtime_prompt)

    def test_content_red_flag_checker_runs_and_detects_flag(self):
        self.assertIsNone(generate_script.find_content_red_flag("نص عربي سليم."))
        self.assertEqual(
            generate_script.find_content_red_flag("هذا البركان الثلجي غير موثق."),
            "البركان الثلجي",
        )

    def test_rejects_unanswered_question_as_final_sentence(self):
        self.assertTrue(generate_script.looks_open_ended("بدأت القصة هنا. ماذا حدث بعد ذلك؟"))
        self.assertFalse(generate_script.looks_open_ended("بدأت القصة هنا. ثم انطفأ الضوء وانتهى كل شيء."))

    def test_digits_are_nonfatal_in_episode_validation(self):
        episode = {
            "narration": ("في عام 1996 ظهرت إشارة غامضة ثم اختفت. " * 30).strip(),
            "hook": "إشارة غامضة ظهرت في الليل",
            "visual_keywords": ["night radio telescope"] * 6,
        }
        generate_script.validate_episode(episode)

    def test_short_latin_noise_is_removed(self):
        episode = {
            "narration": ("ظهرت إشارة XJ في السماء ثم اختفت J. " * 30).strip(),
            "hook": "إشارة غامضة ظهرت في الليل",
            "visual_keywords": ["night radio telescope"] * 6,
        }
        generate_script.validate_episode(episode)
        self.assertNotIn("XJ", episode["narration"])

    def test_canonical_min_min_pronunciation(self):
        self.assertEqual(normalize_min_min_pronunciation("بحيرة مِينَ مِين"), "بحيرة مِين مِين")

    def test_permanent_topic_history_is_loaded_and_prompted_as_json_data(self):
        with tempfile.TemporaryDirectory() as directory:
            history_path = Path(directory) / "topic_history.json"
            generate_script.TopicHistory(history_path).reserve(
                {"title": "اختفاء سفينة في بحر الشمال", "hook": "لغز اختفاء السفينة في بحر الشمال"}
            )
            with patch.object(generate_script, "TOPIC_HISTORY_PATH", history_path), patch.object(
                generate_script, "_history", return_value=[]
            ):
                self.assertIn("اختفاء سفينة في بحر الشمال", generate_script.load_used_history())
        prompt = generate_script.build_user_message(["عنوان سابق"], [], [])
        self.assertIn("بيانات لتجنب التكرار", prompt)
        self.assertIn('["عنوان سابق"]', prompt)


if __name__ == "__main__":
    unittest.main()
