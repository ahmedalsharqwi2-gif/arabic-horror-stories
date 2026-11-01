"""Narrative diagrams cued only by active words in measured ASS captions."""
import re

RULES = {
 'horror': [('boat',r'قارب|نجاة'),('cargo',r'حمولة|حموله|بضاعة|شحنة'),
            ('people',r'طاقم|ركاب|ناس|أشخاص|اختف|محدش|فاضية|فاضيه'),
            ('unknown',r'لغز|تفسير|احتمال|مجهول|نعرف|دليل|دليل'),
            ('ship',r'سفينة|سفينه|بحر|سيليست|شراعية')],
 'history':[('cannon',r'مدفع|مدافع|قصف|قذائف'),('ship',r'سفن|سفينة|بحري'),
            ('wall',r'سور|أسوار|حصار|دفاع|حجارة'),('timeline',r'سنة|عام|قرن|تاريخ|ألف|أربعمية'),
            ('city',r'مدينة|المدينة|القسطنطينية|العاصمة')],
}

def read_active_captions(source, duration):
    if source is None:
        raise RuntimeError('Measured ASS captions are required')
    from pathlib import Path
    def seconds(value):
        h,m,s=value.split(':')
        return int(h)*3600+int(m)*60+float(s)
    events=[]
    for line in Path(source).read_text(encoding='utf-8-sig').splitlines():
        if not line.startswith('Dialogue:'):continue
        fields=line.split(',',9)
        if len(fields)!=10 or r'\c&H000000FF&' not in fields[9]:continue
        start,end=seconds(fields[1]),min(duration,seconds(fields[2]))
        text=re.sub(r'\{[^}]*\}','',fields[9]).strip()
        if text and 0<=start<end:
            events.append({'start':start,'end':end,'text':text,'ass_text':fields[9]})
    if not events:raise RuntimeError('Active word timings missing from source subtitles')
    return events


def cues_from_captions(events,duration,profile):
    words=[]
    for e in events:
        if r'\c&H000000FF&' in e.get('ass_text',''):
            words.append({'text':e['text'],'start':float(e['start']),'end':float(e['end'])})
    words.sort(key=lambda w:(w['start'],w['end']))
    # Positioned word highlights repeat the surrounding inactive words. Only
    # the active event represents this word's actual measured speech time.
    if not words:
        raise RuntimeError('Narrative motion requires measured active-word captions')
    scenes=[];start=0.;pending=[];previous='ship' if profile=='horror' else 'wall';previous_origin=0.
    for index,word in enumerate(words):
        pending.append(word)
        end=words[index+1]['start'] if index+1<len(words) else duration
        if end-start>=6 or index+1==len(words):
            beats=[{'at':0.,'kind':previous,'word':'','origin':previous_origin}]
            for w in pending:
                kind=next((kind for kind,pattern in RULES[profile] if re.search(pattern,w['text'])),None)
                if kind and kind!=beats[-1]['kind']:
                    beats.append({'at':max(0,w['start']-start),'kind':kind,'word':w['text'],'origin':w['start']})
            scenes.append({'id':f'scene_{len(scenes)+1:03d}','start':start,'end':end,
                           'text':' '.join(w['text'] for w in pending), 'kind':'motion',
                           'query':'','prompt':'Original illustrative narrative diagram',
                           'motion':'spoken_word_cues','shot':beats[-1]['kind'],
                           'narrative_beats':beats,'profile':profile})
            previous=beats[-1]['kind'];previous_origin=beats[-1]['origin'];pending=[];start=end
    return scenes



def narrative_frame(scene,profile,t,duration):
    from scripts.cinematic_stage import cinematic_frame
    return cinematic_frame(scene,profile,t,duration)
