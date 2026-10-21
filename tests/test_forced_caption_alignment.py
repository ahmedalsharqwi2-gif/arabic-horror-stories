"""Caption alignment must measure valid boundaries, even after a model retry."""
import types
import unittest
from unittest.mock import patch
from scripts.forced_caption_alignment import align_worker, validate_events


class ForcedCaptionAlignmentTests(unittest.TestCase):
    def test_overlapping_and_zero_length_words_are_rejected(self):
        for events in (
            [{'text':'ده','start':0,'end':0}],
            [{'text':'ده','start':0,'end':.8}, {'text':'اختبار','start':.4,'end':1}],
        ):
            with self.assertRaises(RuntimeError):
                validate_events(events, [e['text'] for e in events], 1)

    def test_larger_local_model_must_pass_the_same_timing_gate(self):
        attempted = []
        def load(size, **kwargs):
            attempted.append(size)
            events = [(0, 0), (.4, .8)] if size == 'small' else [(0, .4), (.4, .8)]
            words = [types.SimpleNamespace(word=text, start=start, end=end)
                     for text, (start,end) in zip(['ده','اختبار'], events)]
            return types.SimpleNamespace(align=lambda *a, **k: types.SimpleNamespace(
                segments=[types.SimpleNamespace(words=words)]))
        modules = {
            'stable_whisper': types.SimpleNamespace(load_faster_whisper=load),
            'torch': types.SimpleNamespace(set_num_threads=lambda n: None),
        }
        with patch.dict('sys.modules', modules), patch(
            'scripts.forced_caption_alignment.subprocess.run',
            return_value=types.SimpleNamespace(stdout='1.0')
        ):
            result = align_worker('voice.mp3', ['ده','اختبار'])
        self.assertEqual(attempted, ['small','medium'])
        self.assertEqual(result[0]['end'], .4)
        self.assertEqual(len(validate_events(result, ['ده','اختبار'], 1)), 2)
