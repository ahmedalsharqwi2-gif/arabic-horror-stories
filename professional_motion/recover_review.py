"""Correct a reserved review; factual gate precedes any new voice synthesis."""
import json,os,subprocess
from pathlib import Path
from .editorial import ask,evidence,verify_evidence,validate,registry,save,REVIEW
PROFILE=os.environ['REVIEW_PROFILE']
RUN={'horror':'40787353327','history':'40787364902','news':'40786180689'}[PROFILE]
# This is a revision of the same reserved episode, not another daily topic.
subprocess.run(['git','fetch','origin','refs/heads/codex/professional-review-run-'+RUN,'--depth=1'],check=True)
s=json.loads(subprocess.check_output(['git','show','FETCH_HEAD:professional_motion/delivery/story.json']))
SCRIPTS={
'horror':[
('سفينة من غير طاقم','hero','تخيل سفينة ماشية في البحر، والأكل والميه لسه موجودين، بس مفيش حد عليها. دي حكاية ماري سيليست.'),
('رحلة ماكملتش','route','السفينة دي خرجت من نيويورك، ووجهتها كانت جنوة في إيطاليا. لكن اللي حصل لطاقمها فضل لغز.'),
('اكتشاف في الأطلسي','hero','سفينة تانية لقت ماري سيليست تايهة في الأطلسي. هي مااختفتش تحت الميه، اللي اختفى كان الناس.'),
('سجلات وأسئلة','timeline','سجل الرحلة بيساعد الباحثين يتتبعوا الطريق. بس السجل لوحده مش بيقول إيه اللي خلّى الطاقم يمشي.'),
('إعادة تتبع الرحلة','research','باحثين رجعوا لبيانات الطقس ومسار السفينة، عشان يحاولوا يفهموا الرحلة. ده بحث بعد الواقعة، مش شهادة عيان.'),
('مضخة مفككة','pump','على السفينة لقوا مضخة مفككة وميه في القاع. الرسم ده توضيحي للمضخة، مش صورة للمعدة الأصلية.'),
('فرضيات من غير حسم','papers','تفاصيل زي دي فتحت باب لتفسيرات مختلفة. بس وجود تفسير محتمل مش معناه إننا عرفنا السبب بشكل قاطع.'),
('السفينة رجعت.. والناس؟','hero','الغريب إن السفينة اتلاقت وهي عايمة، لكن مصير طاقمها فضل مجهول. هنا بالذات، السؤال أقوى من أي إجابة سهلة.')],
'history':[
('جسر بيشيل ميه','hero','الجسر ده مش مجرد طريق فوق نهر. بون دو جار كان جزء من نظام روماني لنقل الميه.'),
('ثلاثة مستويات','levels','بص على الأقواس اللي فوق بعض. هنا ثلاثة مستويات، والمستوى العلوي هو اللي بيشيل قناة الميه.'),
('القوس من جوه','arch','الرومان استخدموا الأقواس في البناء ده. الرسم التوضيحي بيفصل شكل القوس، عشان نشوف ترتيب أجزائه من غير الزحمة.'),
('الميه من فوق','water','الميه كانت بتعدي في قناة فوق الجسر، والنهر بيجري تحته. دي وظيفتين مختلفتين في نفس المنظر.'),
('وحدات بتتكرر','levels','تكرار الأقواس هو اللي بيدي الجسر شكله المميز. بس بص كويس: الأقواس الصغيرة فوق مختلفة عن الكبيرة تحت.'),
('بناء بالحجر','material','الحجر عنصر أساسي في الصرح ده. المجسم بيفصل كتل توضيحية عشان يقرّب لك فكرة البناء، مش مقاسات أصلية.'),
('نشوف التركيب','assembly','خلينا نفصل المجسم ونرجّعه تاني. دي طريقة لشرح تركيب الجسر، مش تسجيل للخطوات اللي اتنفذت وقت بنائه.'),
('الهندسة اللي فضلت','hero','بون دو جار فضل شاهد على هندسة الرومان في نقل الميه. المرة الجاية تشوف أقواس، اسأل نفسك: كانت بتخدم إيه؟')],
'news':[
('جيميني فور كاربون','chip','جوجل ديب مايند أعلنت عن جيميني فور كاربون. الجديد هنا تركيز على مهام هندسية وبرمجية طويلة، مش مجرد رد سريع.'),
('مهمة بتاخد وقت','flow','الفكرة إن النموذج يتعامل مع شغل محتاج خطوات كتير. الرسم ده توضيحي لتدفق المهمة، مش تصوير لبنية النموذج السرية.'),
('الأمن السيبراني','network','الإعلان بيتكلم كمان عن الأمن السيبراني واكتشاف الثغرات. بس اللي بيقوله المطور لازم نفرّقه عن تقييم مستقل للقدرات.'),
('مقارنة مش دعاية','comparison','لو هنقارن بالإصدارات السابقة، لازم نبص لشروط الاختبار. شكل المجسم هنا شرح للفكرة، مش رسم لنتائج أو نسب جديدة.'),
('طرح بشكل تدريجي','deployment','الوصول للنموذج بيبدأ تدريجي مع شركاء ومدافعين سيبرانيين. عشان كده، الإعلان عنه مش معناه إن كل الناس تقدر تستخدمه فوراً.'),
('التكلفة والاستخدام','flow','المصدر بيعرض تفاصيل لتكلفة الاستخدام. بس قبل ما تبني عليه مشروع، راجع التسعير الحالي وشروط الوصول بنفسك.'),
('حدود محتاجة مراجعة','limits','زي أي نموذج قوي، موضوع السلامة والمخاطر محتاج مراجعة. القدرة المعلنة مش ضمان إن كل نتيجة هتطلع صحيحة.'),
('إيه اللي نتابعه؟','chip','اللي يستاهل المتابعة هو التجارب الفعلية بعد الإتاحة. هل المهام الطويلة هتتحسن في شغلك؟ ده سؤال نحكم عليه بالتجربة.')]}
rows=SCRIPTS[PROFILE]
s['scenes']=[{'id':f'scene-{i+1}','label':label,'visual_mode':mode,'narration':narration,'labels':[]} for i,(label,mode,narration) in enumerate(rows)]
s['title']={'horror':'ماري سيليست: السفينة رجعت.. والناس؟','history':'بون دو جار: جسر بيشيل ميه','news':'جيميني فور كاربون: إيه الجديد فعلاً؟'}[PROFILE]
text=evidence(s['source']['url'])
# Select source excerpt IDs; the model cannot alter quoted source wording.
words=text.split();excerpts=[' '.join(words[i:i+15]) for i in range(0,len(words),15) if len(words[i:i+15])>=5]
quotes_schema={'type':'OBJECT','properties':{'excerpt_ids':{'type':'ARRAY','minItems':8,'maxItems':8,'items':{'type':'INTEGER'}}},'required':['excerpt_ids']}
q=ask('For each of the eight Arabic scenes choose the INDEX of the source excerpt most relevant to its factual subject. Diagram descriptions and cautious research questions are explanatory, not claims about actual measurements. Return eight excerpt_ids, in scene order. DATA:\n'+json.dumps({'scenes':s['scenes'],'excerpts':dict(enumerate(excerpts))},ensure_ascii=False),quotes_schema)
if len(q['excerpt_ids'])!=8:raise ValueError('Eight supporting excerpt IDs required')
for scene,idx in zip(s['scenes'],q['excerpt_ids']):
    if not isinstance(idx,int) or not 0<=idx<len(excerpts):raise ValueError('Invalid source excerpt ID')
    scene['evidence_quote']=excerpts[idx]
verify_evidence(s,text)
row={'family':s['visual_family'],'variant':s['variant'],'key':s['topic_key'],'url':s['source']['url'],'publisher':s['source']['publisher']}
s=validate(s,PROFILE,row)
review=ask('Check all factual claims of each scene against source_text. Explicit illustrative diagram descriptions, general cautions and questions do not assert original historical measurements. Reject any actual unsupported fact. This is an authorized revision of the SAME reserved episode: novel=true, do not compare it against itself. Return supported=false and specific issues if needed. DATA:\n'+json.dumps({'story':s,'source_text':text},ensure_ascii=False),REVIEW)
if review.get('supported') is not True or review.get('issues'):raise ValueError('Corrected script failed independent source review: '+json.dumps(review,ensure_ascii=False))
s['editorial_review']=review;s['revision']='source-checked narration and topic-specific authored visual modes'
p=Path('professional_motion/delivery');p.mkdir(exist_ok=True)
for name in ('narration.wav','narration.source.json','timing.json','error.json'):(p/name).unlink(missing_ok=True)
(p/'story.json').write_text(json.dumps(s,ensure_ascii=False,indent=2))
data=registry();episode=next(r for r in data['episodes'] if r['slot']=='review-'+RUN);episode.update(story=s,title=s['title'],status='reserved');save(data)
print('Corrected complete narration independently source-checked before synthesis')
