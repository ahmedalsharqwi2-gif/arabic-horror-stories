import array,unittest
from remotion_factory.compact_silence import quiet_cuts
class SilentOnlyEditing(unittest.TestCase):
 def test_every_removed_sample_is_quiet_and_pauses_survive(self):
  rate=1000;samples=array.array('h',[2000]*2000+[0]*800+[2000]*2000+[0]*900+[2000]*2000)
  cuts,limit=quiet_cuts(samples,rate,1,1000)
  self.assertEqual(sum(b-a for a,b in cuts),1000)
  for a,b in cuts:self.assertTrue(all(abs(x)<=limit for x in samples[a:b]))
  self.assertTrue(all(b-a<=680 for a,b in cuts))
 def test_speech_is_never_removed_to_hit_a_duration_target(self):
  with self.assertRaises(ValueError):quiet_cuts(array.array('h',[2000]*5000),1000,1,1000)
 def test_quiet_cuts_cannot_spend_more_silence_than_available(self):
  with self.assertRaises(ValueError):quiet_cuts(array.array('h',[0]*700+[2000]*5000),1000,1,600)
