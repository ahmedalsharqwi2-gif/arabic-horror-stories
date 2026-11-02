"""Recover timing from the same retained voice and independent raw ASR; no provider calls."""
import hashlib,json,wave
from pathlib import Path
from .alignment import recognized_key,measured_timing
from .speech_characters import character_timing
from .policy import require_duration
def main():
 root=Path('professional_motion/delivery')
 story=json.loads((root/'story.json').read_text());source=json.loads((root/'narration.source.json').read_text())
 full=' '.join(s['narration'] for s in story['scenes'])
 if ' '.join(source['text'].split())!=' '.join(full.split()):raise ValueError('Retained narration text differs')
 audio_hash=hashlib.sha256((root/'narration.wav').read_bytes()).hexdigest()
 if source.get('output_sha256')!=audio_hash:raise ValueError('Retained voice provenance hash differs')
 with wave.open(str(root/'narration.wav')) as audio:duration=audio.getnframes()/audio.getframerate()
 require_duration(duration)
 transcripts=[(m,json.loads((root/('asr-'+m+'.json')).read_text())['recognized_words']) for m in ('medium','small','large-v3')]
 old=measured_timing(story,duration,transcripts,allow_low_coverage=True)
 timing=character_timing(story,duration,transcripts,recognized_key,old.get('exact_token_coverage',old['coverage']))
 timing.update(profile=story['profile'],topic_key=story['topic_key'],story_sha256=hashlib.sha256((root/'story.json').read_bytes()).hexdigest(),audio_sha256=audio_hash)
 (root/'timing.json').write_text(json.dumps(timing,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'duration':duration,'coverage':timing['coverage'],'exact_token_coverage':timing['exact_token_coverage'],'normalized_character_coverage':timing['normalized_character_coverage'],'provider_requests':0}))
if __name__=='__main__':main()
