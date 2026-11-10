// @refresh reset
'use client';
import {useEffect,useRef,useState} from 'react';
import {ArrowUp,Check,Copy,PanelLeft,Pencil,RotateCcw,RefreshCw,Search,SlidersHorizontal,Sparkles,Square,SquarePen,Trash2,X} from 'lucide-react';
import {api,stream} from '@/lib/api';
import {loadModelCatalog} from '@/lib/model-catalog';
import {Button} from './ui/button';
import {Configuration,defaults,InferenceSettings} from './inference-settings';
import {Markdown} from './markdown';
type Message={id?:number;role:'user'|'assistant';content:string;statistics?:Record<string,unknown>};
type Conversation={id:number;title:string;model:string;configuration:Configuration;messages?:Message[]};
export function ChatWorkspace({playground=false}:{playground?:boolean}){
const[models,setModels]=useState<{name:string}[]>([]),[model,setModel]=useState(''),[config,setConfig]=useState(defaults),[conversations,setConversations]=useState<Conversation[]>([]),[current,setCurrent]=useState<Conversation|null>(null),[messages,setMessages]=useState<Message[]>([]),[input,setInput]=useState(''),[search,setSearch]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[copied,setCopied]=useState<number|null>(null),[notice,setNotice]=useState(''),[modelsLoading,setModelsLoading]=useState(true),[mobilePanel,setMobilePanel]=useState<'chat'|'conversations'>('chat'),[settingsOpen,setSettingsOpen]=useState(false);const controller=useRef<AbortController|null>(null),messageList=useRef<HTMLDivElement|null>(null),followOutput=useRef(true),settingsToggle=useRef<HTMLButtonElement|null>(null),composer=useRef<HTMLTextAreaElement|null>(null),catalogVersion=useRef(0),selectionVersion=useRef(0),applicationDefaults=useRef<Configuration>(defaults());
useEffect(()=>{const textarea=composer.current;if(textarea){textarea.style.height='auto';textarea.style.height=`${Math.min(textarea.scrollHeight,160)}px`}},[input]);
async function list(){setConversations(await api('/conversations'))}
async function loadModels(){
 const request=++catalogVersion.current,selection=selectionVersion.current;
 setModelsLoading(true);setError('');setNotice('');
 try{
  const result=await loadModelCatalog(installed=>{
   if(request!==catalogVersion.current)return;
   setModels(installed);setModelsLoading(false);
   if(selection===selectionVersion.current)setModel(installed.some(m=>m.name===model)?model:installed[0]?.name??'');
  });
  if(request!==catalogVersion.current)return;
  if(result.value)applicationDefaults.current=result.value.configuration;
  if(result.warning)setNotice(result.warning);
  if(selection===selectionVersion.current){
   const selected=result.models.some(m=>m.name===model)?model:result.models.some(m=>m.name===result.value?.default_model)?result.value!.default_model:result.models[0]?.name??'';
   await chooseModel(selected);
  }
 }catch(e){if(request===catalogVersion.current)setError(String(e))}
 finally{if(request===catalogVersion.current)setModelsLoading(false)}
}
useEffect(()=>{void loadModels();if(!playground)void list().catch(e=>setError(String(e)));return()=>{catalogVersion.current++;selectionVersion.current++;controller.current?.abort()}},[playground]);
useEffect(()=>{const list=messageList.current;if(list&&followOutput.current)list.scrollTop=list.scrollHeight},[messages,mobilePanel]);
async function open(c:Conversation,clearError=true){selectionVersion.current++;try{const full=await api<Conversation>(`/conversations/${c.id}`);setCurrent(full);setModel(full.model);setConfig(full.configuration);followOutput.current=true;setMobilePanel('chat');setMessages(full.messages??[]);if(clearError)setError('')}catch(e){setError(String(e))}}
async function send(content=input,regenerate=false,edit?:number){if(busy||!model)return;selectionVersion.current++;followOutput.current=true;setBusy(true);setError('');const abort=new AbortController();controller.current=abort;let conversation=current;try{if(!playground&&!conversation){conversation=await api<Conversation>('/conversations',{method:'POST',body:JSON.stringify({title:content.slice(0,80)||'New conversation',model,configuration:config})});setCurrent(conversation);await list()}
let history=messages;if(edit!==undefined){const index=messages.findIndex(m=>m.id===edit);history=messages.slice(0,index)}else if(regenerate&&history.at(-1)?.role==='assistant')history=history.slice(0,-1);
setMessages([...history,...(!regenerate?[{role:'user' as const,content}]:[]),{role:'assistant',content:''}]);setInput('');
await stream('/chat',{model,content:playground&&regenerate?(history.at(-1)?.content??''):content,configuration:config,conversation_id:conversation?.id??null,regenerate:playground?false:regenerate,edit_message_id:edit??null,history:playground?(regenerate?history.slice(0,-1):history).map(({role,content})=>({role,content})):[]},abort.signal,event=>{if(event.type==='error')throw Error(String(event.detail));if(event.type==='token')setMessages(old=>old.map((m,i)=>i===old.length-1?{...m,content:m.content+String(event.content)}:m));if(event.type==='done')setMessages(old=>old.map((m,i)=>i===old.length-1?{...m,statistics:event.statistics as Record<string,unknown>}:m))});
}catch(e){if(!(e instanceof DOMException&&e.name==='AbortError'))setError(String(e))}finally{controller.current=null;if(conversation)await open(conversation,false);setBusy(false)}}
async function chooseModel(name:string){
 const selection=++selectionVersion.current;
 setModel(name);setConfig(structuredClone(applicationDefaults.current));
 if(!name)return;
 try{const saved=await api<Configuration|null>(`/model-preferences?model=${encodeURIComponent(name)}`);if(selection===selectionVersion.current&&saved)setConfig(saved)}
 catch(e){if(selection===selectionVersion.current)setNotice(`Model selected. Saved model settings could not be loaded: ${String(e)}`)}
}
async function saveDefaults(){try{await api(`/model-preferences?model=${encodeURIComponent(model)}`,{method:'PUT',body:JSON.stringify(config)});setNotice('Model defaults saved.')}catch(e){setError(String(e))}}
async function snapshot(){try{await api('/conversation-snapshots',{method:'POST',body:JSON.stringify({title:messages.find(m=>m.role==='user')?.content.slice(0,80)||'Playground session',model,configuration:config,messages:messages.map(({role,content})=>({role,content}))})});setNotice('Session saved. Open Chat to continue.')}catch(e){setError(String(e))}}
async function rename(){if(!current)return;const title=window.prompt('Conversation title',current.title);if(!title?.trim())return;try{const c=await api<Conversation>(`/conversations/${current.id}`,{method:'PUT',body:JSON.stringify({title,model,configuration:config})});setCurrent(c);await list()}catch(e){setError(String(e))}}
async function remove(){if(!current||!window.confirm('Delete this conversation and all messages?'))return;try{await api(`/conversations/${current.id}`,{method:'DELETE'});setCurrent(null);setMessages([]);await list()}catch(e){setError(String(e))}}
return <div className="relative flex min-h-0 flex-1 overflow-hidden">
  {!playground&&<aside className={`min-h-0 w-full shrink-0 flex-col border-r border-zinc-800/70 bg-[#101216] p-3 lg:w-56 ${settingsOpen?'hidden xl:flex':mobilePanel==='conversations'?'flex lg:flex':'hidden lg:flex'}`}>
    <button disabled={busy} onClick={()=>{setCurrent(null);setMessages([]);setError('');setNotice('');setMobilePanel('chat');void loadModels()}} className="mb-5 flex items-center gap-3 rounded-xl px-3 py-3 text-sm text-zinc-200 transition hover:bg-zinc-800"><SquarePen size={17}/>New chat</button>
    <div className="relative mb-6"><Search size={14} className="absolute left-3 top-3 text-zinc-500"/><input aria-label="Search conversations" placeholder="Search chats" value={search} onChange={e=>setSearch(e.target.value)} className="w-full rounded-xl bg-zinc-900 py-2.5 pl-9 pr-3 text-xs outline-none focus:ring-1 focus:ring-zinc-600"/></div>
    <p className="mb-3 px-3 text-[11px] font-medium text-zinc-500">Your chats</p>
    <div className="min-h-0 flex-1 space-y-1 overflow-y-auto overscroll-contain">{conversations.filter(c=>c.title.toLowerCase().includes(search.toLowerCase())).map(c=><button key={c.id} disabled={busy} onClick={()=>void open(c)} className={`block w-full truncate rounded-xl px-3 py-2.5 text-left text-sm transition ${current?.id===c.id?'bg-zinc-800 text-zinc-100':'text-zinc-400 hover:bg-zinc-800/60'}`}>{c.title}</button>)}{!conversations.length&&<p className="px-3 text-xs leading-5 text-zinc-600">Your conversations will appear here.</p>}</div>
    <button onClick={()=>setMobilePanel('chat')} className="mt-4 rounded-lg p-2 text-xs text-zinc-400 lg:hidden">Back to chat</button>
  </aside>}
  <section className={`min-h-0 min-w-0 flex-1 flex-col ${settingsOpen?'hidden xl:flex':mobilePanel==='chat'||playground?'flex lg:flex':'hidden lg:flex'}`}>
    <div className="flex min-h-16 shrink-0 items-center justify-between gap-3 px-4 md:px-6">
      <div className="flex min-w-0 items-center gap-2">{!playground&&<button aria-label="Show conversations" onClick={()=>setMobilePanel('conversations')} className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 lg:hidden"><PanelLeft size={19}/></button>}<select aria-label="Model" disabled={busy} value={model} onChange={e=>void chooseModel(e.target.value)} className="min-w-0 max-w-[240px] rounded-lg bg-transparent px-2 py-2 text-base font-medium text-zinc-200 outline-none hover:bg-zinc-800/60 focus-visible:ring-1 focus-visible:ring-zinc-500"><option value="">Select a model</option>{models.map(m=><option key={m.name} value={m.name} className="bg-zinc-900">{m.name}</option>)}</select><button type="button" aria-label="Refresh installed models" title={`${models.length} installed models · Refresh list`} disabled={busy||modelsLoading} onClick={()=>void loadModels()} className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-800 disabled:opacity-40"><RefreshCw size={14} className={modelsLoading?'animate-spin':''}/></button><span title="Inference runs on your workstation" className="hidden rounded-md border border-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-500 sm:inline">Local</span></div>
      <div className="flex items-center gap-1">{current&&<><button aria-label="Rename conversation" title="Rename conversation" disabled={busy} onClick={()=>void rename()} className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200"><Pencil size={15}/></button><button aria-label="Delete conversation" title="Delete conversation" disabled={busy} onClick={()=>void remove()} className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-800 hover:text-red-300"><Trash2 size={15}/></button></>}{playground&&<button disabled={busy||!messages.length} onClick={()=>void snapshot()} className="rounded-lg px-3 py-2 text-xs text-zinc-400 hover:bg-zinc-800">Save chat</button>}<button ref={settingsToggle} aria-label={settingsOpen?"Close inference settings":"Open inference settings"} aria-expanded={settingsOpen} aria-controls="inference-settings-panel" title="Inference settings" onClick={()=>setSettingsOpen(open=>!open)} className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"><SlidersHorizontal size={18}/></button></div>
    </div>
    <div ref={messageList} role="log" aria-label="Conversation messages" onScroll={e=>{const list=e.currentTarget;followOutput.current=list.scrollHeight-list.scrollTop-list.clientHeight<80}} className="min-h-0 flex-1 overflow-y-auto overscroll-contain [overflow-wrap:anywhere]">
      <div className={`mx-auto flex min-h-full w-full max-w-3xl flex-col px-5 pb-10 pt-6 md:px-8 ${messages.length?'gap-8':'justify-center'}`}>
        {!messages.length&&<div className="pb-12 text-center"><div className="mx-auto mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-zinc-800/50 text-emerald-300"><Sparkles size={25}/></div><h1 className="text-3xl font-medium tracking-tight text-zinc-100 md:text-4xl">What can I help with?</h1><p className="mt-4 text-sm text-zinc-500">A conversation with your model. Entirely on your machine.</p></div>}
        {messages.map((m,i)=><article key={m.id??`live-${i}`} className={`min-w-0 ${m.role==='user'?'flex flex-col items-end':''}`}>
          <div className={m.role==='user'?'max-w-[85%] rounded-3xl rounded-tr-lg bg-[#292b30] px-5 py-3 text-zinc-100':'w-full text-[15px] text-zinc-200'}><Markdown text={m.content}/></div>
          {busy&&m.role==='assistant'&&i===messages.length-1&&!m.content&&<div role="status" className="flex items-center gap-3 py-2 text-sm text-zinc-500"><span className="h-2 w-2 animate-pulse rounded-full bg-zinc-300"/>Thinking…</div>}
          {(m.content||!busy)&&<div className={`mt-2 flex flex-wrap items-center gap-1 text-zinc-500 ${m.role==='user'?'justify-end':''}`}>
            <button aria-label={copied===i?'Copied':'Copy message'} title={copied===i?'Copied':'Copy'} onClick={async()=>{try{await navigator.clipboard.writeText(m.content);setCopied(i)}catch{setError('Clipboard access unavailable')}}} className="rounded-lg p-2 hover:bg-zinc-800 hover:text-zinc-200">{copied===i?<Check size={14}/>:<Copy size={14}/>}</button>
            {m.role==='user'&&m.id&&!busy&&<button aria-label="Edit and resend" title="Edit and resend" onClick={()=>{const text=window.prompt('Edit and resend (later messages will be removed)',m.content);if(text?.trim())void send(text,false,m.id)}} className="rounded-lg p-2 hover:bg-zinc-800 hover:text-zinc-200"><Pencil size={14}/></button>}
            {m.role==='assistant'&&i===messages.length-1&&!busy&&<button aria-label="Regenerate response" title="Regenerate" onClick={()=>void send('',true)} className="rounded-lg p-2 hover:bg-zinc-800 hover:text-zinc-200"><RotateCcw size={14}/></button>}
            {m.role==='assistant'&&m.statistics&&<details className="ml-1 text-[11px]"><summary className="cursor-pointer rounded px-2 py-1 hover:text-zinc-300">Response details</summary><div className="mt-2 flex flex-wrap gap-3 rounded-xl border border-zinc-800 p-3">{m.statistics.eval_count!==undefined&&<span>{String(m.statistics.eval_count)} tokens · provider measurement</span>}{typeof m.statistics.eval_count==='number'&&typeof m.statistics.eval_duration==='number'&&m.statistics.eval_duration>0&&<span>{(m.statistics.eval_count/(m.statistics.eval_duration/1e9)).toFixed(1)} tok/s</span>}{typeof m.statistics.server_ttft_seconds==='number'&&<span>TTFT {m.statistics.server_ttft_seconds.toFixed(2)}s · server clock</span>}</div></details>}
            {m.statistics?.status&&m.statistics.status!=='completed'?<span className="px-2 text-xs text-amber-300">{String(m.statistics.status)}</span>:null}
          </div>}
        </article>)}
      </div>
    </div>
    <div className="shrink-0 px-4 pb-3 pt-2 md:px-8 md:pb-5"><div className="mx-auto w-full max-w-3xl">
      {notice&&<p aria-live="polite" className="mb-3 max-h-20 overflow-y-auto text-xs text-emerald-300">{notice}</p>}{error&&<p role="alert" className="mb-3 max-h-24 overflow-y-auto rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-sm text-amber-300">{error}</p>}
      {!model&&<div className="mb-3 flex items-center justify-between gap-3 text-xs text-amber-300"><p>{modelsLoading?'Loading installed models…':'Select an installed model to start chatting. Download one from Models if the list is empty.'}</p><button type="button" disabled={modelsLoading||busy} onClick={()=>void loadModels()}>Retry</button></div>}
      <form className="rounded-[28px] border border-zinc-700/60 bg-[#222429] p-3 shadow-lg transition focus-within:border-zinc-500" onSubmit={e=>{e.preventDefault();if(input.trim())void send()}}>
        <textarea ref={composer} aria-label="Message" placeholder="Ask anything" rows={1} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();if(!busy&&model&&input.trim())void send()}}} value={input} disabled={busy} onChange={e=>setInput(e.target.value)} className="block max-h-40 min-h-12 w-full resize-none overflow-y-auto bg-transparent px-3 py-3 text-[15px] text-zinc-100 outline-none placeholder:text-zinc-500"/>
        <div className="flex items-center justify-between gap-3 px-1"><button type="button" aria-expanded={settingsOpen} aria-controls="inference-settings-panel" onClick={()=>setSettingsOpen(open=>!open)} className="flex items-center gap-2 rounded-full px-3 py-2 text-xs text-zinc-400 hover:bg-zinc-700/40 hover:text-zinc-200"><SlidersHorizontal size={14}/>Settings</button>{busy?<button aria-label="Stop generation" title="Stop generation" type="button" onClick={()=>controller.current?.abort()} className="flex h-9 w-9 items-center justify-center rounded-full bg-zinc-100 text-zinc-900 hover:bg-white"><Square size={14} fill="currentColor"/></button>:<button aria-label="Send message" title="Send message" disabled={!model||!input.trim()} type="submit" className="flex h-9 w-9 items-center justify-center rounded-full bg-zinc-100 text-zinc-900 hover:bg-white disabled:bg-zinc-600 disabled:text-zinc-400"><ArrowUp size={20}/></button>}</div>
      </form>
      <p className="mt-3 text-center text-[10px] text-zinc-600">{playground?'Temporary chat · Save this conversation to keep it.':'Models can make mistakes. Your conversations stay on this device.'}</p>
    </div></div>
  </section>
  <aside id="inference-settings-panel" aria-labelledby="inference-panel-title" onKeyDown={e=>{if(e.key==='Escape'){setSettingsOpen(false);requestAnimationFrame(()=>settingsToggle.current?.focus())}}} className={`min-h-0 w-full shrink-0 flex-col border-l border-zinc-800/70 bg-[#101216] xl:w-80 ${settingsOpen?'flex':'hidden'}`}>
    <div className="flex h-16 shrink-0 items-center justify-between border-b border-zinc-800/70 px-5"><h2 id="inference-panel-title" className="text-sm font-medium">Model configuration</h2><button aria-label="Close settings" onClick={()=>{setSettingsOpen(false);requestAnimationFrame(()=>settingsToggle.current?.focus())}} className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800"><X size={18}/></button></div>
    <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4"><InferenceSettings value={config} onChange={setConfig} disabled={busy}/><Button disabled={busy||!model} className="mt-4 w-full" variant="outline" onClick={()=>void saveDefaults()}>Save defaults for this model</Button></div>
  </aside>
</div>
}
