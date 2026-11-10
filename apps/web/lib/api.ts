async function responseError(response:Response):Promise<Error>{
 const body:unknown=await response.json().catch(()=>null);
 if(body&&typeof body==='object'&&'detail' in body){
  const detail=body.detail;
  if(typeof detail==='string')return Error(detail);
  if(Array.isArray(detail)){
   const messages=detail.map((item:unknown)=>{if(!item||typeof item!=='object'||!('msg' in item))return '';const path='loc' in item&&Array.isArray(item.loc)?item.loc.join('.'):'';return `${path?`${path}: `:''}${String(item.msg)}`}).filter(Boolean);
   if(messages.length)return Error(messages.join('; '));
  }
 }
 return Error(`Request failed (${response.status})`);
}
export async function api<T>(path:string, init?:RequestInit):Promise<T>{
 const r=await fetch(`/api${path}`,{cache:'no-store',...init,headers:{'Content-Type':'application/json',...init?.headers}});
 if(!r.ok)throw await responseError(r);
 return r.json() as Promise<T>;
}
export async function stream(path:string,body:unknown,signal:AbortSignal,onEvent:(event:Record<string,unknown>)=>void,token?:string){
 const r=await fetch(`/api${path}`,{method:'POST',signal,headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},body:JSON.stringify(body)});
 if(!r.ok)throw await responseError(r);
 if(!r.body)throw Error('Streaming is unavailable');
 const reader=r.body.getReader(),decoder=new TextDecoder();let pending='';
 try{for(;;){const {done,value}=await reader.read();pending+=decoder.decode(value,{stream:!done});const lines=pending.split('\n');pending=lines.pop()??'';for(const line of lines)if(line.trim())onEvent(JSON.parse(line));if(done){if(pending.trim())onEvent(JSON.parse(pending));break}}}finally{await reader.cancel().catch(()=>{});reader.releaseLock()}
}
