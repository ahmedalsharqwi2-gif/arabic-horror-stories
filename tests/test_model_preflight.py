import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch


class ModelPolicyTests(unittest.TestCase):
    def test_policy_has_one_shared_schema_and_provider_order(self):
        policy = json.loads(Path("config/model_policy.json").read_text(encoding="utf-8"))
        self.assertEqual(policy["schema_version"], 1)
        self.assertEqual(list(policy["providers"]), ["gemini", "fallback", "openrouter"])
        for provider in policy["providers"].values():
            self.assertTrue(provider["preferred_models"])
            self.assertIn(503, provider["retry_statuses"])
        groq = policy["providers"]["fallback"]
        self.assertEqual(groq["preferred_models"], ["openai/gpt-oss-120b"])
        self.assertTrue({"openai/gpt-oss-20b", "llama-3.1-8b-instant", "llama-3.3-70b-versatile"}
                        .issubset(set(groq["excluded_models"])))
        self.assertIn("inclusionai/ling-3.1-flash", policy["providers"]["openrouter"]["excluded_models"])


    def test_select_never_returns_unlisted_or_stale_default(self):
        from scripts.model_preflight import select
        self.assertEqual(select(["old-model"], [], [], "old-model"), ("", []))
        self.assertEqual(select(["old-model"], [], ["new-model"], "old-model"), ("new-model", []))
        self.assertEqual(
            select(["old-model", "good-model"], [], ["old-model", "good-model"],
                   excluded=["old-model"]),
            ("good-model", []),
        )

    def test_preflight_is_importable_without_third_party_dependencies(self):
        import scripts.model_preflight as preflight
        self.assertEqual(preflight.DEFAULT_GEMINI, "gemma-4-26b-a4b-it")
        self.assertEqual(preflight.DEFAULT_FALLBACK, "openai/gpt-oss-120b")

    def test_gemini_discovery_uses_only_policy_approved_catalog_models(self):
        import scripts.model_preflight as preflight
        policy = {"providers": {"gemini": {"preferred_models": [
            "gemma-4-26b-a4b-it", "gemma-4-31b-it",
        ]}}}
        responses = [
            (200, {"models": [
                {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemma-4-26b-a4b-it", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemma-4-31b-it", "supportedGenerationMethods": ["generateContent"]},
            ]}),
            (200, {"supportedGenerationMethods": ["generateContent"]}),
            (200, {"supportedGenerationMethods": ["generateContent"]}),
        ]
        requested = []
        def fake_request(url, headers=None):
            requested.append(url)
            return responses.pop(0)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False), \
             patch.object(preflight, "request_json", side_effect=fake_request):
            selected, fallbacks = preflight.discover_gemini(policy)

        self.assertEqual(selected, "gemma-4-26b-a4b-it")
        self.assertEqual(fallbacks, ["gemma-4-31b-it"])
        self.assertFalse(any("gemini-2.5-flash" in url for url in requested))

    def test_groq_403_catalog_uses_policy_fallback_candidates(self):
        import scripts.model_preflight as preflight
        with patch.dict(os.environ, {"GROQ_MODEL": "openai/gpt-oss-20b"}, clear=False), \
             patch.object(preflight, "request_json", return_value=(403, {})):
            selected, fallbacks = preflight.discover_openai_provider(
                "Fallback", "https://api.groq.com/openai/v1/chat/completions",
                "test-key", ["openai/gpt-oss-120b"],
                ("GROQ_MODEL",), "unused-default",
                excluded_models=["openai/gpt-oss-20b"],
            )
        self.assertEqual(selected, "openai/gpt-oss-120b")
        self.assertEqual(fallbacks, [])

    def test_groq_catalog_selection_ignores_models_outside_approved_policy(self):
        import scripts.model_preflight as preflight
        catalog = {"data": [
            {"id": "openai/gpt-oss-120b"},
            {"id": "openai/gpt-oss-20b"},
            {"id": "llama-3.1-8b-instant"},
            {"id": "llama-3.3-70b-versatile"},
        ]}
        with patch.dict(os.environ, {"GROQ_MODEL": "openai/gpt-oss-20b"}, clear=False), \
             patch.object(preflight, "request_json", return_value=(200, catalog)):
            selected, fallbacks = preflight.discover_openai_provider(
                "Fallback", "https://api.groq.com/openai/v1/chat/completions",
                "test-key", ["openai/gpt-oss-120b"],
                ("GROQ_MODEL",), "unused-default",
                excluded_models=["openai/gpt-oss-20b", "llama-3.1-8b-instant",
                                 "llama-3.3-70b-versatile"],
            )
        self.assertEqual(selected, "openai/gpt-oss-120b")
        self.assertEqual(fallbacks, [])


if __name__ == "__main__":
    unittest.main()
