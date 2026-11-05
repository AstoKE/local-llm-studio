export async function api<T>(path:string, init?:RequestInit):Promise<T>{
 const r=await fetch(`/api${path}`,{...init,headers:{'Content-Type':'application/json',...init?.headers}});
 if(!r.ok){const body=await r.json().catch(()=>({}));throw Error(typeof body.detail==='string'?body.detail:`Request failed (${r.status})`)}
 return r.json() as Promise<T>;
}
export async function stream(path:string,body:unknown,signal:AbortSignal,onEvent:(event:Record<string,unknown>)=>void,token?:string){
 const r=await fetch(`/api${path}`,{method:'POST',signal,headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},body:JSON.stringify(body)});
 if(!r.ok){const b=await r.json().catch(()=>({}));throw Error(typeof b.detail==='string'?b.detail:`Request failed (${r.status})`)}
 if(!r.body)throw Error('Streaming is unavailable');
 const reader=r.body.getReader(),decoder=new TextDecoder();let pending='';
 try{for(;;){const {done,value}=await reader.read();pending+=decoder.decode(value,{stream:!done});const lines=pending.split('\n');pending=lines.pop()??'';for(const line of lines)if(line.trim())onEvent(JSON.parse(line));if(done){if(pending.trim())onEvent(JSON.parse(pending));break}}}finally{await reader.cancel().catch(()=>{});reader.releaseLock()}
}
