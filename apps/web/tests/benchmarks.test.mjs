import {test} from 'node:test';
import assert from 'node:assert/strict';
import {compare} from '../lib/benchmarks.ts';
const row=(statistics,extra={})=>({configuration_index:0,configuration_name:'a',warmup:false,host_memory_peak_bytes:1024,statistics,...extra});
test('benchmark comparison excludes warmups and failed runs and averages available measurements',()=>{
 const result=compare([row({status:'completed',eval_count:10,eval_duration:1000000000,server_ttft_seconds:.1,server_duration_seconds:1}),row({status:'completed',eval_count:30,eval_duration:1000000000,server_ttft_seconds:.3,server_duration_seconds:3}),row({status:'completed',eval_count:999,eval_duration:1},{warmup:true}),row({status:'failed',eval_count:999,eval_duration:1})]);
 assert.equal(result.length,1);assert.equal(result[0].rate,20);assert.equal(result[0].runs,2);assert.equal(result[0].ttft,.2);assert.equal(result[0].duration,2);
});
test('unknown or zero-duration provider measurements do not produce fabricated rates',()=>{
 const result=compare([row({status:'completed',eval_count:0,eval_duration:0}),row({status:'completed'})]);
 assert.equal(result[0].rate,null);assert.equal(result[0].ttft,null);assert.equal(result[0].duration,null);
});
