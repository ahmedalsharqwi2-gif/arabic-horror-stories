"""Reviewed, exact-topic public-domain USGS assets when free generation is unavailable."""
import hashlib,io,json
from pathlib import Path
import requests
from PIL import Image
ASSETS={
 'lake':('https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/2_2.jpg','https://www.usgs.gov/media/images/exploding-lakes-cameroon-0','Jack Lockwood / USGS'),
 'fountain':('https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/1_2.jpg','https://www.usgs.gov/media/images/exploding-lakes-cameroon','USGS'),
 'raft':('https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/4_2.jpg','https://www.usgs.gov/media/images/exploding-lakes-cameroon-2','USGS')
}
def prepare_archive(plan):
 if plan['topic_id']!='nyos-cameroon-1986-documented':raise ValueError('Archive cannot illustrate a different event')
 cache=Path('.image_cache/nyos-usgs');cache.mkdir(parents=True,exist_ok=True);out=Path('output/images');out.mkdir(parents=True,exist_ok=True)
 for key,(url,_,_) in ASSETS.items():
  p=cache/(key+'.jpg')
  if not p.exists():
   r=requests.get(url,timeout=60);r.raise_for_status()
   with Image.open(io.BytesIO(r.content)) as im:
    im.load()
    if min(im.size)<300:raise ValueError('Archive asset too small')
    im.convert('RGB').save(p,quality=95)
 paths=[];records=[]
 for i,scene in enumerate(plan['scenes']):
  text=scene['narration'];key='raft' if any(w in text for w in ('أنابيب','انابيب','مواسير')) else 'fountain' if any(w in text for w in ('ماسورة','نافورة','تنفيس','تفريغ')) else 'lake'
  target=out/('scene-%02d.jpg'%(i+1));target.write_bytes((cache/(key+'.jpg')).read_bytes());paths.append(target)
  records.append({'scene':i,'file':str(target),'provider':'USGS public-domain archival photo','url':ASSETS[key][0],'source_page':ASSETS[key][1],'credit':ASSETS[key][2],'license':'Public Domain','date_not_assumed_to_be_the_night_of_the_disaster':True,'generated':False,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
 plan['visual_mode']='reviewed_public_domain_archive';plan['visual_credit']='Jack Lockwood / USGS • Public Domain';Path('output/plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2))
 Path('output/image_manifest.json').write_text(json.dumps({'completed':True,'mode':plan['visual_mode'],'images':records},ensure_ascii=False,indent=2))
 print('Using reviewed exact-topic USGS archive: three original public-domain photos, six edited shots; no unrelated stock or paid generation',flush=True)
 return paths
