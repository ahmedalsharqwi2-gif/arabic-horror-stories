import {test} from 'node:test';import assert from 'node:assert/strict';import {mkdtemp,readFile,rm} from 'node:fs/promises';import os from 'node:os';import path from 'node:path';
import {script} from '../pipeline/providers.mjs';
const config={name:'test-channel',profile:'documented_history'};
const topic={editorialMode:'daily',sources:[{id:'s1',title:'t',url:'https://example.com/a',text:'x'.repeat(80),published:'2026-11-19',official:true}]};
test('script writes zod diagnostics for a response missing scenes',async()=>{
 const dir=await mkdtemp(path.join(os.tmpdir(),'scriptdiag-'));
 try{
  const client={config:{voice:{}},generate:async()=>({candidates:[{content:{parts:[{text:JSON.stringify({topicKey:'k1',title:'t',hook:'h',cta:'c'})}]}}],_pipeline:{model:'fake'}})};
  const diagnosticsPath=path.join(dir,'script-diagnostics.json');
  await assert.rejects(()=>script(topic,config,[],{client,diagnosticsPath}),err=>err.message==='SCRIPT_SCHEMA_INVALID');
  const diag=JSON.parse(await readFile(diagnosticsPath,'utf8'));
  assert.equal(diag.code,'SCRIPT_SCHEMA_INVALID');
  assert.ok(diag.zodIssues.some(i=>(i.path||[]).join('.')==='scenes'),'diagnostics must name the missing field');
 }finally{await rm(dir,{recursive:true,force:true});}
});
