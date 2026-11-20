import {test} from 'node:test';
import assert from 'node:assert/strict';
import {sourceRelevance} from '../pipeline/relevance.mjs';

const rule = {enabled: true, minimumMatches: 1, requiredTerms: ['لغز'], excludedTerms: ['قتل حديث']};

test('proposed topics match requiredTerms in title scope only', () => {
  const body = {title: 'المغامرون الخمسة', url: 'https://ar.wikipedia.org/wiki/x', text: 'سلسلة قصص مغامرات فيها لغز تاريخي كامل'};
  assert.equal(sourceRelevance(body, rule, '', {requiredTermsInTitleOnly: true}).accepted, false, 'body-only term match must not accept a proposed topic');
  assert.equal(sourceRelevance(body, rule, '').accepted, true, 'feed behavior unchanged: full-body match still accepts');
  assert.equal(sourceRelevance({...body, title: 'لغز المغامرون الخمسة'}, rule, '', {requiredTermsInTitleOnly: true}).accepted, true, 'title match accepts');
});

test('excluded terms still scan the full body in title-only mode', () => {
  const s = {title: 'لغز قديم', url: 'https://ar.wikipedia.org/wiki/y', text: 'تقرير عن قتل حديث في المدينة'};
  const d = sourceRelevance(s, rule, '', {requiredTermsInTitleOnly: true});
  assert.equal(d.accepted, false);
  assert.equal(d.reason, 'excluded_channel_topic');
});
