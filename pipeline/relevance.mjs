import {normalized} from './policy.mjs';
const domainMatches=(hostname,domain)=>hostname===domain||hostname.endsWith('.'+domain);
export function sourceRelevance(source,rule){
 if(!rule?.enabled)return {accepted:true,reason:'no_channel_rule_required',matchedTerms:[]};
 let hostname;try{hostname=new URL(source.url).hostname.toLowerCase();}catch{return {accepted:false,reason:'invalid_source_url',matchedTerms:[]};}
 if((rule.blockedDomains||[]).some(d=>domainMatches(hostname,d)))return {accepted:false,reason:'blocked_source_domain',matchedTerms:[]};
 if(rule.allowedDomains?.length&&!rule.allowedDomains.some(d=>domainMatches(hostname,d)))return {accepted:false,reason:'source_domain_not_in_channel_profile',matchedTerms:[]};
 const text=normalized([source.title||'',source.text||''].join(' '));
 const excluded=(rule.excludedTerms||[]).filter(t=>text.includes(normalized(t)));
 if(excluded.length)return {accepted:false,reason:'excluded_channel_topic',matchedTerms:[],excludedTerms:excluded};
 const matchedTerms=(rule.requiredTerms||[]).filter(t=>text.includes(normalized(t)));
 return {accepted:matchedTerms.length>=(rule.minimumMatches||1),reason:matchedTerms.length>=(rule.minimumMatches||1)?'channel_terms_and_domain_match':'no_channel_terms',matchedTerms};
}
export function requireRelevantSources(sources,rule){
 const decisions=sources.map(source=>({id:source.id,url:source.url,...sourceRelevance(source,rule)}));
 if(!sources.length||decisions.some(d=>!d.accepted)){const e=Error('NO_CHANNEL_RELEVANT_SOURCE');e.sourceDiagnostics={channelRelevance:decisions};throw e;}
 return decisions;
}
