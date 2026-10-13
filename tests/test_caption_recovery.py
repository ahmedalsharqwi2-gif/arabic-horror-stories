import ast
import importlib.util
import os
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]

class Repairs(unittest.TestCase):
    def test_real_sentence_recovery_preserves_pauses_and_covers_words(self):
        for repo in ("current",):
            tree = ast.parse((ROOT / "scripts/generate_voice.py").read_text())
            func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "synthesize_voice")
            handler = next(n.handlers[0] for n in func.body if isinstance(n, ast.Try) and any(isinstance(c, ast.Assign) and ast.unparse(c).startswith("all_word_events = align_words") for c in n.body))
            code = compile(ast.Module(body=handler.body, type_ignores=[]), "<recovery>", "exec")
            namespace = {"os": os, "math": math, "exc": RuntimeError("overlapping word timings"), "strip_diacritics": lambda s: s,
                         "segments": [{"duration": 2, "sentence": "هذا نص", "is_silence": False},
                                      {"duration": .5, "is_silence": True},
                                      {"duration": 1, "sentence": "سليم", "is_silence": False}],
                         "display_words": ["هذا", "نص", "سليم"]}
            with patch.dict(os.environ, {"QUALITY_GATES_BLOCKING": "false"}):
                exec(code, namespace)
                self.assertEqual([e["offset"] for e in namespace["all_word_events"]], [0, 1, 2.5])
                namespace["display_words"] = ["نص آخر"]
                with self.assertRaises(RuntimeError): exec(code, namespace)


if __name__ == "__main__": unittest.main()
