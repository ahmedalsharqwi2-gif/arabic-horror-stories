import unittest
from scripts.narrative_motion import cues_from_captions

class NarrativeCueTests(unittest.TestCase):
    def test_inactive_display_words_cannot_trigger_early_motion(self):
        events=[{'text':'سفينة','start':0.,'end':1.,'ass_text':r'{\pos(1,1)}سفينة'},
                {'text':'قارب','start':0.,'end':1.,'ass_text':r'{\pos(1,1)}قارب'},
                {'text':'سفينة','start':0.,'end':1.,'ass_text':r'{\c&H000000FF&}سفينة'},
                {'text':'قارب','start':2.,'end':3.,'ass_text':r'{\c&H000000FF&}قارب'}]
        scenes=cues_from_captions(events,4.,'horror')
        self.assertEqual(scenes[0]['text'],'سفينة قارب')
        self.assertEqual(scenes[0]['narrative_beats'][-1]['at'],2.)
        self.assertEqual(scenes[0]['narrative_beats'][-1]['kind'],'boat')
        self.assertEqual(scenes[-1]['end'],4.)

    def test_no_measured_timing_is_an_error(self):
        with self.assertRaisesRegex(RuntimeError,'measured'):
            cues_from_captions([{'text':'سفينة','start':0.,'end':3.}],3.,'horror')
