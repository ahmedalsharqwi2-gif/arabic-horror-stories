"""Original stereo ambience and narrated-event accents, with clear center voice."""
from pathlib import Path
import json
import math
import subprocess
import wave
import numpy as np


def cue_events(scenes):
    events={}
    for scene in scenes:
        for beat in scene.get('narrative_beats',[]):
            if not beat.get('word'):continue
            at=float(beat.get('origin',scene['start']+beat['at']))
            events[(beat['kind'],round(at,3))]={'kind':beat['kind'],'at':at,'word':beat['word']}
    return sorted(events.values(),key=lambda e:e['at'])


def stereo_pan(signal,pan):
    pan=np.asarray(pan)
    return np.stack((signal*np.sqrt((1-pan)/2),signal*np.sqrt((1+pan)/2)),axis=-1).astype('float32')


def ambience(duration,profile,events,rate=24000):
    n=math.ceil(duration*rate);t=np.arange(n,dtype='float32')/rate
    rng=np.random.default_rng(1287)
    # Smoothed noise gives wind and distant water rather than full-band hiss.
    raw=rng.standard_normal(n).astype('float32')
    cumulative=np.cumsum(raw,dtype='float64')
    width=90
    wind=np.zeros(n,dtype='float32')
    wind[width:]=(cumulative[width:]-cumulative[:-width])/width
    wind*=.11 if profile=='horror' else .055
    wind*=.6+.4*np.sin(t*.23)**2
    drone=.009*np.sin(2*np.pi*48*t)+.004*np.sin(2*np.pi*71.3*t)
    bed=stereo_pan(wind+drone,.35*np.sin(t*.19))
    fx=np.zeros((n,2),dtype='float32')
    def place(at,length,fn,pan=0.):
        lo=max(0,round(at*rate));hi=min(n,lo+round(length*rate))
        if hi<=lo:return
        z=np.arange(hi-lo,dtype='float32')/rate
        fx[lo:hi]+=stereo_pan(fn(z),pan)
    if profile=='horror':
        for index,at in enumerate(np.arange(4.,duration,9.7)):
            def creak(z):
                return .027*np.sin(2*np.pi*(145*z+22*z*z)+.8*np.sin(z*9))*np.sin(np.pi*z/1.8)**2
            place(float(at),1.8,creak,(-.7 if index%2 else .7))
        for event in events:
            if event['kind'] in ('people','unknown'):
                for offset in (0.,1.05,2.1):
                    def heartbeat(z):
                        return .035*np.sin(2*np.pi*58*z)*np.exp(-23*z)+.019*np.sin(2*np.pi*65*z)*np.exp(-28*np.abs(z-.15))
                    place(event['at']+offset,.45,heartbeat)
    elif profile=='history':
        for event in events:
            if event['kind']=='cannon':
                def boom(z):
                    noise=rng.standard_normal(len(z)).astype('float32')
                    return .10*np.sin(2*np.pi*(72*z-7*z*z))*np.exp(-3*z)+.026*noise*np.exp(-10*z)
                place(event['at']+.05,1.8,boom,-.35)
                def impact(z):
                    return .06*rng.standard_normal(len(z)).astype('float32')*np.exp(-13*z)
                place(event['at']+1.45,.8,impact,.35)
    fade=np.minimum(1,t/1.5)*np.minimum(1,np.maximum(0,duration-t)/2)
    bed*=fade[:,None];fx*=fade[:,None]
    return bed,fx


def write_wave(path,signal,rate=24000):
    with wave.open(str(path),'wb') as out:
        out.setnchannels(2);out.setsampwidth(2);out.setframerate(rate)
        out.writeframes((np.clip(signal,-.95,.95)*32767).astype('<i2').tobytes())


def mix_immersive(voice,output,duration,scenes,profile,root):
    root=Path(root);work=Path(output).parent;work.mkdir(parents=True,exist_ok=True)
    events=cue_events(scenes)
    bed,fx=ambience(duration,profile,events)
    bed_path,fx_path=work/'immersive-bed.wav',work/'immersive-effects.wav'
    write_wave(bed_path,bed);write_wave(fx_path,fx)
    # Center narration stays dry and intelligible; only the environment is stereo.
    graph=('[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[v][key];'
           '[1:a]aresample=48000[bed];[2:a]aresample=48000[fx];'
           '[bed][fx]amix=inputs=2:normalize=0[env];'
           '[env][key]sidechaincompress=threshold=0.015:ratio=6:attack=12:release=250[duck];'
           '[v][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.94:level=disabled[a]')
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(voice),'-i',str(bed_path),'-i',str(fx_path),
        '-filter_complex',graph,'-map','[a]','-t',str(duration),'-c:a','aac','-b:a','192k',str(output)],check=True)
    state=root/'state';state.mkdir(exist_ok=True)
    (state/'immersive_audio.json').write_text(json.dumps({'profile':profile,'voice_changed_by_mixer':False,
        'original_synthesized_effects':True,'archival_audio':False,'stereo_environment':True,
        'narration_ducking':True,'effect_cues':events,'bed_peak':float(np.max(np.abs(bed))),
        'effects_peak':float(np.max(np.abs(fx)))},ensure_ascii=False,indent=2),encoding='utf-8')
