"""One bounded schema diagnostic; never creates a production story or voice."""
import hashlib
import json
import os
from pathlib import Path
import requests
from professional_motion import editorial
from .directing import load_catalog, response_schema
from .diagnose import redact
from .export_review import StatusStore, context

def main():
    request=json.loads(Path('.github/provider-probe-request.json').read_text())
    profile=request['profile']
    repository,run,attempt,source=context(profile)
    schema=response_schema(editorial.SCHEMA,load_catalog('.',profile))
    model=editorial.model_name()
    key=(os.getenv('GEMINI_TEXT_API_KEY') or os.getenv('GEMINI_API_KEY') or '').strip()
    if not key:raise RuntimeError('Missing repository writing credential')
    report={'kind':'bounded_provider_schema_probe','profile':profile,'repository':repository,
            'run_id':run,'run_attempt':attempt,'source_commit':source,
            'model':model,'schema_sha256':hashlib.sha256(json.dumps(schema,sort_keys=True).encode()).hexdigest(),
            'provider_requests':0,'story_generated':False,'voice_generated':False,
            'posts_created':False,'cutover_eligible':False}
    payload={'contents':[{'parts':[{'text':'Diagnostic only. Do not write a film. Return an unsuitable result.'}]}],
             'generationConfig':{'responseMimeType':'application/json','responseSchema':schema,
                                 'temperature':0.1,'maxOutputTokens':1}}
    from api_budget import reserve
    reserve('text',model,key)
    report['provider_requests']=1
    response=requests.post('https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent',
                           headers={'x-goog-api-key':key},json=payload,timeout=90)
    report['http_status']=response.status_code
    if response.status_code!=200:
        try:error=response.json().get('error',{})
        except ValueError:error={}
        report['provider_error']={name:redact(error[name])[:3000] for name in ('code','status','message') if name in error}
        report['stage']='failure'
    else:
        report['schema_accepted']=True
        report['stage']='success'
    Path('work').mkdir(exist_ok=True)
    Path('work/provider-schema-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    report['status_commit']=StatusStore('.', 'codex/production-v2-provider-diagnostics').save(run,attempt,report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if report['stage']!='success':raise SystemExit(1)
if __name__=='__main__':main()
