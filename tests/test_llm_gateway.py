import time
import unittest
from unittest.mock import patch

from scripts import llm_gateway
from scripts.llm_gateway import (
    EPISODE_SCHEMA,
    OutputError,
    Provider,
    ProviderTimeout,
    _run_with_timeout,
    generate_valid_episode,
    make_validator,
    make_validator,
    parse_episode_json,
)


class LlmGatewayTests(unittest.TestCase):
    def test_episode_schema_is_fully_strict_for_structured_output_providers(self):
        def assert_strict(node):
            if node.get("type") == "object":
                properties = node.get("properties", {})
                self.assertIs(node.get("additionalProperties"), False)
                self.assertEqual(set(node.get("required", [])), set(properties))
                for child in properties.values():
                    assert_strict(child)
            if node.get("type") == "array":
                assert_strict(node["items"])

        self.assertTrue(EPISODE_SCHEMA["strict"])
        assert_strict(EPISODE_SCHEMA["schema"])

    def test_short_episode_retry_includes_prior_narration_and_missing_words(self):
        short = {
            "title": "x", "hook": "هوك", "region": "مكان", "story_type": "true_case",
            "basis": "مصدر", "narration": "كلمة " * 10,
            "visual_keywords": ["night radio telescope"] * 7,
            "visual_match": [{"keyword": "night radio telescope"}] * 7,
            "caption": "قصة #رعب", "phonetic_hints": [],
            "verification_report": {}, "production_table": [], "authenticity_label": "REAL_EVENT", "final_checks": {"fact_check": "PASS", "visual_check": "PASS", "horror_check": "PASS", "authenticity_check": "PASS", "audio_check": "PASS", "subtitle_check": "PASS", "sensitivity_check": "PASS"},
        }
        full = dict(short, narration="كلمة " * 230)
        calls = []

        # Use JSON so parse_episode_json receives a real object.
        import json
        def json_provider(_system, user, _budget):
            calls.append(user)
            return json.dumps(short if len(calls) == 1 else full, ensure_ascii=False)

        episode, label = generate_valid_episode(
            "system", "request", 1000, [Provider("test", json_provider)],
            make_validator(), sleep=lambda _seconds: None,
        )
        self.assertEqual(label, "test")
        self.assertEqual(len(episode["narration"].split()), 230)
        self.assertIn("كلمة", calls[1])
        self.assertIn("أضف", calls[1])
    def test_parse_episode_json_removes_fence_and_think_block(self):
        raw = '<think>internal</think>\n```json\n{"title": "x"}\n```'
        self.assertEqual(parse_episode_json(raw), {"title": "x"})

    def test_parse_episode_json_rejects_truncated_json(self):
        with self.assertRaises(OutputError) as ctx:
            parse_episode_json('{"title": "x"')
        self.assertTrue(ctx.exception.truncated)

    def test_http_400_is_permanent_but_503_is_transient(self):
        invalid = RuntimeError("bad request")
        invalid.status_code = 400
        transient = RuntimeError("service unavailable")
        transient.status_code = 503
        self.assertEqual(llm_gateway.classify(invalid), "permanent")
        self.assertEqual(llm_gateway.classify(transient), "transient")

    def test_validator_rejects_unknown_story_type(self):
        episode = {
            "title": "اختبار",
            "hook": "في عام 2090 وصلت إشارة قبل إرسالها",
            "region": "الفضاء",
            "story_type": "science_fiction",
            "basis": "الاتصالات الراديوية",
            "narration": " ".join(["إشارة"] * 230) + ".",
            "visual_keywords": ["night radio station"] * 7,
            "visual_match": [{"keyword": "night radio station"}] * 7,
            "caption": "قصة رعب #رعب",
            "verification_report": {}, "production_table": [], "authenticity_label": "REAL_EVENT", "final_checks": {"fact_check": "PASS", "visual_check": "PASS", "horror_check": "PASS", "authenticity_check": "PASS", "audio_check": "PASS", "subtitle_check": "PASS", "sensitivity_check": "PASS"},
            "phonetic_hints": [],
        }
        with self.assertRaises(OutputError):
            make_validator()(episode)

    def test_invalid_phonetic_hint_is_nonfatal(self):
        episode = {
            "title": "اختبار",
            "hook": "إشارة غريبة وصلت من السماء",
            "region": "أتاكاما",
            "story_type": "true_case",
            "basis": "تقرير علمي منشور",
            "narration": " ".join(["إشارة"] * 230) + ".",
            "visual_keywords": ["night sky radio telescope"] * 7,
            "visual_match": [{"keyword": "night sky radio telescope"}] * 7,
            "caption": "قصة غامضة #رعب",
            "verification_report": {}, "production_table": [], "authenticity_label": "REAL_EVENT", "final_checks": {"fact_check": "PASS", "visual_check": "PASS", "horror_check": "PASS", "authenticity_check": "PASS", "audio_check": "PASS", "subtitle_check": "PASS", "sensitivity_check": "PASS"},
            "phonetic_hints": [{"word": "Flannan", "phonetic": "فلانان"}],
        }
        make_validator()(episode)
        self.assertEqual(episode["phonetic_hints"], [])

    def test_build_providers_rotates_openrouter_models(self):
        with patch.object(llm_gateway, "GEMINI_API_KEY", ""), \
             patch.object(llm_gateway, "GROQ_API_KEY", ""), \
             patch.object(llm_gateway, "OPENROUTER_API_KEY", "test-key"), \
             patch.object(llm_gateway, "OPENROUTER_MODELS", ["model-a", "model-b"]):
            providers = llm_gateway.build_providers()
        self.assertEqual([p.label for p in providers], ["openrouter:model-a", "openrouter:model-b"])

    def test_default_provider_order_puts_groq_before_openrouter(self):
        with patch.object(llm_gateway, "GEMINI_API_KEY", "gemini-key"), \
             patch.object(llm_gateway, "GEMINI_MODELS", ["gemini-model"]), \
             patch.object(llm_gateway, "GROQ_API_KEY", "groq-key"), \
             patch.object(llm_gateway, "GROQ_MODEL", "openai/gpt-oss-120b"), \
             patch.object(llm_gateway, "GROQ_MODELS", ["openai/gpt-oss-120b"]), \
             patch.object(llm_gateway, "OPENROUTER_API_KEY", "router-key"), \
             patch.object(llm_gateway, "OPENROUTER_MODELS", ["router-model"]), \
             patch.dict("os.environ", {"PREFER_OPENROUTER": "false"}):
            providers = llm_gateway.build_providers()
        self.assertEqual(
            [p.label for p in providers],
            ["gemini:gemini-model", "groq:openai/gpt-oss-120b", "openrouter:router-model"],
        )

    def test_groq_models_are_rotated_as_independent_providers(self):
        with patch.object(llm_gateway, "GEMINI_API_KEY", ""), \
             patch.object(llm_gateway, "GROQ_API_KEY", "groq-key"), \
             patch.object(llm_gateway, "GROQ_MODELS", ["model-a", "model-b"]), \
             patch.object(llm_gateway, "OPENROUTER_API_KEY", ""):
            providers = llm_gateway.build_providers()
        self.assertEqual([p.label for p in providers], ["groq:model-a", "groq:model-b"])

    def test_rate_limit_honors_retry_after_then_retries_same_model(self):
        from types import SimpleNamespace
        calls = []
        waits = []

        def rate_then_success(_system, _user, _budget):
            calls.append("groq")
            if len(calls) == 1:
                error = RuntimeError("Groq HTTP 429: rate limit")
                error.status_code = 429
                error.response = SimpleNamespace(headers={"Retry-After": "7"}, text="rate limit")
                raise error
            return '{"ok":true}'

        with patch.object(llm_gateway, "LLM_RETRIES", 3), \
             patch.object(llm_gateway, "LLM_DEADLINE_SECONDS", 10):
            episode, label = llm_gateway.generate_valid_episode(
                "system", "request", 1000,
                [Provider("groq:model", rate_then_success, family="groq")],
                lambda _ep: None, sleep=waits.append,
            )
        self.assertEqual(episode, {"ok": True})
        self.assertEqual(label, "groq:model")
        self.assertEqual(calls, ["groq", "groq"])
        self.assertEqual(waits, [7.0])

    def test_daily_429_skips_sibling_models_for_same_provider_key(self):
        calls = []

        def daily_limit(_system, _user, _budget):
            calls.append("router:first")
            error = RuntimeError("OpenRouter HTTP 429: free-models-per-day limit reached")
            error.status_code = 429
            raise error

        def sibling(_system, _user, _budget):
            calls.append("router:sibling")
            return '{"wrong":true}'

        def next_provider(_system, _user, _budget):
            calls.append("groq")
            return '{"ok":true}'

        providers = [
            Provider("openrouter:first", daily_limit, family="openrouter"),
            Provider("openrouter:sibling", sibling, family="openrouter"),
            Provider("groq:model", next_provider, family="groq"),
        ]
        episode, _ = llm_gateway.generate_valid_episode(
            "system", "request", 1000, providers, lambda _ep: None,
            sleep=lambda _seconds: None,
        )
        self.assertEqual(episode, {"ok": True})
        self.assertEqual(calls, ["router:first", "groq"])

    def test_402_credit_error_disables_all_models_for_provider_key(self):
        calls = []

        def out_of_credits(_system, _user, _budget):
            calls.append("router:first")
            error = RuntimeError("OpenRouter HTTP 402: requires more credits")
            error.status_code = 402
            raise error

        def sibling(_system, _user, _budget):
            calls.append("router:sibling")
            return '{"wrong":true}'

        def next_provider(_system, _user, _budget):
            calls.append("groq")
            return '{"ok":true}'

        providers = [
            Provider("openrouter:first", out_of_credits, family="openrouter"),
            Provider("openrouter:sibling", sibling, family="openrouter"),
            Provider("groq:model", next_provider, family="groq"),
        ]
        episode, _ = llm_gateway.generate_valid_episode(
            "system", "request", 1000, providers, lambda _ep: None,
            sleep=lambda _seconds: None,
        )
        self.assertEqual(episode, {"ok": True})
        self.assertEqual(calls, ["router:first", "groq"])

    def test_400_and_404_disable_only_the_bad_model(self):
        calls = []

        def bad_model(status):
            def fail(_system, _user, _budget):
                calls.append(status)
                error = RuntimeError(f"Groq HTTP {status}: model unavailable")
                error.status_code = status
                raise error
            return fail

        def good_model(_system, _user, _budget):
            calls.append("good")
            return '{"ok":true}'

        providers = [
            Provider("groq:400-model", bad_model(400), family="groq"),
            Provider("groq:404-model", bad_model(404), family="groq"),
            Provider("groq:good-model", good_model, family="groq"),
        ]
        episode, _ = llm_gateway.generate_valid_episode(
            "system", "request", 1000, providers, lambda _ep: None,
            sleep=lambda _seconds: None,
        )
        self.assertEqual(episode, {"ok": True})
        self.assertEqual(calls, [400, 404, "good"])

    def test_credit_error_is_classified_as_quota(self):
        self.assertEqual(llm_gateway.classify(RuntimeError("OpenRouter HTTP 402: requires more credits")), "quota")
        self.assertEqual(llm_gateway.classify(RuntimeError("HTTP 429 free-models-per-day limit reached")), "quota")

    def test_duplicate_feedback_is_carried_to_next_provider(self):
        calls = []

        def duplicate(_system, user, _budget):
            calls.append(user)
            raise OutputError("الموضوع مكرر أو قريب جدًا من موضوع سابق")

        def next_provider(_system, user, _budget):
            calls.append(user)
            return '{"title":"new"}'

        episode, label = generate_valid_episode(
            "system", "request", 1000,
            [Provider("duplicate", duplicate), Provider("next", next_provider)],
            lambda _ep: None, sleep=lambda _seconds: None,
        )
        self.assertEqual((episode, label), ({"title": "new"}, "next"))
        self.assertIn("مختلفة جذريًا", calls[-1])

    def test_quota_provider_is_not_recreated_between_rounds(self):
        calls = []
        def no_credit(_system, _user, _budget):
            calls.append("paid")
            error = RuntimeError("HTTP 402 insufficient credits")
            error.status_code = 402
            raise error
        def invalid_then_valid(_system, _user, _budget):
            calls.append("working")
            if calls.count("working") == 1:
                raise llm_gateway.OutputError("invalid content")
            return '{"story_type": "true_case"}'
        providers = [Provider("paid", no_credit, family="paid"),
                     Provider("working", invalid_then_valid)]
        with patch.object(llm_gateway, "build_providers", return_value=providers) as build, \
             patch.object(llm_gateway, "pick_story_type", return_value="true_case"), \
             patch.object(llm_gateway, "LLM_INVALID_RETRIES", 1):
            result = llm_gateway.generate_episode("system", 1000, lambda ep: None,
                rounds=2, cooldown=0, user_message="project context")
        self.assertEqual(result["story_type"], "true_case")
        self.assertEqual(calls, ["paid", "working", "working"])
        self.assertEqual(build.call_count, 1)

    def test_groq_truncated_schema_400_is_recoverable(self):
        error = RuntimeError("HTTP 400 max completion tokens reached before generating a valid document")
        error.status_code = 400
        self.assertEqual(llm_gateway.classify(error), "invalid")

    def test_duplicate_topic_starts_a_fresh_generation_round(self):
        prompts = []

        def generate_once(_system, user, _budget, _providers, _validate):
            prompts.append(user)
            if len(prompts) == 1:
                raise RuntimeError("فشل كل المزوّدين: الموضوع مكرر")
            return {"title": "موضوع جديد"}, "next"

        with patch.object(llm_gateway, "build_providers", return_value=[]), \
             patch.object(llm_gateway, "generate_valid_episode", side_effect=generate_once), \
             patch.object(llm_gateway.time, "sleep"):
            episode = llm_gateway.generate_episode(
                "system", 1000, lambda _episode: None,
                rounds=2, cooldown=0,
            )

        self.assertEqual(episode["title"], "موضوع جديد")
        self.assertIn("إعادة اختيار إلزامية", prompts[1])
        self.assertIn("الموضوع مكرر", prompts[1])

    def test_blocking_provider_call_has_hard_timeout(self):
        with self.assertRaises(ProviderTimeout):
            _run_with_timeout(lambda: time.sleep(2), 1, "test-provider")


if __name__ == "__main__":
    unittest.main()
