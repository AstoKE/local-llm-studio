import type {Page} from '@playwright/test';
export const configuration={options:{temperature:.8,top_k:40,top_p:.9,min_p:0,repeat_penalty:1.1,num_ctx:4096,num_predict:512,seed:-1,stop:[]},system_prompt:'',keep_alive:300};
export async function installFixtures(page:Page,{preferencesFail=false,longReply=false}={}){
 const models=Array.from({length:4},(_,i)=>({name:`fixture-${i+1}:latest`}));
 const conversations=new Map<number,Record<string,unknown>>();let nextId=1;
 const reply=longReply?Array.from({length:50},(_,i)=>`Fixture paragraph ${i+1}: browser layout verification.`).join('\n\n'):'Fixture response from the browser test.';
 const system={sampled_at:new Date().toISOString(),cpu_percent:12,cpu_count:4,memory_used:2*1024**3,memory_available:6*1024**3,memory_total:8*1024**3,memory_percent:25,gpu:null,gpu_note:'Fixture: no GPU'};
 await page.route('**/api/**',async route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname,method=request.method();
  const body=method==='GET'?{}:request.postDataJSON()??{};
  const json=(value:unknown,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(value)});
  if(path==='/api/dashboard')return json({ollama:{connected:true,version:'fixture',models,loaded:[],error:null},system,conversations:[],benchmarks:[],active_jobs:0});
  if(path==='/api/models')return json({models});
  if(path==='/api/preferences')return preferencesFail?json({detail:'Fixture missing preferences'},404):json({default_model:models[1].name,configuration,theme:'dark'});
  if(path==='/api/model-preferences')return json(null);
  if(path==='/api/presets')return json([]);
  if(path==='/api/auth/me')return json({authenticated:false,role:'local',lan_mode:false,password_configured:true});
  if(path==='/api/conversations'&&method==='GET')return json([...conversations.values()]);
  if(path==='/api/conversations'&&method==='POST'){const c={...body,id:nextId++,messages:[]};conversations.set(c.id,c);return json(c,201)}
  if(/^\/api\/conversations\/\d+$/.test(path)){const id=Number(path.split('/').at(-1));if(method==='DELETE'){conversations.delete(id);return json({deleted:true})}return json(conversations.get(id)??{detail:'Missing'},conversations.has(id)?200:404)}
  if(path==='/api/conversation-snapshots'){const c={...body,id:nextId++};conversations.set(c.id,c);return json(c,201)}
  if(path==='/api/chat'){
   const statistics={status:'completed',eval_count:12,eval_duration:1000000000,server_ttft_seconds:.1};
   const c=conversations.get(body.conversation_id);
   if(c){const messages=c.messages as Record<string,unknown>[];messages.push({id:messages.length+1,role:'user',content:body.content},{id:messages.length+2,role:'assistant',content:reply,statistics})}
   return route.fulfill({contentType:'application/x-ndjson',body:JSON.stringify({type:'token',content:reply})+'\n'+JSON.stringify({type:'done',statistics})+'\n'});
  }
  if(path==='/api/monitoring')return json({current:system,system_history:[system],runs:[],models:[],active_jobs:0,stale:false,sampler_error:null,has_more:false,interval_seconds:5,retention_hours:24});
  if(path==='/api/benchmarks')return json({items:[],has_more:false});
  return json({detail:`Unhandled browser fixture: ${method} ${path}`},404);
 });
 return {models,conversations,reply};
}
