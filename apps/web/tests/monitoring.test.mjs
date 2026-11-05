import {test} from 'node:test';
import assert from 'node:assert/strict';
import {numeric,seconds,gib,historyPoints} from '../lib/monitoring.ts';
test('absent provider metrics stay unknown, zero is a valid measurement',()=>{
 assert.equal(numeric(undefined),'—');assert.equal(numeric(null),'—');assert.equal(numeric(0),'0');
 assert.equal(seconds(undefined),null);assert.equal(seconds(2500000000),2.5);assert.equal(gib(1024**3),'1 GiB');
});
test('GPU history selects stable device identity and preserves missing samples',()=>{
 const time='2026-11-05T10:00:00Z';
 const base={sampled_at:time,cpu_percent:30,memory_percent:50};
 const points=historyPoints([{...base,gpu:[{id:'a',utilization:12,memory_used_mib:1024},{id:'b',utilization:81,memory_used_mib:2048}]},{...base,gpu:null},{...base,gpu:[{id:'b',utilization:0,memory_used_mib:0}]}],'b');
 assert.equal(points[0].gpu,81);assert.equal(points[0].vram,2);assert.equal(points[1].gpu,null);assert.equal(points[1].vram,null);assert.equal(points[2].gpu,0);assert.equal(points[2].vram,0);
});
