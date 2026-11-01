"""Resume an exact reserved candidate from retained audio; no text or TTS calls."""
import argparse,hashlib,io,json,os,sys,zipfile
from pathlib import Path,PurePosixPath
from .diagnose import Reader
from .export_review import context
from .ledger import Ledger,encode,Conflict
from .durable import GitLedgerStore
from .generate import isolated_editor,_copy_inputs,_write
from .review import bundle,main as render_review

def retained_delivery(raw,slot):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members=archive.namelist()
        if any(PurePosixPath(n).name=='candidate-review.mp4' for n in members):
            raise Conflict('A full film already exists; inspect retained media instead of rendering a duplicate')
        failures=[n for n in members if PurePosixPath(n).name=='generation-failure.json']
        if len(failures)!=1:raise ValueError('Exact failure evidence required')
        failure=json.loads(archive.read(failures[0]))
        if failure.get('slot')!=slot or failure.get('reservation_retained') is not True:
            raise Conflict('Retained artifact does not match the exact reserved slot')
        names=[n for n in members if n.endswith('/professional_motion/delivery/story.json')]
        if len(names)!=1:raise ValueError('One retained story required')
        prefix=names[0].rsplit('/',1)[0]+'/'
        files={}
        for name in members:
            if not name.startswith(prefix):continue
            relative=PurePosixPath(name[len(prefix):])
            if len(relative.parts)!=1 or relative.name not in ('story.json','narration.wav') and relative.suffix!='.json':continue
            if archive.getinfo(name).file_size>12*1024*1024:raise ValueError('Retained delivery file too large')
            files[relative.name]=archive.read(name)
        for required in ('story.json','narration.wav','narration.source.json'):
            if required not in files:raise ValueError('Complete retained story, audio, provenance and timing required')
        if 'timing.json' not in files:
            from .speech_characters import character_timing
            from professional_motion.alignment import recognized_key
            story=json.loads(files['story.json']);provenance=json.loads(files['narration.source.json'])
            full=' '.join(s['narration'] for s in story['scenes'])
            audio_hash=hashlib.sha256(files['narration.wav']).hexdigest()
            if provenance.get('text')!=full or provenance.get('output_sha256')!=audio_hash:
                raise ValueError('Retained audio provenance mismatch')
            import wave
            with wave.open(io.BytesIO(files['narration.wav'])) as wav:duration=wav.getnframes()/wav.getframerate()
            transcripts=[(m,json.loads(files['asr-'+m+'.json'])['recognized_words']) for m in ('medium','small','large-v3')]
            timing=character_timing(story,duration,transcripts,recognized_key)
            timing.update(story_sha256=hashlib.sha256(files['story.json']).hexdigest(),audio_sha256=audio_hash,profile=story['profile'],topic_key=story['topic_key'])
            files['timing.json']=json.dumps(timing,ensure_ascii=False,indent=2).encode()
        timing=json.loads(files['timing.json'])
        for name,key in [('story.json','story_sha256'),('narration.wav','audio_sha256')]:
            if hashlib.sha256(files[name]).hexdigest()!=timing.get(key):
                raise ValueError('Retained bytes differ from original measured evidence')
        return files

def resume(profile,target_run,slot,run_dir,ledger_path,production=False):
    repository,run,attempt,source=context(profile)
    repo=Path.cwd().resolve();out=Path(run_dir).resolve();database=Path(ledger_path).resolve()
    if out==repo or repo.is_relative_to(out) or any(out.is_relative_to(repo/n) for n in ('state','config','professional_motion','.git')):
        raise ValueError('Use a separate isolated resume directory')
    if out.exists() and any(out.iterdir()):raise FileExistsError('Existing resume outputs are retained')
    if database.is_relative_to(out) or database.suffix!='.sqlite3' or any(database.is_relative_to(repo/n) for n in ('state','config','professional_motion','.git')):
        raise ValueError('Use a separate candidate ledger')
    reader=Reader(repository,os.environ['GITHUB_TOKEN'])
    artifacts=reader.json('/actions/runs/'+str(int(target_run))+'/artifacts').get('artifacts',[])
    expected=profile+'-v2-fresh-candidate-'+str(target_run)
    matches=[a for a in artifacts if a.get('name')==expected and not a.get('expired')]
    if len(matches)!=1:raise ValueError('Exact retained failed candidate artifact required')
    files=retained_delivery(reader.archive('/actions/artifacts/'+str(matches[0]['id'])+'/zip'),slot)
    story=json.loads(files['story.json'])
    if story.get('profile')!=profile:raise Conflict('Retained story belongs to another profile')
    store=GitLedgerStore(repo)
    with store.restore(database):pass
    from professional_motion import editorial,voice_job
    with Ledger(database) as ledger:
        original=[json.loads(r[0]) for r in ledger.db.execute("SELECT payload FROM events WHERE kind='candidate_story'") if json.loads(r[0]).get('slot')==slot]
        reserved=ledger.db.execute('SELECT topic,story_sha256 FROM reservations WHERE slot=?',(slot,)).fetchone()
        identity=hashlib.sha256(encode(story).encode()).hexdigest()
        if len(original)!=1 or original[0].get('story')!=story or not reserved or reserved[1]!=identity:
            raise Conflict('Archive story does not match the durable reservation')
        if ledger.db.execute('SELECT 1 FROM intents WHERE slot=?',(slot,)).fetchone():
            raise Conflict('Publication intent exists; reconcile instead of rendering')
        out.mkdir(parents=True);delivery=out/'professional_motion/delivery';delivery.mkdir(parents=True)
        inputs=_copy_inputs(repo,out)
        for name,data in files.items():(delivery/name).write_bytes(data)
        _write(out/'source-snapshot.json',{'repository':str(repo),'inputs':inputs})
        with ledger.transaction():ledger.event('candidate_resumed',{'slot':slot,'profile':profile,'from_run':str(target_run),'story_sha256':identity,'no_text_or_tts_requests':True})
        store.checkpoint(ledger)
        try:
            # Timing is reconstructed only from retained real ASR, never re-synthesized.
            checked,timing=bundle(delivery,profile)
            renderer={p.relative_to(repo).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for pattern in ('*.js','*.mjs') for p in (repo/'professional_motion').glob(pattern)}
            result={'slot':slot,'profile':profile,'topic_key':story['topic_key'],'duration':timing['duration'],
                    'story_sha256':hashlib.sha256(files['story.json']).hexdigest(),'audio_sha256':hashlib.sha256(files['narration.wav']).hexdigest(),
                    'fresh_topic_verified':True,'generated_in_isolation':True,'resumed_from_run':str(target_run),
                    'generation_origin':'new_generation_from_same_retained_reservation','review_only':not production,'publishable':False,
                    'no_text_or_tts_requests':True,'renderer_source_sha256':renderer}
            _write(out/'generation-verification.json',result)
            old=sys.argv
            try:
                sys.argv=['production_v2.review','--profile',profile,'--delivery-dir',str(delivery),'--output-dir',str(out/'output')]
                if production:sys.argv.append('--production')
                render_review()
            finally:sys.argv=old
            with ledger.transaction():ledger.event('candidate_generated',result)
            store.checkpoint(ledger)
            return result
        except BaseException as error:
            failure={'slot':slot,'profile':profile,'reservation_retained':True,'publishable':False,'error_class':type(error).__name__,'no_text_or_tts_requests':True}
            _write(out/'generation-failure.json',failure)
            with ledger.transaction():ledger.event('candidate_resume_failed',failure)
            store.checkpoint(ledger)
            raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',required=True);p.add_argument('--target-run',required=True,type=int)
    p.add_argument('--slot',required=True);p.add_argument('--run-dir',required=True);p.add_argument('--ledger',required=True)
    p.add_argument('--production',action='store_true')
    a=p.parse_args();print(json.dumps(resume(a.profile,a.target_run,a.slot,a.run_dir,a.ledger,production=a.production),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
