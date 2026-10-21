"""Reversibly hide the superseded upload; retain evidence of any API limitation."""
import json
from pathlib import Path
from googleapiclient.discovery import build
from scripts.publish_youtube_direct import load_credentials
from scripts.audit_publication_delivery import main as audit

result={'superseded_youtube_id':'kSamnxZ_Urc','requested_visibility':'private'}
try:
 yt=build('youtube','v3',credentials=load_credentials())
 updated=yt.videos().update(part='status',body={'id':'kSamnxZ_Urc','status':{'privacyStatus':'private','selfDeclaredMadeForKids':False,'containsSyntheticMedia':True}}).execute()
 result['privacyStatus']=updated.get('status',{}).get('privacyStatus')
 result['hidden']=result['privacyStatus']=='private'
except Exception as exc:
 result.update(hidden=False,error_type=type(exc).__name__)
 if hasattr(exc,'resp'):result['http_status']=getattr(exc.resp,'status',None)
Path('output/superseded-version-status.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
audit()
