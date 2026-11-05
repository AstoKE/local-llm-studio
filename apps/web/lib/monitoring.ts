export type Gpu={id:string;name:string;source:string;utilization:number|null;memory_used_mib:number|null;memory_total_mib:number|null};
export type SystemSample={id?:number;sampled_at:string;cpu_percent:number;cpu_count:number;memory_used:number;memory_available:number;memory_total:number;memory_percent:number;gpu:Gpu[]|null;gpu_note:string|null;active_jobs?:number};
export type Statistics={status:'completed'|'failed'|'interrupted';eval_count?:number;eval_duration?:number;prompt_eval_count?:number;prompt_eval_cached_count?:number;prompt_eval_duration?:number;load_duration?:number;total_duration?:number;server_ttft_seconds?:number;server_duration_seconds?:number};
export type Run={id:number;created_at:string;model:string;source:string;statistics:Statistics;tokens_per_second:number|null};
export type MonitoringData={current:SystemSample;system_history:SystemSample[];runs:Run[];models:string[];active_jobs:number;stale:boolean;sampler_error:string|null;has_more:boolean;interval_seconds:number;retention_hours:number};
export function numeric(value:number|null|undefined,digits=1):string{return value==null?'—':value.toLocaleString(undefined,{maximumFractionDigits:digits})}
export function seconds(ns:number|undefined):number|null{return ns==null?null:ns/1e9}
export function gib(bytes:number|null|undefined):string{return bytes==null?'—':`${numeric(bytes/1024**3)} GiB`}
export function historyPoints(history:SystemSample[],gpuId?:string){return history.map(s=>{const gpu=s.gpu?.find(g=>g.id===gpuId);return {time:new Date(s.sampled_at).getTime(),cpu:s.cpu_percent,ram:s.memory_percent,gpu:gpu?.utilization??null,vram:gpu?.memory_used_mib!=null?gpu.memory_used_mib/1024:null}})}
