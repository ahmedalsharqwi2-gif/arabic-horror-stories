"""Reuse exact original Charon audio; correct year captions to source/independent ASR."""
import hashlib,json,subprocess,re
from pathlib import Path
from . import editorial as e
from .alignment import measured_timing
SOURCE='c270644f69d05c54990ba192940072cf6c214cdf'
AUDIO='2e96aaa0e07cf34b11544976d0b2a24ddbfbb3a8201f79fac99fcae4df8a02bd'
FIXES={'ألف وكمان مية وخمسة والأربعين':'1845','ألف وكمان مية وتسعة وخمسين':'1859','ألف وكمان مية وثمانية':'1848','ألفين وكمان أربعة عشر وألفين وكمان ستة عشر':'2014 و2016','إتش إم إس إريبوس وإتش إم إس تيرور':'HMS Erebus وHMS Terror'}
def main():
 subprocess.run(['git','fetch','origin','refs/heads/codex/professional-review-run-41053666915'],check=True)
 def blob(name):return subprocess.check_output(['git','show',SOURCE+':professional_motion/delivery/'+name])
 out=Path('professional_motion/delivery');out.mkdir(exist_ok=True)
 original=blob('story.json');story=json.loads(original)
 if story['topic_key']!='franklin-expedition-1845':raise ValueError('Wrong reserved incident')
 wav=blob('narration.wav')
 if hashlib.sha256(wav).hexdigest()!=AUDIO:raise ValueError('Original audio changed')
 transcripts=[]
 for model in ('medium','small','large-v3'):
  raw=blob('asr-'+model+'.json');(out/('asr-'+model+'.json')).write_bytes(raw);transcripts.append((model,json.loads(raw)['recognized_words']))
 words={year for _,raw in transcripts for w in raw for year in re.findall(r'\d{4}',w['text'])}
 if not {'1845','1859','1848','2014','2016'}<=words:raise ValueError('Independent recognized years do not support caption correction')
 for scene in story['scenes']:
  for old,new in FIXES.items():scene['narration']=scene['narration'].replace(old,new)
 story['post_edit_review']={'reviewer':'Codex','scope':'Correct malformed written-out years to real source dates independently recognized in the original audio; retain narration audio byte for byte','original_story_sha256':hashlib.sha256(original).hexdigest(),'original_audio_sha256':AUDIO,'changes':FIXES}
 data=e.registry();episode=next(r for r in data['episodes'] if r['slot']=='daily-2026-10-30')
 if episode.get('status') in ('scheduled','published'):raise ValueError('Do not replace scheduled media')
 episode.update(story=story,status='reserved');e.save(data)
 (out/'story.json').write_text(json.dumps(story,ensure_ascii=False,indent=2));(out/'narration.wav').write_bytes(wav)
 # Keep original supplied text and provenance intact; never relabel a TTS input.
 (out/'narration.source.json').write_bytes(blob('narration.source.json'))
 (out/'transcript-correction.json').write_text(json.dumps(story['post_edit_review'],ensure_ascii=False,indent=2))
 duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(out/'narration.wav')]))
 if not 120<=duration<180:raise ValueError('Original voice is outside daily duration')
 timing=measured_timing(story,duration,transcripts)
 timing.update(profile='horror',topic_key=story['topic_key'],audio_sha256=AUDIO,story_sha256=hashlib.sha256((out/'story.json').read_bytes()).hexdigest())
 (out/'timing.json').write_text(json.dumps(timing,ensure_ascii=False,indent=2))
 print('Same original audio:',duration,'seconds; exact ASR coverage:',timing['exact_token_coverage'])
if __name__=='__main__':main()
