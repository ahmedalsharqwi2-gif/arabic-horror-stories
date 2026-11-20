// Vertical slice for the pro-motion spec: 7 scenes, paper-technical (light) theme,
// storyboard.json first, validated plan, zone check, render, motion QA.
// Silent preview (no local TTS keys): synthetic word timings.
import {writeFile} from 'node:fs/promises';
import {renderEpisode} from './pipeline/render.mjs';
import {validatePlan} from './pipeline/drawplan.mjs';
import {camTargetsFor, zoneViolations} from './src/paper/camera.js';
import {buildStoryboard, validateStoryboard} from './director/storyboard.mjs';
import {check as motionCheck} from './pipeline/motion-qa.mjs';

const sceneTexts = [
  'في قلب غابات بيليز عاشت كاراكول واحدة من أعظم مدن المايا',
  'المدينة كان بيسكنها أكتر من مائة ألف نسمة في أوج قوتها',
  'علماء الآثار لقوا شبكة طرق واسعة بتربط كاراكول بضواحيها',
  'تقنية الليدار كشفت مباني مدفونة تحت الغابة من غير حفر',
  'السبب الأرجح للانهيار جفاف طويل ضرب الزراعة والمياه',
  'النقوش لسه بتحكي عن ملوك وحروب وتحالفات قديمة',
  'الغابة بلعت المدينة ولسه بتحتفظ بأسرارها لحد النهارده',
];
const meta = [
  {title: 'رصد غامض', summary: 'الصوت الأول', keyword: 'الرصد', template: 'phenomenon', labels: ['الرصد', 'المحيط']},
  {title: 'أعلى صوت', summary: 'خمسة آلاف كم', keyword: 'خمسة', template: 'stat', labels: ['خمسة', 'كيلومتر'], values: [{v: '5000', l: 'كيلومتر'}]},
  {title: 'تخمينات', summary: 'كائن مجهول؟', keyword: 'كائن', template: 'phenomenon', labels: ['كائن', 'خندق']},
  {title: 'مقارنة الترددات', summary: 'بلا نتيجة', keyword: 'الترددات', template: 'comparison', labels: ['الترددات', 'مقارنة']},
  {title: 'الحقيقة', summary: 'جليد ينشق', keyword: 'جليد', template: 'cause', labels: ['جليد', 'مطابقة']},
  {title: 'أسئلة باقية', summary: 'لغز مستمر', keyword: 'الأسئلة', template: 'journey', labels: ['الأسئلة', 'لغز']},
  {title: 'القاع يخبي', summary: 'أسرار المحيط', keyword: 'أسرار', template: 'quote', labels: ['أسرار', 'المحيط']},
];
const DUR = 8;
const scenes = sceneTexts.map((text, i) => {
  const ws = text.split(' ');
  return {...meta[i], text, duration: DUR, words: ws.map((w, k) => ({text: w, start: k * (DUR - 1) / ws.length, end: (k + 1) * (DUR - 1) / ws.length})), labels: meta[i].labels, kind: (i===2||i===5)?'legend':'fact', sourceLabel: ['unesco.org','britannica.com','nature.com','nasa.gov','cambridge.org','chase1985','metmuseum.org'][i]};
});
const props = {
  title: 'الملف رقم ٧: إزاي مدينة كاملة اختفت من غير أثر؟',
  seriesLabel: 'ملفات غامضة', channelName: 'ملفات غامضة',
  scenes, durationInFrames: scenes.length * DUR * 30, mascot: false,
  paper: {theme: 'ink-dark', citations: true, topBar: true, logoPath: 'brand/logo/logo.jpg', chapterLabel: 'الملف'},
};
const storyboard = buildStoryboard(props);
const sbProblems = validateStoryboard(storyboard);
if (sbProblems.length) { console.error('STORYBOARD INVALID:', sbProblems); process.exit(1); }
await writeFile('/tmp/horror-slice-out/storyboard.json', JSON.stringify(storyboard, null, 2));
console.log('storyboard ok:', storyboard.scenes.map(s => s.template).join(', '));

const plan = {
  strokes: [
    {d: 'M 180 1240 C 350 1150, 500 1180, 640 1060 C 760 960, 820 900, 880 820', width: 4, color: 'ink'},
    {d: 'M 620 520 L 540 660 L 700 660 Z', width: 5, color: 'ink'},
    {d: 'M 590 590 L 650 590', width: 3, color: 'gold'},
    {d: 'M 150 500 C 220 460, 300 470, 340 520', width: 3, color: 'green'},
    {d: 'M 160 560 C 240 520, 320 540, 360 580', width: 3, color: 'green'},
  ],
  fills: [
    {shape: 'path', d: 'M 120 1250 C 320 1200, 560 1270, 760 1210 C 880 1175, 960 1210, 980 1200 L 980 1480 L 120 1480 Z', color: 'green', opacity: 0.4, hatch: true},
    {shape: 'circle', cx: 640, cy: 1060, r: 12, color: 'red', delay: 10},
  ],
  marks: [
    {x: 180, y: 1240, r: 7, color: 'red', delay: 6},
    {x: 880, y: 820, r: 7, color: 'gold', delay: 9},
    {x: 620, y: 590, r: 6, color: 'ink', delay: 12},
  ],
  labels: [
    {x1: 640, y1: 1060, x2: 760, y2: 990, text: 'كاراكول'},
    {x1: 300, y1: 1330, x2: 420, y2: 1410, text: 'غابات بيليز'},
  ],
  annotations: [
    {type: 'circle', x: 620, y: 590, r: 110, delay: 30, color: 'gold'},
    {type: 'arrow', x1: 850, y1: 1150, x2: 700, y2: 1080, delay: 25, color: 'red'},
    {type: 'pip', x: 250, y: 460, w: 260, h: 150, delay: 35, text: 'وثيقة أثرية'},
  ],
  scenes: [
    {strokes: [{d: 'M 720 540 C 800 570, 800 590, 720 640', width: 3, color: 'cyan'}, {d: 'M 400 540 C 340 560, 340 580, 400 600', width: 3, color: 'cyan'}, {d: 'M 200 760 C 400 730, 640 780, 880 740', width: 2, color: 'starBlue'}, {d: 'M 200 820 C 420 790, 660 840, 880 800', width: 2, color: 'cyan'}], fills: [], marks: [{x: 250, y: 745, r: 5, color: 'cyan', delay: 40}, {x: 830, y: 785, r: 5, color: 'gold', delay: 80}, {x: 500, y: 770, r: 4, color: 'starBlue', delay: 130}], labels: [], annotations: []},
    {strokes: [{d: 'M 380 900 L 700 900', width: 4, color: 'gold'}, {d: 'M 380 950 L 640 950', width: 3, color: 'cyan'}], fills: [], marks: [{x: 700, y: 900, r: 8, color: 'gold', delay: 8}], labels: [{x1: 700, y1: 900, x2: 760, y2: 830, text: 'خمسة آلاف'}], annotations: []},
    {strokes: [{d: 'M 380 1100 C 420 1050, 480 1050, 500 1100 C 520 1150, 460 1180, 420 1160 Z', width: 4, color: 'ink'}], fills: [], marks: [{x: 440, y: 1120, r: 6, color: 'gold', delay: 5}], labels: [], annotations: []},
    {strokes: [{d: 'M 300 800 C 400 780, 500 820, 600 800', width: 3, color: 'cyan'}, {d: 'M 300 860 C 400 890, 500 850, 600 870', width: 3, color: 'gold'}], fills: [], marks: [], labels: [{x1: 600, y1: 800, x2: 700, y2: 750, text: 'تردد معروف'}, {x1: 600, y1: 870, x2: 700, y2: 930, text: 'تردد اللغز'}], annotations: []},
    {strokes: [{d: 'M 620 1080 L 700 1000 L 780 1080 L 700 1140 Z', width: 4, color: 'starBlue'}], fills: [{shape: 'circle', cx: 700, cy: 1070, r: 9, color: 'gold', delay: 6}], marks: [], labels: [{x1: 700, y1: 1070, x2: 596, y2: 1072, text: 'انشقاق الجليد'}], annotations: []},
    {strokes: [{d: 'M 420 700 C 460 660, 540 660, 580 700 C 540 740, 460 740, 420 700 Z', width: 3, color: 'cyan'}], fills: [], marks: [{x: 500, y: 700, r: 5, color: 'gold', delay: 4}], labels: [], annotations: []},
    {strokes: [{d: 'M 200 1000 C 400 950, 600 1030, 880 980', width: 3, color: 'ink'}, {d: 'M 200 1060 C 400 1010, 600 1090, 880 1040', width: 2, color: 'cyan'}], fills: [], marks: [], labels: [], annotations: []},
  ],
  endStat: 'اختفاء بلا تفسير',
  summaryPoints: ['كاراكول كانت من أعظم مدن المايا', 'الليدار كشف المدينة من غير حفر', 'الجفاف الطويل هو السبب الأرجح'],
};
const problems = validatePlan(plan, scenes.length);
if (problems.length) { console.error('PLAN INVALID:', problems); process.exit(1); }
props.paper.plan = plan;
const windows = scenes.map((s, i) => ({start: i * DUR * 30, frames: DUR * 30}));
const layers = [{strokes: plan.strokes, fills: plan.fills, marks: plan.marks, labels: plan.labels, annotations: plan.annotations}, ...plan.scenes];
const targets = camTargetsFor(windows, layers);
const violations = zoneViolations(windows, layers, targets);
if (violations.length) { console.error('ZONE VIOLATIONS:', violations.slice(0, 10)); process.exit(1); }
console.log('zone check clean; scales:', targets.map(t => t.s.toFixed(2)).join(', '));
const t0 = Date.now();
const result = await renderEpisode(props, '/tmp/horror-slice-out', {filename: 'vertical-slice.mp4'});
const secs = (Date.now() - t0) / 1000;
console.log('rendered', result.file, 'in', secs, 's');
const qa = motionCheck(result.file, scenes.map(() => ({duration: DUR})), {out: '/tmp/horror-slice-out/motion-qa.json'});
console.log('motion-qa passed:', qa.passed, qa.scenes.map(s => s.meanDiff).join(','));
if (!qa.passed) process.exit(1);
