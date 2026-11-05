"""Check deliberate suspense pauses against actual quiet intervals; never insert silence."""
import re,subprocess
from visual_contract import load_template

def select_beats(story,timing,intervals):
 cfg=load_template()['silence'];minimum=cfg['min_ms']/1000;beats=[]
 selected=[i for i,s in enumerate(story['scenes'][:-1]) if s.get('silence_after') is True]
 if not selected:raise ValueError('At least one authored suspense pause is required')
 for i in selected:
  scene=timing['scenes'][i];boundary=scene['end']
  candidates=[(a,b) for a,b in intervals if b-a>=minimum and a>=scene['start'] and abs(b-boundary)<=.5]
  if not candidates:raise ValueError('Authored suspense beat has no measured 400ms narration pause; retain voice, never pad it')
  a,b=min(candidates,key=lambda x:abs(x[1]-boundary));beats.append({'scene':i,'start':a,'end':b,'measured_quiet_ms':round((b-a)*1000)})
 for beat in beats:
  if sum(beat['start']<=x['start']<beat['start']+60 for x in beats)>cfg['max_per_60s']:raise ValueError('Too many suspense beats in a rolling 60 seconds')
 return beats

def verify(story,timing,wav):
 cfg=load_template()['silence'];r=subprocess.run(['ffmpeg','-hide_banner','-i',str(wav),'-af',f"silencedetect=noise=-45dB:d={cfg['min_ms']/1000}",'-f','null','-'],capture_output=True,text=True,check=True)
 starts=[];intervals=[]
 for line in r.stderr.splitlines():
  a=re.search(r'silence_start: ([0-9.]+)',line);b=re.search(r'silence_end: ([0-9.]+)',line)
  if a:starts.append(float(a.group(1)))
  if b and starts:intervals.append((starts.pop(0),float(b.group(1))))
 return select_beats(story,timing,intervals)
