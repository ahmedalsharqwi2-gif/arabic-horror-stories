import {normalized} from './policy.mjs';
const domainMatches=(hostname,domain)=>hostname===domain||hostname.endsWith('.'+domain);
export function sourceRelevance(source,rule,extraText='',opts={}){
 if(!rule?.enabled)return {accepted:true,reason:'no_channel_rule_required',matchedTerms:[]};
 let hostname;try{hostname=new URL(source.url).hostname.toLowerCase();}catch{return {accepted:false,reason:'invalid_source_url',matchedTerms:[]};}
 if((rule.blockedDomains||[]).some(d=>domainMatches(hostname,d)))return {accepted:false,reason:'blocked_source_domain',matchedTerms:[]};
 if(rule.allowedDomains?.length&&!rule.allowedDomains.some(d=>domainMatches(hostname,d)))return {accepted:false,reason:'source_domain_not_in_channel_profile',matchedTerms:[]};
 const fullText=normalized([source.title||'',source.text||'',extraText].join(' '));
 const excluded=(rule.excludedTerms||[]).filter(t=>fullText.includes(normalized(t)));
 if(excluded.length)return {accepted:false,reason:'excluded_channel_topic',matchedTerms:[],excludedTerms:excluded};
 // Proposed (trend-radar) topics ground on a full Wikipedia article; a long
 // body trivially contains one loose term (e.g. a children's adventure series
 // matching "لغز" inside "ألغاز"), so for them requiredTerms must match the
 // TITLE scope only. Excluded terms still scan the full text. Stricter-only.
 const termText=opts.requiredTermsInTitleOnly?normalized([source.title||'',extraText].join(' ')):fullText;
 const matchedTerms=(rule.requiredTerms||[]).filter(t=>termText.includes(normalized(t)));
 return {accepted:matchedTerms.length>=(rule.minimumMatches||1),reason:matchedTerms.length>=(rule.minimumMatches||1)?'channel_terms_and_domain_match':'no_channel_terms',matchedTerms};
}
export function requireRelevantSources(sources,rule){
 const decisions=sources.map(source=>({id:source.id,url:source.url,...sourceRelevance(source,rule)}));
 if(!sources.length||decisions.some(d=>!d.accepted)){const e=Error('NO_CHANNEL_RELEVANT_SOURCE');e.sourceDiagnostics={channelRelevance:decisions};throw e;}
 return decisions;
}
