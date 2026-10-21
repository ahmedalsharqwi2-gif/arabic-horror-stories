"""Narrative diagrams cued only by active words in measured ASS captions."""
import math
import re
from PIL import Image, ImageDraw
from scripts.motion_graphics import label

RULES = {
 'horror': [('boat',r'قارب|نجاة'),('cargo',r'حمولة|حموله|بضاعة|شحنة'),
            ('people',r'طاقم|ركاب|ناس|أشخاص|اختف|محدش|فاضية|فاضيه'),
            ('unknown',r'لغز|تفسير|احتمال|مجهول|نعرف|دليل|دليل'),
            ('ship',r'سفينة|سفينه|بحر|سيليست|شراعية')],
 'history':[('cannon',r'مدفع|مدافع|قصف|قذائف'),('ship',r'سفن|سفينة|بحري'),
            ('wall',r'سور|أسوار|حصار|دفاع|حجارة'),('timeline',r'سنة|عام|قرن|تاريخ|ألف|أربعمية'),
            ('city',r'مدينة|المدينة|القسطنطينية|العاصمة')],
}
TITLES={
 'horror':{'ship':'سفينة في عرض البحر','boat':'قارب النجاة','cargo':'الحمولة','people':'الناس فين؟','unknown':'إيه اللي نعرفه؟'},
 'history':{'wall':'الأسوار والحصار','cannon':'المدافع في الحصار','ship':'السفن ومسار الأحداث','city':'المدينة','timeline':'تتابع الأحداث'},
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
    scenes=[];start=0.;pending=[];previous='ship' if profile=='horror' else 'wall'
    for index,word in enumerate(words):
        pending.append(word)
        end=words[index+1]['start'] if index+1<len(words) else duration
        if end-start>=6 or index+1==len(words):
            beats=[{'at':0.,'kind':previous,'word':''}]
            for w in pending:
                kind=next((kind for kind,pattern in RULES[profile] if re.search(pattern,w['text'])),None)
                if kind and kind!=beats[-1]['kind']:
                    beats.append({'at':max(0,w['start']-start),'kind':kind,'word':w['text']})
            scenes.append({'id':f'scene_{len(scenes)+1:03d}','start':start,'end':end,
                           'text':' '.join(w['text'] for w in pending), 'kind':'motion',
                           'query':'','prompt':'Original illustrative narrative diagram',
                           'motion':'spoken_word_cues','shot':beats[-1]['kind'],
                           'narrative_beats':beats,'profile':profile})
            previous=beats[-1]['kind'];pending=[];start=end
    return scenes


def arrow(d,a,b,color,width=5):
    d.line((a,b),fill=color,width=width);x,y=b;angle=math.atan2(y-a[1],x-a[0])
    d.polygon([(x,y),(x-18*math.cos(angle-.6),y-18*math.sin(angle-.6)),
               (x-18*math.cos(angle+.6),y-18*math.sin(angle+.6))],fill=color)


def ship(d,t,accent,ghost=False):
    cy=1060+5*math.sin(t*.8)
    for row in range(5):
        d.line([(x,1180+row*38+7*math.sin(x*.015-t*1.1-row)) for x in range(100,990,9)],fill='#385567',width=3)
    d.polygon([(235,cy),(860,cy),(765,cy+130),(335,cy+130)],fill='#45525a',outline=accent,width=4)
    for x,h in [(450,320),(640,360)]:
        d.line((x,cy,x,cy-h),fill=accent,width=6)
        d.polygon([(x+8,cy-h+20),(x+140,cy-30),(x+8,cy-30)],fill='#839698',outline=accent,width=2)
    d.rectangle((360,cy-40,760,cy),fill='#35414d',outline=accent,width=2)


def narrative_frame(scene,profile,t,duration):
    accent='#e9bf83' if profile=='history' else '#9bc7c9'
    base='#101b26' if profile=='history' else '#0a1420'
    im=Image.new('RGB',(1080,1920),base);d=ImageDraw.Draw(im)
    # Small deterministic texture, no external images or paid requests.
    for y in range(500,1480,26):
        for x in range(85,1010,35):
            if (x*7+y*11)%17<3:d.point((x,y),fill='#233441')
    d.rounded_rectangle((60,75,1020,180),radius=26,fill='#1b2c38')
    label(im,'على خط الحكاية' if profile=='history' else 'قبل ما تطفي النور',540,130,38,accent)
    beat=[b for b in scene['narrative_beats'] if b['at']<=t+.00001][-1]
    kind=beat['kind'];age=max(0,t-beat['at']);reveal=min(1,age/.45)
    label(im,TITLES[profile][kind],540,350,58,'#f0ede5',width=900,maxlines=2)
    d.rounded_rectangle((65,550,1015,1440),radius=38,fill='#132734',outline='#334854',width=2)
    absolute=scene['start']+t
    if profile=='horror':
        if kind=='ship':ship(d,absolute,accent)
        elif kind=='boat':
            ship(d,absolute,accent)
            # Outline shows the object discussed, not a reconstruction of how
            # anyone abandoned the ship or a claimed route.
            d.rounded_rectangle((630,1230,935,1350),radius=20,outline=accent,width=3)
            d.polygon([(665,1280),(900,1280),(860,1320),(705,1320)],outline=accent,width=3)
        elif kind=='cargo':
            for row in range(3):
                for col in range(4):
                    x=210+col*175;y=765+row*165
                    d.rounded_rectangle((x,y,x+125,y+135),radius=23,fill='#3a4a50',outline=accent,width=3)
                    for dy in (35,100):d.line((x,y+dy,x+125,y+dy),fill='#698587',width=3)
        elif kind=='people':
            for i in range(5):
                x=230+i*155
                d.ellipse((x-34,845,x+34,913),outline=accent,width=4)
                d.rounded_rectangle((x-48,925,x+48,1105),radius=30,outline=accent,width=4)
                d.line((x-20,1108,x-20,1170),fill=accent,width=4)
                d.line((x+20,1108,x+20,1170),fill=accent,width=4)
            label(im,'رموز توضيحية، مش عدد أشخاص',540,1320,27,'#95aab5')
        else:
            for i in range(3):
                x=195+i*260;y=800+(i%2)*90
                d.rounded_rectangle((x,y,x+180,y+255),radius=15,fill='#243b48',outline=accent,width=2)
                for row in range(5):d.line((x+25,y+45+row*32,x+145,y+45+row*32),fill='#6f8c98',width=3)
            d.ellipse((398,900,682,1184),outline=accent,width=6)
            label(im,'؟',540,1035,140,accent)
    else:
        if kind in ('wall','city','cannon'):
            for i in range(10):
                x=155+i*78
                d.rectangle((x,895,x+77,1165),fill='#5b6260',outline='#899185',width=2)
                d.rectangle((x,860,x+42,895),fill='#899185')
                for row in range(5):d.line((x,930+row*45,x+77,930+row*45),fill='#899185',width=2)
            for x in (190,760):
                d.rectangle((x,765,x+130,1165),fill='#737b70',outline=accent,width=3)
                for k in range(3):d.rectangle((x+k*44,725,x+k*44+24,765),fill=accent)
            d.rounded_rectangle((470,1020,610,1165),radius=50,fill=base,outline=accent,width=3)
            if kind=='cannon':
                d.ellipse((170,1220,290,1340),fill='#364752',outline=accent,width=4)
                d.line((225,1255,425,1170),fill=accent,width=38)
                phase=(age*.4)%1;px=440+phase*270;py=1160-phase*200
                d.ellipse((px-8,py-8,px+8,py+8),fill=accent)
        elif kind=='ship':
            ship(d,absolute,accent)
            d.arc((160,640,900,1320),210,330,fill=accent,width=4)
        else:
            for i in range(4):
                x=200+i*225;ry=1010
                if i<3:d.line((x,ry,x+225,ry),fill='#70828b',width=4)
                d.ellipse((x-25,ry-25,x+25,ry+25),fill=accent if i<=int(reveal*3) else '#4f6470')
            label(im,'وقائع مترتبة في الحكاية',540,1260,35,accent)
    if beat['word']:
        size=40+round(5*(1-min(1,age/.3)))
        label(im,beat['word'],540,1515,size,accent,width=860,maxlines=2)
    label(im,'تصور توضيحي، وليس تصويرًا للواقعة',540,1640,27,'#98aab4')
    d.line((80,1845,1000,1845),fill='#3a4c57',width=4)
    d.line((80,1845,80+920*t/max(duration,.01),1845),fill=accent,width=5)
    return im
