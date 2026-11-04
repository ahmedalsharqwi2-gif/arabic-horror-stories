"""Shorten only measured near-silent pauses; retain original PCM and all speech."""
import array,hashlib,json,math,os,sys,wave
from pathlib import Path
def quiet_cuts(samples,rate,channels,remove_frames,threshold_db=-48,minimum_pause=.5,keep_pause=.22):
 limit=int(32767*10**(threshold_db/20));spans=[];begin=None;frames=len(samples)//channels
 for index in range(frames):
  quiet=all(abs(samples[index*channels+c])<=limit for c in range(channels))
  if quiet and begin is None:begin=index
  if not quiet and begin is not None:
   if index-begin>=minimum_pause*rate:spans.append((begin,index))
   begin=None
 if begin is not None and frames-begin>=minimum_pause*rate:spans.append((begin,frames))
 room=[(b-a-round(keep_pause*rate),a,b) for a,b in spans]
 if sum(max(0,n) for n,a,b in room)<remove_frames:raise ValueError('Insufficient measured silence; no speech may be cut')
 cuts=[];left=remove_frames
 for capacity,a,b in sorted(room,reverse=True):
  take=min(max(0,capacity),left)
  if take:
   start=a+(b-a-take)//2;end=start+take
   if any(abs(x)>limit for x in samples[start*channels:end*channels]):raise ValueError('Removal includes non-silent samples')
   cuts.append((start,end));left-=take
  if not left:break
 if left:raise ValueError('Could not preserve required pauses')
 return sorted(cuts),limit
def compact(wav,source,target=179.5):
 wav=Path(wav);source=Path(source);proof=json.loads(source.read_text());raw=wav.read_bytes();original_sha=hashlib.sha256(raw).hexdigest()
 if (proof.get('output_sha256') or proof.get('sha256'))!=original_sha:raise ValueError('Voice provenance mismatch before silence editing')
 with wave.open(str(wav),'rb') as w:params=w.getparams();samples=array.array('h',w.readframes(w.getnframes()))
 if sys.byteorder!='little':samples.byteswap()
 if params.sampwidth!=2 or params.comptype!='NONE' or params.nchannels not in (1,2):raise ValueError('Only original PCM16 voice may be compacted')
 duration=params.nframes/params.framerate
 if not 180<=duration<=188 or proof.get('silence_compaction'):raise ValueError('Only a single bounded long-voice silence edit is allowed')
 remove=params.nframes-round(target*params.framerate)
 if remove/params.nframes>.04:raise ValueError('Silence editing budget exceeds four percent')
 cuts,limit=quiet_cuts(samples,params.framerate,params.nchannels,remove)
 original=wav.with_name('narration.original.wav')
 if original.exists() and original.read_bytes()!=raw:raise ValueError('Another original voice is already retained')
 original.write_bytes(raw);output=array.array('h');cursor=0
 for start,end in cuts:output.extend(samples[cursor*params.nchannels:start*params.nchannels]);cursor=end
 output.extend(samples[cursor*params.nchannels:])
 if sys.byteorder!='little':output.byteswap()
 temporary=wav.with_name('narration.compacted.tmp.wav')
 with wave.open(str(temporary),'wb') as w:w.setparams(params);w.writeframes(output.tobytes())
 temporary.replace(wav);digest=hashlib.sha256(wav.read_bytes()).hexdigest()
 report={'method':'Remove only PCM samples inside continuous pauses below -48dB; no resynthesis, speech cut or speed change','original_sha256':original_sha,'output_sha256':digest,'original_duration':duration,'duration':len(output)/params.nchannels/params.framerate,'removed_seconds':remove/params.framerate,'maximum_removed_amplitude':limit,'kept_pause_seconds':.22,'cuts':[{'start':a/params.framerate,'end':b/params.framerate} for a,b in cuts]}
 proof.update(original_output_sha256=original_sha,output_sha256=digest,silence_compaction=report);source.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
 for old in wav.parent.glob('asr-*.json'):
  if not old.name.startswith('asr-before-silence-'):old.rename(old.with_name('asr-before-silence-'+old.name[4:]))
 return report
