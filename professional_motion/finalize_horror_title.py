"""Keep original audio and frames; replace only a revealing intro title."""
import hashlib,json,subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path('professional_motion/output');ROOT.mkdir(exist_ok=True)
NEW='الدور الرابع.. الباب اللي مش بيرجعني البيت'
def run(args):subprocess.run(args,check=True)
def audio_digest(path):
 raw=subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0','-show_packets','-show_entries','packet=data_hash','-show_data_hash','sha256','-of','csv=p=0',str(path)])
 return hashlib.sha256(raw).hexdigest()
def main():
 old=ROOT/'original-1080p.mp4';story=json.loads((ROOT/'story.json').read_text());timing=json.loads((ROOT/'timing.json').read_text());report=json.loads((ROOT/'verification.json').read_text());duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(old)]))
 image=Image.new('RGBA',(1080,1920));d=ImageDraw.Draw(image);d.rounded_rectangle((50,415,1030,495),radius=14,fill=(3,12,19,255),outline=(92,126,127,130),width=1);font=ImageFont.truetype('professional_motion/fonts/NotoSansArabic-Bold.ttf',34);d.text((540,455),NEW,font=font,fill='#f1f0df',anchor='mm',direction='rtl');image.save(ROOT/'safe-intro-title.png')
 output=ROOT/'review-1080p.mp4';run(['ffmpeg','-v','error','-y','-i',str(old),'-loop','1','-i',str(ROOT/'safe-intro-title.png'),'-filter_complex',f"[0:v][1:v]overlay=0:0:enable='lt(t,{timing['scenes'][0]['end']})'[v]",'-map','[v]','-map','0:a:0','-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p','-c:a','copy','-t',str(duration),'-movflags','+faststart',str(output)])
 before=audio_digest(old);after=audio_digest(output)
 if before!=after:raise ValueError('Audio packets changed during title correction')
 run(['ffmpeg','-v','error','-i',str(output),'-f','null','-'])
 report['original_render_story_sha256']=report['story_sha256'];report['source_video_sha256']=hashlib.sha256(old.read_bytes()).hexdigest();story['title']=NEW;raw=json.dumps(story,ensure_ascii=False,indent=2).encode();(ROOT/'final-story.json').write_bytes(raw);report['story_sha256']=hashlib.sha256(raw).hexdigest();report['postproduction_edit']={'scope':'intro title only, above diagram area; avoid revealing the final twist','original_audio_packets_unchanged':True,'audio_packets_sha256':after,'full_decode_passed':True};report['publication_metadata']['title']='ملفات غامضه | '+NEW
 (ROOT/'final-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('Title corrected; audio packet checksum unchanged',after)
if __name__=='__main__':main()
