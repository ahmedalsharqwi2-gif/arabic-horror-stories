"""Two bounded real Workers AI portrait requests. Never publishes or substitutes stock."""
import base64,io,json,os
from pathlib import Path
import requests
from PIL import Image

MODEL='@cf/black-forest-labs/flux-2-klein-4b'
PROMPTS=[
 'A lifelike documentary reconstruction photograph of Lake Nyos in Cameroon, a deep green crater lake enclosed by high forested volcanic hills, camera at the edge of a rough grassy path, a single small rural unbranded mud-plaster house in the near foreground. Nightfall with the last natural blue light across the distant hills, dim warm oil-lamp light through a real wooden doorway, wet earth and irregular grass, subdued true-to-life colors, fine photographic detail, deep foreground-to-background separation. Vertical 9:16 composition with the lake clearly visible beyond the house. Full scale location photography, natural exposure and soft atmospheric distance, no illustration, no plastic or miniature appearance, no ghosts, no bodies, no colored gas, no text, no watermark. Illustrative reconstruction, not historical evidence.',
 'A lifelike editorial historical reconstruction photograph at human eye level on a narrow street in the City of London in September 1666. One ordinary person in historically plausible wool and linen clothing carrying a cloth bundle toward the river, viewed from behind in the foreground, several other people farther down the uneven muddy lane. A timber-framed building burning far in the background, realistic small flames and rising dark smoke lit by overcast late afternoon, weathered plaster, irregular handmade timber, worn clothes and natural human proportions. Vertical 9:16 full-frame composition, subject in lower middle and tall buildings creating depth, restrained natural film color, candid photographic realism rather than a miniature set. No modern city, no electricity, no St Paul dome, no helmets, no flags, no logos, no writing, no plastic, no video-game rendering, no gore. Illustrative reconstruction, not archival evidence.'
]

def main():
 token=os.environ['CLOUDFLARE_API_TOKEN'];account=os.environ['CLOUDFLARE_ACCOUNT_ID'];out=Path('output/portrait-probe');out.mkdir(parents=True,exist_ok=True)
 records=[]
 for i,prompt in enumerate(PROMPTS):
  r=requests.post(f'https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{MODEL}',headers={'Authorization':'Bearer '+token},files={k:(None,str(v)) for k,v in {'prompt':prompt,'width':1088,'height':1920}.items()},timeout=180)
  row={'scene':i+1,'model':MODEL,'http_status':r.status_code,'requested_dimensions':[1088,1920],'prompt':prompt,'published':False}
  if r.status_code!=200:
   try:row['error_codes']=[x.get('code') for x in r.json().get('errors',[])];row['quota_exhausted']=any('neuron' in str(x.get('message','')).lower() or 'quota' in str(x.get('message','')).lower() for x in r.json().get('errors',[]))
   except ValueError:row['error_codes']=[]
   records.append(row);(out/'report.json').write_text(json.dumps(records,indent=2));print(json.dumps(row),flush=True);raise RuntimeError('Portrait provider unavailable; no repeated quota requests, paid fallback or stock substitution')
  data=r.json() if 'image/' not in r.headers.get('Content-Type','') else None
  raw=r.content if data is None else base64.b64decode(data.get('result',data)['image'])
  with Image.open(io.BytesIO(raw)) as im:
   im.load();row['actual_dimensions']=list(im.size)
   if im.height<=im.width or im.width<1000:raise ValueError('Provider did not return the required portrait image')
   im.convert('RGB').save(out/f'scene-{i+1:02}.jpg',quality=96)
  records.append(row);(out/'report.json').write_text(json.dumps(records,indent=2));print(json.dumps({k:v for k,v in row.items() if k!='prompt'}),flush=True)
if __name__ == '__main__':
    raise SystemExit('Retired production path. Run: python -m motion_factory.produce horror')
