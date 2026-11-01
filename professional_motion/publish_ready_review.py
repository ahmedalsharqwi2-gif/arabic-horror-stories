"""One authorized immutable review; does not enable daily publication."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from .editorial import registry,save
from .publisher import preflight
from .policy import require_duration
from film_factory.buffer import ContentPublisher
from scripts.publication_state import accepted_receipt,require_services,confirm_stock
ROOT=Path(__file__).resolve().parent
CONFIG=Path(os.getenv('APPROVED_PUBLICATION_CONFIG','config/approved_review_publication.json'))

def validate(grant,video,report,story_bytes):
    if grant.get('approved') is not True or grant.get('profile') not in ('science','horror','history','news'):raise PermissionError('No approval for this film')
    checksum=hashlib.sha256(video.read_bytes()).hexdigest()
    if checksum!=grant['video_sha256']:raise ValueError('Approved video checksum mismatch')
    if hashlib.sha256(story_bytes).hexdigest()!=report.get('story_sha256'):raise ValueError('Story checksum mismatch')
    if report.get('topic_key')!=grant.get('topic_key') or report.get('profile')!=grant['profile']:raise ValueError('Wrong approved episode')
    story=json.loads(story_bytes)
    if story.get('topic_key')!=grant.get('topic_key') or story.get('profile')!=grant['profile']:raise ValueError('Original story does not match the authorized profile/topic')
    if report.get('editorial_review',{}).get('supported') is not True:raise ValueError('Missing factual or original-narrative editorial review')
    if report.get('independent_asr_word_coverage',0)<.85:raise ValueError('Missing independent speech evidence')
    if report.get('audio_tail',{}).get('audio_tail_checked') is not True or report.get('visual_gate',{}).get('passed') is not True:raise ValueError('Film verification missing')
    require_duration(report['duration'])
    return checksum

def persist():subprocess.run([sys.executable,'-m','professional_motion.persist_state'],check=True)

def main():
    grant=json.loads(CONFIG.read_text());profile=grant['profile'];out=ROOT/'output';delivery=ROOT/'delivery';out.mkdir(exist_ok=True);delivery.mkdir(exist_ok=True)
    def blob(ref,path):return subprocess.check_output(['git','show',ref+':'+path])
    video=out/'professional-review.mp4';video.write_bytes(blob(grant['media_commit'],'review-1080p.mp4'))
    report=json.loads(blob(grant['media_commit'],'verification.json'));story_bytes=blob(grant['evidence_commit'],'professional_motion/delivery/story.json');story=json.loads(story_bytes)
    checksum=validate(grant,video,report,story_bytes)
    subprocess.run(['ffmpeg','-v','error','-i',str(video),'-f','null','-'],check=True)
    from film_factory.delivery import probe
    require_duration(float(probe(video)['format']['duration']))
    if profile=='news':
        from .news_policy import require_fresh
        from datetime import datetime,timezone,timedelta
        require_fresh(story['source'],datetime.now(timezone.utc)+timedelta(minutes=3))
    destinations=preflight(profile,True)
    mapping=destinations['buffer']
    if not mapping or destinations['direct_youtube']:raise RuntimeError('Expected the previously verified Buffer destinations')
    media_id='approved-'+profile+'-'+str(grant['media_run']);os.environ.update(PUBLISH_IMMEDIATE='true',PUBLICATION_RECEIPTS_ENABLED='true',BUFFER_SCHEDULE_MODE='customScheduled',PRODUCTION_MEDIA_ID=media_id,BUFFER_CHANNEL_IDS=','.join(k+':'+v for k,v in mapping.items()),PUBLISH_CHANNELS=','.join(mapping))
    require_services(mapping);data=registry();episode=next((r for r in data['episodes'] if r.get('topic_key')==grant['topic_key']),None)
    if episode is None:episode={'slot':'review-'+str(grant['media_run']),'topic_key':grant['topic_key'],'story':story};data['episodes'].append(episode)
    if episode.get('one_off_publication',{}).get('status') in ('submitting','partial_or_failed') and not all(accepted_receipt(s) for s in mapping):raise RuntimeError('PublicationReconciliationRequired: inspect existing Buffer posts before retrying')
    (delivery/'story.json').write_bytes(story_bytes)
    from .metadata import make
    metadata=make(story,profile);title=metadata['title'];caption=metadata['caption']
    Path('state/current_episode.json').write_text(json.dumps({**story,'title':title,'caption':caption},ensure_ascii=False,indent=2))
    episode['one_off_publication']={'status':'submitting','approved_video_sha256':checksum,'media_id':media_id,'title':title};save(data);persist()
    ok=ContentPublisher().publish_to_buffer(video,title,caption,[])
    receipts={s:accepted_receipt(s) for s in mapping}
    result={'accepted_by_every_destination':bool(ok and all(receipts.values())),'receipts':receipts,'title':title,'video_sha256':checksum,'mode':'immediate','public_live_status_verified':False}
    (delivery/'approved-publication-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    episode['one_off_publication'].update(status='accepted' if result['accepted_by_every_destination'] else 'partial_or_failed',receipts=receipts)
    if result['accepted_by_every_destination']:
        os.environ['BUFFER_OUTCOME']='success';confirm_stock();episode['status']='scheduled'
    save(data);persist()
    print(json.dumps(result,ensure_ascii=False))
    if not result['accepted_by_every_destination']:raise RuntimeError('Not every destination accepted the approved film; see safe receipts')
if __name__=='__main__':main()
