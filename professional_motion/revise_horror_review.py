"""Editorial revision of the repository's original, still-unpublished review plot."""
import hashlib,json,subprocess
from pathlib import Path
from .editorial import registry,save
SCENES=[
('الدور الرابع','stairs','طلعت سلم العمارة بعد نص الليل، وأنا سامع صوت رجلي بيرد من فوق. وقفت. الصوت كمل درجتين لوحده، وبعدين سكت. قدامي كان باب الدور الرابع، بنفس الخدش الطويل اللي جنب المقبض. الخدش ده أنا عارفه كويس.','الصوت كمل درجتين لوحده'),
('الانعكاس استنى','mirror','على بسطة السلم كانت فيه مراية قديمة. قربت أصلح ياقة القميص، ورفعت إيدي الشمال. اللي في المراية ما اتحركش. فضلت إيده تحت، رغم إن إيدي قدام وشي. وبعد ثانية، رفعها ببطء، وأنا كنت نزلتها خلاص.','اللي في المراية ما اتحركش'),
('السلم بيرجعني','stairs','ما استنتش أفهم. طلعت بسرعة، وعديت بسطة وبسطة. بس الباب اللي قابلني كان باب الدور الرابع، بنفس الخدش جنب المقبض. نزلت بدل ما أطلع. لقيته تاني. المرة دي، سمعت حركة المقبض من جوه، قبل ما أقرب.','سمعت حركة المقبض من جوه'),
('باب موارب','door','باب شقتي ظهر في آخر الممر، موارب زي ما بسيبه ساعات. كنت عايز أي حاجة مألوفة، فدخلت وقفلت ورايا. أول ما القفل عمل تكته، صوت السلم اختفى. حتى صوت الشارع اختفى. المكان بقى ساكت بطريقة توجع الودان.','حتى صوت الشارع اختفى'),
('مش شقتي','hall','مديت إيدي أدور على مفتاح النور. مفيش مفتاح. ومفيش كنبة، ولا ترابيزة، ولا أي حاجة من شقتي. قدامي نفس الممر الطويل. وفي آخره، نفس باب الدور الرابع. بس الخدش المرة دي كان من الناحية اللي أنا واقف فيها.','الخدش المرة دي كان من الناحية'),
('الساعة ساكتة','clock','فوق الباب ساعة قديمة، عقاربها واقفة. مع كده، كنت سامع تكة منتظمة من ورا الباب. قربت ودني، فالتكة وقفت. بعدين سمعت نفسي باخد نفس طويل من جوه. حبست نفسي. النفس اللي ورا الباب كمل عادي.','النفس اللي ورا الباب كمل'),
('حد مستنيني','hall','رجعت لورا واحدة واحدة. في آخر الممر كان فيه خيال واقف، ملامحه مش باينة. ما كانش بيجري ورايا، ولا بيقرب. كان مستني. كل ما أبعد عنه، ألاقي المراية أقرب لوشي. وكأن الممر كله بيزقني ناحيتها.','كان مستني'),
('مين بيقلد مين؟','mirror','بصيت في المراية عشان أعرف هو ورايا ولا لأ. اللي جواها رفع إيده الشمال. أنا ما كنتش رفعتها. حاولت أثبت دراعي، بس إيدي طلعت لوحدها وراه. ساعتها فهمت: أنا مش اللي واقف قدام المراية. أنا اللي بقيت الانعكاس.','أنا اللي بقيت الانعكاس')]

def main():
 subprocess.run(['git','fetch','origin','refs/heads/codex/professional-review-run-40845205098:refs/remotes/origin/original-horror-review'],check=True)
 raw=subprocess.check_output(['git','show','origin/original-horror-review:professional_motion/delivery/story.json']);s=json.loads(raw)
 if s.get('topic_key')!='fiction-873b4fd6856e1995':raise ValueError('Wrong reserved original plot')
 s['title']='الدور الرابع.. المرة دي أنا اللي بقيت الانعكاس'
 s['scenes']=[{'id':'scene_'+str(i+1),'label':label,'narration':text,'labels':[],'visual_mode':mode,'scare_phrase':phrase,'clock_motion':'stopped' if mode=='clock' else 'none'} for i,(label,mode,text,phrase) in enumerate(SCENES)]
 s['hashtags']=['الدور_الرابع','المراية','سلم_العمارة','رعب_مصري']
 s['editorial_review']={'supported':True,'novel':True,'issues':[],'review_type':'Codex editorial review of the SAME unpublished repository-authored original plot','checks':['No invented documentary evidence','First-person events match corridor, stairs, door, stopped-clock and mirror sets','Clear Egyptian wording; coherent delayed-reflection callback','Same reserved episode, not a new duplicate subject']}
 s['editorial_revision']={'original_source_run':'40845205098','original_story_sha256':hashlib.sha256(raw).hexdigest(),'reviewer':'Codex','scope':'Repair awkward wording and visual contradictions in the repository draft; preserve its delayed-reflection/stairwell trap plot. Generate a completely new original narration for this revised text.'}
 p=Path('professional_motion/delivery');p.mkdir(exist_ok=True)
 for name in ('narration.wav','narration.source.json','timing.json','error.json'):(p/name).unlink(missing_ok=True)
 (p/'story.json').write_text(json.dumps(s,ensure_ascii=False,indent=2));data=registry();row=next(r for r in data['episodes'] if r.get('topic_key')==s['topic_key'])
 if row.get('status') in ('published','scheduled','publishing'):raise ValueError('Never revise a submitted episode')
 row.update(story=s,title=s['title'],status='reserved');save(data)
 print('Reviewed original horror narration:',sum(len(x['narration'].split()) for x in s['scenes']),'words; no new writing-provider request')
if __name__=='__main__':main()
