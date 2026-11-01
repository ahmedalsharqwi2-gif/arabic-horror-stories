import unittest
from scripts.horror_verification import validate_episode


def episode():
    keywords = ["abandoned hospital night corridor", "old police archive case files", "remote forest road night", "missing person map table", "analog cassette recorder closeup", "empty hotel hallway night", "stormy mountain road documentary"]
    return {
        "title": "قضية موثقة",
        "hook": "بعد آخر تسجيل موثق، بقيت الكاميرا تعمل وحدها.",
        "region": "أوروبا",
        "story_type": "true_case",
        "basis": "تقارير صحفية وسجل رسمي",
        "narration": "قصة موثقة تكشف ما نعرفه وما لا نعرفه.",
        "visual_keywords": keywords,
        "visual_match": [{"keyword": k, "scene": "مشهد مرتبط بالقضية", "place": "المكان الحقيقي", "source_type": "REAL_LOCATION", "authenticity": "REAL_LOCATION", "status": "PASS", "audio_decision": "ORIGINAL AUDIO + VOICE DUCKING", "audio_match": "PASS"} for k in keywords],
        "caption": "رعب حقيقي موثق #رعب_حقيقي",
        "phonetic_hints": [],
        "authenticity_label": "REAL_EVENT",
        "verification_report": {"case_name": "قضية موثقة", "classification": "true_case", "period": "القرن العشرون", "location": "أوروبا", "people": ["شخص موثق"], "facts": ["واقعة موثقة"], "sources": [{"title": "سجل رسمي", "publisher_or_author": "أرشيف", "date": "1990", "url": "https://example.org/a", "tier": "official", "supports": "الواقعة"}, {"title": "صحيفة موثوقة", "publisher_or_author": "صحيفة", "date": "1991", "url": "https://example.org/b", "tier": "reputable_press", "supports": "الواقعة"}], "confirmed_claims": ["الواقعة"], "disputed_claims": [], "excluded_claims": [], "verified_quotes": [], "decision": "APPROVED"},
        "production_table": [{"time": "00:00", "narration": "نص", "scene": "لقطة", "scene_source": "مكان حقيقي", "sound_effect": "صمت", "music": "Room Tone", "subtitle": "نص", "tension": 1}] * 7,
        "final_checks": {"fact_check": "PASS", "visual_check": "PASS", "horror_check": "PASS", "authenticity_check": "PASS", "audio_check": "PASS", "subtitle_check": "PASS", "sensitivity_check": "PASS"},
    }

class HorrorVerificationTests(unittest.TestCase):
    def test_verified_episode_passes(self): validate_episode(episode())
    def test_unlabeled_reenactment_fails(self):
        value = episode(); value["visual_match"][0]["authenticity"] = "REENACTMENT"
        with self.assertRaises(ValueError): validate_episode(value)
    def test_non_horror_caption_fails(self):
        value = episode(); value["caption"] = "قصة عادية #وثائقي"
        with self.assertRaises(ValueError): validate_episode(value)

if __name__ == "__main__": unittest.main()
