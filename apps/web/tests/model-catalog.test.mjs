import {test,afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {loadModelCatalog} from '../lib/model-catalog.ts';
const originalFetch=globalThis.fetch;
afterEach(()=>{globalThis.fetch=originalFetch});
const models=[{name:'fixture-a:latest'},{name:'fixture-b:latest'},{name:'fixture-c:latest'},{name:'fixture-d:latest'}];
test('all installed models remain available when preferences endpoint fails',async()=>{
 globalThis.fetch=async path=>path==='/api/models'?Response.json({models}):Response.json({detail:'Not Found'},{status:404});
 let displayed=[];
 const result=await loadModelCatalog(value=>{displayed=value});
 assert.deepEqual(displayed,models);
 assert.equal(result.value,null);
 assert.match(result.warning,/Default settings could not be loaded/);
});
test('model list is published before slow optional preferences resolve',async()=>{
 let finishPreferences;
 const preferences=new Promise(resolve=>{finishPreferences=resolve});
 globalThis.fetch=async path=>path==='/api/models'?Response.json({models}):preferences;
 let publish;
 const published=new Promise(resolve=>{publish=resolve});
 const loaded=loadModelCatalog(value=>publish(value));
 assert.deepEqual(await published,models);
 finishPreferences(Response.json({default_model:'fixture-c:latest',configuration:{}}));
 assert.equal((await loaded).value.default_model,'fixture-c:latest');
});
test('provider failure is surfaced even if preferences are unavailable',async()=>{
 globalThis.fetch=async path=>path==='/api/models'?Response.json({detail:'Ollama unavailable'},{status:503}):Response.json({detail:'Not Found'},{status:404});
 await assert.rejects(()=>loadModelCatalog(()=>assert.fail('No models returned')),/Ollama unavailable/);
});
