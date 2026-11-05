import {test,afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {api,stream} from '../lib/api.ts';
const originalFetch=globalThis.fetch;
afterEach(()=>{globalThis.fetch=originalFetch});
test('stream decodes UTF-8 and split JSON lines and sends auth only when supplied',async()=>{
 const encoded=new TextEncoder().encode('{"type":"token","content":"Türkçe"}\n{"type":"done"}\n');
 let captured;
 globalThis.fetch=async(url,options)=>{captured={url,options};return new Response(new ReadableStream({start(c){for(let i=0;i<encoded.length;i+=3)c.enqueue(encoded.slice(i,i+3));c.close()}}))};
 const events=[];await stream('/chat',{content:'hi'},new AbortController().signal,e=>events.push(e));
 assert.deepEqual(events,[{type:'token',content:'Türkçe'},{type:'done'}]);
 assert.equal(captured.url,'/api/chat');assert.equal(captured.options.headers.Authorization,undefined);
 await stream('/models/pull',{model:'fixture'},new AbortController().signal,()=>{},'secret');
 assert.equal(captured.options.headers.Authorization,'Bearer secret');
});
test('API surfaces validation errors and does not treat errors as stream tokens',async()=>{
 globalThis.fetch=async()=>Response.json({detail:'Administrator token required.'},{status:401});
 await assert.rejects(()=>api('/models/delete'),/Administrator token required/);
 await assert.rejects(()=>stream('/chat',{},new AbortController().signal,()=>assert.fail()),/Administrator token required/);
});
test('stream cancels reader when server error callback throws',async()=>{
 let cancelled=false;
 globalThis.fetch=async()=>new Response(new ReadableStream({start(c){c.enqueue(new TextEncoder().encode('{"type":"error","detail":"OOM"}\n'))},cancel(){cancelled=true}}));
 await assert.rejects(()=>stream('/chat',{},new AbortController().signal,e=>{throw Error(e.detail)}),/OOM/);
 assert.equal(cancelled,true);
});
