"""Exercise the actual async recovery function without loading speech models."""
import ast
import asyncio
import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch


class VoiceRecoveryTests(unittest.TestCase):
    def load_recovery(self, engine="edge"):
        path = Path(__file__).resolve().parents[1] / "scripts/generate_voice.py"
        if not path.exists():
            path = Path(__file__).with_name("horror_generate_voice.py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "synthesize_with_recovery")
        namespace = {"os": os, "TTS_ENGINE": engine,
                     "synthesize_sentences": AsyncMock(side_effect=[RuntimeError("Edge 403"), [{"path": "local.mp3"}]]),
                     "configure_silma_voice_profile": Mock()}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
        return namespace

    def test_edge_failure_uses_one_local_attempt(self):
        ns = self.load_recovery()
        with patch.dict(os.environ, {"EDGE_FALLBACK_TO_SILMA": "true"}):
            segments, engine = asyncio.run(ns["synthesize_with_recovery"](["نص عربي."]))
        self.assertEqual(engine, "silma")
        self.assertEqual(segments[0]["path"], "local.mp3")
        self.assertEqual(ns["synthesize_sentences"].await_count, 2)
        ns["configure_silma_voice_profile"].assert_called_once()

    def test_local_failure_does_not_cycle_back_to_edge(self):
        ns = self.load_recovery("silma")
        with self.assertRaises(RuntimeError):
            asyncio.run(ns["synthesize_with_recovery"](["نص."]))
        self.assertEqual(ns["synthesize_sentences"].await_count, 1)

    def test_disabled_fallback_is_respected(self):
        ns = self.load_recovery()
        with patch.dict(os.environ, {"EDGE_FALLBACK_TO_SILMA": "false"}), self.assertRaises(RuntimeError):
            asyncio.run(ns["synthesize_with_recovery"](["نص."]))
        ns["configure_silma_voice_profile"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
