import {test} from 'node:test';
import assert from 'node:assert/strict';
import {proposeTopics,fetchTopicSources} from '../pipeline/trend-radar.mjs';
import {chooseSources,selectTopic} from '../pipeline/topics.mjs';

const signals = {
  trends: [{term: 'مثلث برمودا', news: []}],
  suggestions: [{seed: 'لغز', text: 'لغز سفينة الأشباح ماري سيليست'}, {seed: 'لغز', text: 'قصص'}],
  competitorVideos: [], onThisDay: [], hackerNews: [], reddit: [],
};
const config = {propose: {lang: 'ar', maxCandidates: 5}, excludedTerms: ['قتل حديث']};

test('proposeTopics ranks suggestions first, drops short terms, used topics and excluded terms', () => {
  const ranked = proposeTopics({...signals, trends: [...signals.trends, {term: 'قتل حديث في المدينة', news: []}]}, config, {history: ['مثلث برمودا']});
  assert.equal(ranked[0].topic, 'لغز سفينة الأشباح ماري سيليست');
  assert.ok(!ranked.some(r => r.topic.includes('قتل حديث')));
  assert.ok(!ranked.some(r => r.topic === 'مثلث برمودا'));
  assert.ok(!ranked.some(r => r.topic === 'قصص'));
});

test('fetchTopicSources grounds a proposed topic in Wikipedia summaries', async () => {
  const fetcher = async (url) => {
    if (url.includes('search/page')) return new Response(JSON.stringify({pages: [{key: 'ماري_سيليست', title: 'ماري سيليست'}]}));
    return new Response(JSON.stringify({title: 'ماري سيليست', extract: 'ماري سيليست سفينة تجارية وُجدت مهجورة في المحيط الأطلسي عام 1872 وطاقمها مختفٍ في ظروف غامضة، وأصبحت من أشهر ألغاز البحر في التاريخ الحديث وأثارت نظريات كثيرة عن مصير طاقمها.'.repeat(2), content_urls: {desktop: {page: 'https://ar.wikipedia.org/wiki/ماري_سيليست'}}}));
  };
  const sources = await fetchTopicSources('لغز سفينة الأشباح', config, {fetcher});
  assert.equal(sources.length, 1);
  assert.equal(sources[0].proposed, true);
  assert.ok(sources[0].text.length >= 200);
});

test('chooseSources allowProposed keeps term gates but not the publisher allowlist', () => {
  const source = {id: 'w1', title: 'ماري سيليست', url: 'https://ar.wikipedia.org/wiki/ماري_سيليست', text: 'لغز سفينة ماري سيليست من أشهر الألغاز الغامضة في التاريخ '.repeat(6), published: '2026-11-19T00:00:00Z', official: false, publisher: 'wikipedia.org', primaryRefs: []};
  const cfg = {maxAgeHours: 720, channelRelevance: {enabled: true, minimumMatches: 1, allowedDomains: ['archaeology.org'], blockedDomains: [], excludedTerms: [], requiredTerms: ['لغز']}};
  const rejected = () => chooseSources([source], cfg, {});
  assert.throws(rejected, /NO_CHANNEL_RELEVANT_SOURCE/);
  const chosen = chooseSources([source], cfg, {allowProposed: true});
  assert.equal(chosen.selected.id, 'w1');
  assert.equal(chosen.verification[0].basis, 'proposed_topic_wikipedia_grounding');
});

test('proposed path still hard-excludes victim topics via channel terms', () => {
  const source = {id: 'w2', title: 'قضية حديثة', url: 'https://ar.wikipedia.org/wiki/x', text: 'قصة قتل حديث وقعت هذا العام مع ضحايا حقيقيين '.repeat(6), published: '2026-11-19T00:00:00Z', official: false, publisher: 'wikipedia.org', primaryRefs: []};
  const cfg = {maxAgeHours: 720, channelRelevance: {enabled: true, minimumMatches: 1, allowedDomains: [], blockedDomains: [], excludedTerms: ['قتل حديث'], requiredTerms: ['لغز']}};
  assert.throws(() => chooseSources([source], cfg, {allowProposed: true}), /NO_CHANNEL_RELEVANT_SOURCE/);
});

test('selectTopic falls back to a proposed grounded topic when feeds verify nothing', async () => {
  const fetcher = async (url) => {
    if (url.includes('example.com')) return new Response('<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>');
    if (url.includes('suggestqueries')) return new Response('["لغز",[["لغز سفينة الأشباح ماري سيليست"]]]');
    if (url.includes('search/page')) return new Response(JSON.stringify({pages: [{key: 'ماري_سيليست', title: 'ماري سيليست'}]}));
    if (url.includes('page/summary')) return new Response(JSON.stringify({title: 'ماري سيليست', extract: 'ماري سيليست سفينة وُجدت مهجورة وطاقمها مختفٍ في ظروف غامضة، لغز بحري شهير أثار نظريات كثيرة. '.repeat(4), content_urls: {desktop: {page: 'https://ar.wikipedia.org/wiki/ماري_سيليست'}}}));
    throw Error('FEED_HTTP_404');
  };
  const cfg = {
    profile: 'horror', maxAgeHours: 720,
    feeds: [{url: 'https://example.com/feed', publisher: 'example.com'}],
    channelRelevance: {enabled: true, minimumMatches: 1, allowedDomains: ['archaeology.org'], blockedDomains: [], excludedTerms: [], requiredTerms: ['لغز']},
    trends: {enabled: true, mode: 'propose', autocompleteSeeds: ['لغز'], propose: {lang: 'ar', maxCandidates: 3}, excludedTerms: []},
  };
  const topic = await selectTopic(cfg, [], {fetcher});
  assert.equal(topic.proposedTopic.topic, 'لغز سفينة الأشباح ماري سيليست');
  assert.ok(topic.sources[0].publisher === 'wikipedia.org');
});
