import io
import json
import os
import unittest
from unittest.mock import Mock,patch
import zipfile
from production_v2.diagnose import redact,inspect_zip,Reader,diagnose,MAX_FILE,MAX_DOWNLOAD


def archive(files):
 stream=io.BytesIO()
 with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as zipped:
  for name,value in files.items():zipped.writestr(name,value)
 return stream.getvalue()

class DiagnosticTests(unittest.TestCase):
 def test_redacts_existing_secret_values_and_header_query_patterns(self):
  with patch.dict(os.environ,{'GEMINI_API_KEY':'my-test-secret','GITHUB_TOKEN':'my-git-secret'},clear=True):
   text=redact('RuntimeError my-test-secret my-git-secret Authorization: Bearer other-token https://example.test/?key=unknown-value&x=1')
  for forbidden in ['my-test-secret','my-git-secret','other-token','unknown-value']:self.assertNotIn(forbidden,text)
  self.assertIn('RuntimeError',text)
 def test_only_whitelisted_json_fields_and_selected_error_lines_retained(self):
  raw=archive({'run/planning-errors.json':json.dumps([{'topic_key':'new-topic','validation':'HTTP429 quota exhausted','error_class':'RuntimeError','password':'do-not-retain'}]),'other.json':'{"token":"excluded"}'})
  result=inspect_zip(raw);self.assertEqual(len(result),1);self.assertNotIn('password',json.dumps(result));self.assertNotIn('excluded',json.dumps(result))
  logs=inspect_zip(archive({'job/step.txt':'normal provider output\nRuntimeError: HTTP403 my-test-secret\nnormal done'}),logs=True)
  self.assertEqual(len(logs[0]['error_lines']),1)
 def test_traversal_absolute_and_windows_paths_rejected_without_extraction(self):
  for name in ['../planning-errors.json','/planning-errors.json','C:\\planning-errors.json','safe/../../planning-errors.json']:
   with self.assertRaises(ValueError):inspect_zip(archive({name:'{}'}))
 def test_oversize_selected_member_is_omitted(self):
  result=inspect_zip(archive({'planning-errors.json':'x'*(MAX_FILE+1)}))
  self.assertEqual(result[0]['omitted'],'file_size_limit')
 def test_get_only_reader_does_not_forward_token_to_signed_download(self):
  first=Mock(status_code=302,headers={'Location':'https://storage.example.test/signed?value=one'})
  second=Mock(status_code=200);second.iter_content.return_value=[b'zip-data']
  session=Mock();session.get.side_effect=[first,second]
  reader=Reader('owner/repo','mock-token',session=session)
  self.assertEqual(reader.archive('/actions/runs/123/logs'),b'zip-data')
  self.assertEqual(session.get.call_count,2);self.assertIn('headers',session.get.call_args_list[0].kwargs)
  self.assertNotIn('headers',session.get.call_args_list[1].kwargs)
  session.post.assert_not_called();session.put.assert_not_called();session.delete.assert_not_called()
 def test_download_limit_and_unsafe_redirect_fail_closed(self):
  response=Mock(status_code=200);response.iter_content.return_value=[b'x'*(MAX_DOWNLOAD+1)]
  session=Mock();session.get.return_value=response
  with self.assertRaises(ValueError):Reader('owner/repo','mock-token',session=session).archive('/logs')
  session.get.return_value=Mock(status_code=302,headers={'Location':'http://unsafe.example/logs'})
  with self.assertRaises(ValueError):Reader('owner/repo','mock-token',session=session).archive('/logs')
 def test_actual_prior_run_diagnosis_records_actionable_reason_without_provider_calls(self):
  reader=Mock();reader.json.return_value={'artifacts':[{'id':7,'expired':False}]}
  reader.archive.side_effect=[archive({'generation-failure.json':json.dumps({'error_class':'RuntimeError','reservation_retained':False})}),archive({'step.txt':'RuntimeError: No usable source after HTTP429 quota'})]
  store=Mock();store.save.return_value='a'*40
  env={'GITHUB_REPOSITORY':'ahmedalsharqwi2-gif/documented-history-stories','GITHUB_RUN_ID':'456','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'b'*40}
  with patch.dict(os.environ,env,clear=True):result=diagnose('history','123',reader=reader,store=store)
  self.assertEqual(result['provider_http_statuses'],[429]);self.assertEqual(result['target_run'],'123')
  self.assertTrue(result['no_provider_calls']);self.assertTrue(result['no_posts_created']);store.save.assert_called_once()
 def test_wrong_repository_and_nonnumeric_target_rejected_before_read(self):
  reader=Mock()
  with patch.dict(os.environ,{'GITHUB_REPOSITORY':'other/repo'},clear=True):
   with self.assertRaises(PermissionError):diagnose('history','123',reader=reader)
  with self.assertRaises(ValueError):diagnose('history','123;bad',reader=reader)
  reader.json.assert_not_called()

if __name__=='__main__':unittest.main()
