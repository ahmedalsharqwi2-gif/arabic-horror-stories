import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from professional_motion import fiction
from professional_motion.editorial import SCHEMA
from api_budget import BudgetExceeded

class HorrorRecoveryTests(unittest.TestCase):
 def draft(self):
  return {'title':'صوت الإنتركم','suitable':True,'plot_signature':'A strange intercom anticipates a visitor and reveals a specific quiet callback at the door.',
   'scenes':[{'narration':'ده صوت الإنتركم اللي سمعته وأنا واقف جنب باب الشقة','visual_mode':'phone','scare_phrase':''} for _ in range(8)],'hashtags':['الإنتركم','باب_الشقة','رعب']}
 def test_optional_expansion_outage_keeps_the_complete_original_draft(self):
  draft=self.draft();ask=Mock(side_effect=[draft,RuntimeError('Editorial provider HTTP 503; current story retained'),{'supported':True,'novel':True,'issues':[]}])
  with tempfile.TemporaryDirectory() as td,patch.object(fiction,'ROOT',Path(td)):
   result=fiction.write({},[],ask,SCHEMA,lambda story,*args:story)
   self.assertEqual(result['scenes'],draft['scenes']);self.assertEqual(ask.call_count,3)
   self.assertTrue(any('original draft retained' in warning for warning in result['editorial_warnings']))
 def test_local_safety_budget_is_not_swallowed_as_an_optional_edit(self):
  ask=Mock(side_effect=[self.draft(),BudgetExceeded('text local safety budget reached')])
  with tempfile.TemporaryDirectory() as td,patch.object(fiction,'ROOT',Path(td)):
   with self.assertRaises(BudgetExceeded):fiction.write({},[],ask,SCHEMA,lambda story,*args:story)
   self.assertEqual(ask.call_count,2)
 def test_targeted_review_uses_a_known_single_seed(self):
  with patch.dict('os.environ',{'HORROR_REVIEW_SEED_KEY':''}):
   candidate=next(r for r in fiction.candidates() if r['variant']=='apartment' and r['motif'].startswith('إنتركم') and r['story_rule'].startswith('تفصيلة'))
  with patch.dict('os.environ',{'HORROR_REVIEW_SEED_KEY':candidate['key']}):
   rows=fiction.candidates();self.assertEqual(len(rows),1);self.assertEqual(rows[0]['key'],candidate['key']);self.assertIn('No delayed reflections',rows[0]['editorial_brief'])

if __name__=='__main__':unittest.main()
