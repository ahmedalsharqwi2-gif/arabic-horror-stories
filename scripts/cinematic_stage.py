"""Original full-frame narrative animation; illustrative, never archival footage."""
import math
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from scripts.motion_graphics import label

W,H=1080,1920


def smooth(x):
    x=max(0.,min(1.,x));return x*x*(3-2*x)


def active_beat(scene,t):
    beat=[b for b in scene['narrative_beats'] if b['at']<=t+.00001][-1]
    absolute=scene['start']+t
    return beat,absolute,max(0.,absolute-beat.get('origin',scene['start']+beat['at']))


@lru_cache(2)
def sky(profile):
    im=Image.new('RGB',(W,H));d=ImageDraw.Draw(im)
    for y in range(H):
        q=min(1,y/1450)
        rgb=(round(13+q*25),round(24+q*25),round(36+q*25)) if profile=='horror' else (round(36+q*55),round(34+q*39),round(37+q*28))
        d.line((0,y,W,y),fill=rgb)
    return im


@lru_cache(1)
def light_stamp():
    import numpy as np
    y,x=np.mgrid[-1:1:complex(0,850),-1:1:complex(0,850)]
    alpha=(185*np.exp(-3.4*(x*x+y*y))).astype('uint8')
    return Image.fromarray(alpha,'L')


def vignette(im,focus):
    dark=ImageChops.multiply(im,Image.new('RGB',im.size,(91,105,125)))
    mask=Image.new('L',im.size,20)
    x,y=focus;mask.paste(light_stamp(),(round(x)-425,round(y)-425))
    return Image.composite(im,dark,mask)


def frame_chrome(im,profile,kind,word,age):
    # Screen space stays fixed while the world and camera move behind it.
    d=ImageDraw.Draw(im,'RGBA')
    d.rectangle((0,0,W,210),fill=(5,12,20,210))
    d.rectangle((0,1635,W,H),fill=(5,12,20,225))
    brand='ملفات غامضه' if profile=='horror' else 'نقص ونروى'
    color='#bad6d5' if profile=='horror' else '#edc589'
    label(im,brand,540,125,38,color)
    if word and age<2.2:
        a=smooth(min(age/.25,(2.2-age)/.3))
        if a>.01:
            label(im,word,540,1525-round(12*a),38+round(5*a),color,width=850,maxlines=2)
    label(im,'تصور درامي توضيحي' if profile=='horror' else 'تحريك توضيحي للحدث، وليس تصويرًا للواقعة',540,1885,24,'#a9b7ba')
    return im


def ocean(d,t,horizon=725):
    d.rectangle((0,horizon,W,1450),fill='#173442')
    for row in range(30):
        y=horizon+row*24
        amp=2+row*.2
        points=[(x,y+amp*math.sin(x*.012-t*.9+row*.8)) for x in range(-40,W+45,18)]
        d.line(points,fill=(38+row//3,65+row//3,77+row//3),width=2)


def deck_scene(t,kind,age):
    im=sky('horror').copy();d=ImageDraw.Draw(im)
    ocean(d,t,715)
    # Forward-facing camera on a rolling deck; perspective converges at the hatch.
    vanx=540+18*math.sin(t*.3);van=(vanx,935)
    d.polygon([(170,960),(910,960),(1270,1700),(-190,1700)],fill='#403a32')
    for i in range(-9,10):
        d.line((vanx+i*32,950,540+i*135,1710),fill='#76654c',width=3)
    for k in range(10):
        z=((k/10+t*.022)%1)**1.6;y=960+z*740
        d.line((-200,y,1270,y),fill='#241e1c',width=4)
    for side in (0,1):
        for k in range(7):
            z=k/6; x=(180-205*z) if side==0 else (900+205*z);y=965+z*650
            d.line((x,y,x,y-180-90*z),fill='#85745c',width=8)
        d.line((180 if side==0 else 900,790,-25 if side==0 else 1105,1390),fill='#a08d6e',width=9)
    d.rectangle((400,630,680,960),fill='#292b2a',outline='#7d7b68',width=4)
    d.polygon([(355,640),(725,640),(675,585),(405,585)],fill='#6a6655')
    d.rectangle((455,725,625,960),fill='#111e27',outline='#a09070',width=5)
    d.line((535,380,535,650),fill='#786c58',width=12)
    for x in (70,1010):d.line((535,400,x,1080),fill='#84827a',width=2)
    if kind=='boat':
        # Empty boat supports communicate absence, not an invented departure.
        d.polygon([(675,1170),(875,1095),(1010,1220),(815,1330)],fill='#192b34',outline='#a5a68b',width=3)
        for x,y in [(725,1170),(870,1235)]:
            d.arc((x-55,y-50,x+55,y+30),0,180,fill='#a79b7b',width=8)
    focus=(540+160*math.sin(t*.43),1000+70*math.sin(t*.6))
    return vignette(im,focus)


def cabin_scene(t,kind,age):
    im=sky('horror').copy();d=ImageDraw.Draw(im)
    ox=14*math.sin(t*.45);oy=6*math.sin(t*.9)
    left,right=270+ox,810+ox
    d.polygon([(0,300),(left,625),(left,1150),(0,1550)],fill='#35352e')
    d.polygon([(W,300),(right,625),(right,1150),(W,1550)],fill='#2d302d')
    d.rectangle((left,625,right,1150),fill='#444238')
    d.polygon([(0,1550),(left,1150),(right,1150),(W,1550)],fill='#453c31')
    for side in range(7):
        y=490+side*135
        d.line((0,y,left,625+(y-490)*.51),fill='#71614a',width=4)
        d.line((W,y,right,625+(y-490)*.51),fill='#625c49',width=4)
    for x in range(-100,1200,110):d.line((540,1080,x,1580),fill='#7a664b',width=3)
    d.rectangle((450+ox,700,630+ox,1150),fill='#111d26',outline='#958569',width=7)
    # Inside the opening only deep perspective is visible; no invented ghost.
    d.rectangle((477+ox,750,602+ox,1150),fill='#1c2930',outline='#394148',width=2)
    if kind=='people':
        for x in (75,735):
            d.polygon([(x,1040),(x+230,940),(x+260,1080),(x+10,1200)],fill='#7c7560',outline='#aaa18a',width=4)
            d.polygon([(x+15,1030),(x+220,955),(x+232,990),(x+25,1070)],fill='#b5ad96')
            d.line((x+20,1200,x+20,1320),fill='#4b4537',width=12)
    elif kind=='cargo':
        for x,y in [(70,1010),(810,1000),(120,1240),(760,1220)]:
            d.rounded_rectangle((x,y,x+145,y+180),radius=35,fill='#67553e',outline='#aa916c',width=4)
            for dy in (40,135):d.line((x,y+dy,x+145,y+dy),fill='#383f41',width=9)
    else:
        d.polygon([(150,1230),(630,1120),(890,1290),(370,1450)],fill='#827252',outline='#a89b77',width=4)
        for k in range(3):
            x=340+k*100;y=1270-k*22
            d.polygon([(x,y),(x+105,y-10),(x+115,y+55),(x+5,y+65)],fill='#c5c0a3')
            for row in range(4):d.line((x+15,y+15+row*8,x+85,y+9+row*8),fill='#6b685b',width=1)
        d.ellipse((390,1150,510,1260),fill='#787d74',outline='#c7c4a4',width=4)
        d.ellipse((410,1170,490,1240),fill='#1c313b')
    return vignette(im,(540+180*math.sin(t*.39),1040+110*math.sin(t*.3)))


def horror_world(scene,t,duration):
    beat,absolute,age=active_beat(scene,t);kind=beat['kind']
    view=deck_scene(absolute,kind,age) if kind in ('ship','boat') else cabin_scene(absolute,kind,age)
    # Slow camera roll, not arbitrary sliding cards or repeated stick figures.
    angle=.65*math.sin(absolute*.43)
    view=view.rotate(angle,resample=Image.Resampling.BICUBIC,fillcolor='#111e29')
    d=ImageDraw.Draw(view)
    for i in range(38 if kind in ('ship','boat') else 12):
        x=(i*173+absolute*31)%W;y=250+(i*119+absolute*57)%1250
        if kind in ('ship','boat'):d.line((x,y,x-10,y+36),fill='#5e7980',width=1)
        else:d.ellipse((x,y,x+2,y+2),fill='#638087')
    return frame_chrome(view,'horror',kind,beat['word'],age)


def soldier(d,x,y,scale,t,index,advance=True):
    stride=math.sin(t*5+index*.75)*8*scale if advance else 0
    c='#202c31';r=12*scale
    d.ellipse((x-r,y-80*scale-r,x+r,y-80*scale+r),fill=c)
    d.polygon([(x-17*scale,y-65*scale),(x+17*scale,y-65*scale),(x+22*scale,y-18*scale),(x-21*scale,y-18*scale)],fill=c)
    d.line((x-9*scale,y-20*scale,x-16*scale+stride,y+17*scale),fill=c,width=max(1,round(8*scale)))
    d.line((x+9*scale,y-20*scale,x+16*scale-stride,y+17*scale),fill=c,width=max(1,round(8*scale)))
    d.ellipse((x-30*scale,y-60*scale,x+5*scale,y-8*scale),fill='#6d7364',outline='#b3a786',width=max(1,round(scale)))
    d.line((x+26*scale,y-35*scale,x+26*scale,y-160*scale),fill='#b6a981',width=max(1,round(3*scale)))


def smoke(im,cx,cy,age,strength=1.):
    if not 0<age<4:return
    layer=Image.new('RGBA',(W,H));d=ImageDraw.Draw(layer)
    for i in range(8):
        r=22+age*36+i*6;x=cx+math.sin(i*3.1)*age*42;y=cy-age*(45+i*8)
        a=round(80*strength*(1-age/4))
        d.ellipse((x-r,y-r,x+r,y+r),fill=(152,144,125,a))
    im.paste(layer,(0,0),layer)


def fortress(im,t,kind,age):
    d=ImageDraw.Draw(im)
    for row in range(3):
        y=670+row*80
        for i in range(12):
            x=i*100-90+row*20
            d.polygon([(x,y+100),(x+45,y),(x+95,y+100)],fill=('#585b55','#4b524f','#3d4948')[row])
    # Full stage rather than a diagram inside a small rounded rectangle.
    d.rectangle((0,900,W,1280),fill='#777565')
    for row in range(8):
        y=900+row*45
        d.line((0,y,W,y),fill='#454c49',width=3)
        for x in range(-80,W+80,110):
            xx=x+(55 if row%2 else 0);d.line((xx,y,xx,y+45),fill='#4a514d',width=2)
    for x in (95,740):
        d.rectangle((x,710,x+240,1290),fill='#83816d',outline='#b0aa8c',width=3)
        for k in range(5):d.rectangle((x+k*52,670,x+k*52+30,730),fill='#b1aa89')
        for yy in (800,950):d.rounded_rectangle((x+90,yy,x+148,yy+100),radius=22,fill='#263b40')
    d.rounded_rectangle((420,1080,635,1320),radius=90,fill='#1b3036',outline='#b5a783',width=6)
    d.polygon([(0,1280),(W,1280),(W,H),(0,H)],fill='#77715c')
    for row in range(3):
        s=.48+row*.19
        for col in range(9):
            x=75+col*130+14*math.sin(t*.45+row);y=1380+row*115
            soldier(d,x,y,s,t,col+row*9,advance=kind in ('wall','cannon'))
    # A cannon shot happens once at its narration cue; impacts share its clock.
    if kind=='cannon':
        recoil=14*math.exp(-age*5) if age<1 else 0
        d.ellipse((68-recoil,1440,235-recoil,1607),fill='#334046',outline='#a49d7a',width=8)
        d.polygon([(108-recoil,1490),(372-recoil,1320),(410-recoil,1375),(155-recoil,1550)],fill='#575949',outline='#c5b284',width=4)
        if .05<age<1.45:
            p=(age-.05)/1.4;x=400+300*p;y=1340-440*p+220*p*p
            d.ellipse((x-10,y-10,x+10,y+10),fill='#302b24')
        if .02<age<.2:d.polygon([(390,1345),(490,1270),(465,1370)],fill='#f9d078')
        smoke(im,420,1350,age,.9)
        smoke(im,705,1110,age-1.45,.9)
        if 1.45<age<2.5:
            dr=ImageDraw.Draw(im);z=age-1.45
            for i in range(10):
                x=705+(i-5)*z*55;y=1120-130*z+180*z*z+i*4
                dr.rectangle((x,y,x+7,y+10),fill='#c4b69b')


def fleet(im,t,age):
    d=ImageDraw.Draw(im);ocean(d,t,780)
    # No invented geographic map or exact fleet count: illustrative silhouettes.
    for i,(cx,cy,scale) in enumerate([(250,1010,.75),(730,1140,1.05),(400,1350,.6)]):
        cx+=45*math.sin(t*.2+i);cy+=5*math.sin(t+i)
        pts=[(cx-180*scale,cy),(cx+180*scale,cy),(cx+130*scale,cy+80*scale),(cx-100*scale,cy+80*scale)]
        d.polygon(pts,fill='#4d534c',outline='#c5b99a',width=3)
        d.line((cx,cy,cx,cy-250*scale),fill='#cabd99',width=5)
        d.polygon([(cx+8,cy-235*scale),(cx+160*scale,cy-20),(cx+8,cy-20)],fill='#c4bda7')


def history_world(scene,t,duration):
    beat,absolute,age=active_beat(scene,t);kind=beat['kind']
    im=sky('history').copy()
    if kind=='ship':fleet(im,absolute,age)
    else:fortress(im,absolute,kind,age)
    # A slow camera push keeps architecture large without zooming the captions.
    zoom=1.015+.012*math.sin(absolute*.12)
    nw,nh=round(W*zoom),round(H*zoom)
    im=im.resize((nw,nh),Image.Resampling.BICUBIC).crop(((nw-W)//2,(nh-H)//2,(nw+W)//2,(nh+H)//2))
    if kind=='cannon' and 1.45<age<1.9:
        dx=round(4*math.sin(age*60)*(1-(age-1.45)/.45))
        im=im.transform((W,H),Image.Transform.AFFINE,(1,0,dx,0,1,0),fillcolor='#3b3c37')
    return frame_chrome(im,'history',kind,beat['word'],age)


def cinematic_frame(scene,profile,t,duration):
    return horror_world(scene,t,duration) if profile=='horror' else history_world(scene,t,duration)
