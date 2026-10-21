import unittest
import numpy as np
from scripts.immersive_sound import cue_events,ambience

class ImmersiveSoundTests(unittest.TestCase):
    def test_cannon_cue_is_not_restarted_at_each_scene_boundary(self):
        scenes=[{'start':0,'narrative_beats':[{'at':2,'origin':2,'kind':'cannon','word':'مدافع'}]},
                {'start':6,'narrative_beats':[{'at':0,'origin':2,'kind':'cannon','word':''}]}]
        self.assertEqual(cue_events(scenes),[{'at':2.,'kind':'cannon','word':'مدافع'}])

    def test_effect_waits_for_spoken_event_and_does_not_clip(self):
        bed,fx=ambience(5,'history',[{'kind':'cannon','at':2.,'word':'مدافع'}])
        self.assertEqual(fx.shape,(120000,2))
        self.assertFalse(np.any(fx[:48000]))
        self.assertTrue(np.any(fx[50000:]))
        self.assertLess(float(np.max(np.abs(fx))),.5)
        self.assertTrue(np.all(np.isfinite(bed)))
