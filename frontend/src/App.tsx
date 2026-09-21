import {useEffect,useRef,useState,type FormEvent,type ReactNode} from 'react';
import {Activity,ArrowRight,ArrowUpRight,BookOpen,Check,ChevronRight,Compass,FileText,Layers,LoaderCircle,MessageSquare,Plus,RefreshCw,Search,ShieldCheck,Sparkles,TriangleAlert,User} from 'lucide-react';
import {api} from './api';
import {HealthDashboard,ApiHealthDetails,ProductMetricReadings} from './HealthDashboard';
import {healthView,investigationPayload,labels as healthLabels} from './healthView';
import {InvestigationAnalysis} from './InvestigationAnalysis';
import {KnowledgeDashboard} from './KnowledgeDashboard';
import {Badge,Drawer,Empty,EvidenceCard,EvidenceList,Metric,Raw,Stepper,Timeline,docName,short,when,Quote,MarkdownText} from './components';
import type {Bootstrap,Draft,Evidence,Gap,Health,Issue,Job,JobPayload,Knowledge,Page,Pattern,Run} from './types';
const nav=[{id:'health',label:'Product Health',icon:Activity},{id:'investigations',label:'Investigations',icon:Search},{id:'knowledge',label:'Knowledge Health',icon:BookOpen}] as const;
// 'opportunities' page/content stays implemented below (see counts, titles, page==='opportunities' block) but is
// deliberately left out of nav — removed from the demo for now, not deleted; re-add the entry above to bring it back.
const severityTone={High:'critical',Medium:'warning',Low:'neutral'} as const;
const severityOrder={High:0,Medium:1,Low:2} as const;
const classificationTone:Record<string,'neutral'|'warning'|'good'|'critical'>={'Technical / Service Issue':'critical','Customer Experience Issue':'warning','Knowledge / Documentation Issue':'warning','Expected Product Behavior':'good','Insufficient Evidence':'neutral'};
function issueEvidence(refs:string[],evidence:Record<string,Evidence>){
 const records=refs.map(r=>evidence[r]).filter(Boolean);
 return {complaints:records.filter(r=>r.signal_type==='complaint'),incidents:records.filter(r=>r.signal_type==='incident'),
  productMetric:records.find(r=>r.signal_type==='product_metric'),apiMetric:records.find(r=>r.signal_type==='api_metric')};
}
function primaryIssue(p:Health['report']['products'][number]){return [...p.issues].sort((a,b)=>severityOrder[a.severity as keyof typeof severityOrder]-severityOrder[b.severity as keyof typeof severityOrder])[0]}
function sourceLinkLabel(r:Evidence){
 if(r.text){const name=(r.metadata?.source||r.source||'').split('/').pop();
  if(name==='product_source_of_truth.md')return 'Open Source of Truth';
  if(name==='api_documentation.md')return 'Open API documentation';
  if(name==='agent_procedures.md')return 'Open agent procedure';
  if(name==='product_faq.md')return 'Open FAQ';
  return 'Open source'}
 if(r.signal_type==='complaint')return 'Open complaint record';
 if(r.signal_type==='incident')return 'Open incident record';
 if(r.signal_type==='api_metric')return 'Open API dashboard';
 if(r.signal_type==='product_metric')return 'Open product dashboard';
 if(r.session_id)return 'Open customer session';
 return 'Open source';
}
function stripMarkdown(text:string){return text.split('\n').map(l=>l.replace(/^#{1,6}\s*/,'')).join('\n')}
function truthLabel(gap:Gap){return `Product Source of Truth · ${gap.product} · ${gap.title}`}
function escapeHtml(s:string){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function wordDocHtml(gap:Gap,wording:string){
 const body=`<h1>Documentation Update Request</h1><p><b>Product:</b> ${escapeHtml(gap.product)}</p><p><b>Document:</b> ${escapeHtml(docName(gap.file))}</p>`
  +`<h2>Approved wording</h2><p>${escapeHtml(wording).split('\n').filter(Boolean).join('</p><p>')}</p>`
  +`<h2>Why this update is needed</h2><p>${escapeHtml(gap.why)}</p>`
  +`<h2>Source of truth</h2><p>${escapeHtml(truthLabel(gap))}</p><p style="color:#888;font-size:9pt">Reference: ${escapeHtml(gap.truth_ref)}</p>`
 return `<html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'><head><meta charset='utf-8'><title>Documentation Update Request</title></head><body style="font-family:Calibri,Arial,sans-serif;font-size:11pt">${body}</body></html>`
}
const titles={health:['Product Health','See what needs attention across your products.'],investigations:['Follow the evidence','Investigate a customer complaint or an issue from product health.'],knowledge:['Keep your product knowledge aligned','Find and resolve gaps across your Product Source of Truth, API docs, agent procedures, and FAQs.'],opportunities:['See the patterns worth exploring','Turn repeated customer friction into questions worth pursuing.']};
type Detail={type:'issue';product:string;issue?:Issue}|{type:'run';run:Run}|{type:'gap';gap:Gap}|{type:'pattern';pattern:Pattern}|{type:'new'};
export default function App(){
 const [page,setPage]=useState<Page>(()=>(nav.some(n=>n.id===location.hash.slice(1))?location.hash.slice(1):'health') as Page);
 const [data,setData]=useState<Bootstrap|null>(null),[product,setProduct]=useState('All products'),[start,setStart]=useState(''),[end,setEnd]=useState(''),[activePreset,setActivePreset]=useState('');
 const [detail,setDetail]=useState<Detail|null>(null),[source,setSource]=useState<Evidence|null>(null),[sourceText,setSourceText]=useState('');
 const [busy,setBusy]=useState<{id:string;payload:JobPayload;originPage:Page;step?:string|null}|null>(null),[error,setError]=useState(''),[lastRequest,setLastRequest]=useState<JobPayload|null>(null);
 const [notice,setNotice]=useState(''),[notes,setNotes]=useState(''),[wording,setWording]=useState(''),[approved,setApproved]=useState(''),[tab,setTab]=useState('Key evidence'),[rewordFeedback,setRewordFeedback]=useState('');
 const [dismissing,setDismissing]=useState(false),[dismissReason,setDismissReason]=useState('');
 const initial=useRef(true);const timer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined);const boot=()=>api<Bootstrap>('/bootstrap').then(d=>{setData(d);if(initial.current){setStart(d.start);setEnd(d.end);initial.current=false}return d});
 useEffect(()=>{boot().catch(e=>setError(e.message));return()=>clearTimeout(timer.current)},[]);
 useEffect(()=>{const changed=()=>{const next=location.hash.slice(1);if(nav.some(n=>n.id===next)){setPage(next as Page);setDetail(null);setSource(null)}};window.addEventListener('hashchange',changed);return()=>window.removeEventListener('hashchange',changed)},[]);
 const go=(p:Page)=>{setPage(p);location.hash=p;setDetail(null);setSource(null);setError('');setNotice('')};
 const scoped=product==='All products'?data?.products||[]:[product];
 const scan=data?.health;
 const knowledge=data?.knowledge;const knowledgeMatches=knowledge&&scoped.every(p=>knowledge.scope.products.includes(p));
 const gaps=knowledgeMatches?knowledge!.gaps.filter(g=>scoped.includes(g.product)):[];
 const selectedGap=detail?.type==='gap'?detail.gap:null;const draft=selectedGap?data?.drafts[selectedGap.id]:undefined;const gapReview=selectedGap?data?.reviews[selectedGap.id]:undefined;
 const selectedIssue=detail?.type==='issue'?detail.issue:undefined;const findingReview=selectedIssue?data?.health_reviews[selectedIssue.id]:undefined;
 const show=(d:Detail)=>{setNotice('');setDetail(d);setNotes(d.type==='run'?d.run.notes:'');setTab('Key evidence');setRewordFeedback('');setDismissing(false);setDismissReason('');if(d.type==='gap'){const approvedWording=data?.approved[d.gap.id]||'';setWording(approvedWording||stripMarkdown(data?.drafts[d.gap.id]?.proposed_wording||''));setApproved(approvedWording)}else setApproved('')};
 const viewSource=(r:Evidence)=>{setSource(r);setSourceText('');const name=(r.metadata?.source||r.source||'').split('/').pop();if(name?.endsWith('.md'))api<{text:string}>('/documents/'+encodeURIComponent(name)).then(d=>setSourceText(d.text)).catch(()=>setSourceText('Source document unavailable.'))};
 async function launch(payload:JobPayload){
  if(busy)return;setError('');setNotice('');setLastRequest(payload);setBusy({id:'starting',payload,originPage:page});
  try{const {id}=await api<{id:string}>('/jobs',payload);setBusy({id,payload,originPage:page});
   const poll=async()=>{try{const job=await api<Job>('/jobs/'+id);if(job.status==='running'){setBusy(b=>b?{...b,step:job.step}:b);timer.current=setTimeout(poll,1200);return}setBusy(null);if(job.status==='failed'){setError(job.error||'The review could not complete.');return}
    const result=job.result as Health|Knowledge|Run|Draft;
    const openDespiteFailure=payload.kind==='investigation'&&'status' in result&&result.status==='unavailable'  // service/tool failure — evidence gathered so far is preserved and worth showing, unlike a normal incomplete/validation failure
    if('status' in result&&result.status!=='completed'&&!openDespiteFailure){setError(result.error||'Evidence could not be verified. No finding has been approved.');return}
    const d=await boot();
    if(payload.kind==='health')setDetail(null);
    if(payload.kind==='investigation'){setPage('investigations');history.replaceState(null,'','#investigations');show({type:'run',run:result as Run})}
    if(payload.kind==='draft'){const next=stripMarkdown((result as Draft).proposed_wording);setWording(next);setApproved('');setRewordFeedback('');setNotice(payload.feedback?(next.trim()===payload.wording?.trim()?'The rewrite returned the same wording. Try more specific instructions.':'Wording updated. Review the revised draft before approving.'):'Draft ready for review.');setTimeout(()=>document.getElementById('draft-editor')?.scrollIntoView({behavior:'smooth'}),100)}
    if(payload.kind==='knowledge'){setDetail(null);setNotice(`Comparison complete. ${d.knowledge?.gaps.length||0} potential ${(d.knowledge?.gaps.length||0)===1?'gap is':'gaps are'} ready to review.`)}
   }catch(e){setBusy(null);setError((e as Error).message)}};await poll();
  }catch(e){setBusy(null);setError((e as Error).message)}
 }
 async function reviewRun(decision:string){if(detail?.type!=='run')return;try{const run=await api<Run>(`/investigations/${detail.run.id}/review`,{decision,notes});setDetail({type:'run',run});await boot();setNotice('Review saved. No customer or product changes were made.')}catch(e){setError((e as Error).message)}}
 async function reviewFinding(decision:string,reason=''){if(!selectedIssue)return;try{await api(`/health-findings/${selectedIssue.id}/review`,{decision,reason});setDismissing(false);setDismissReason('');await boot();setNotice(decision==='monitoring'?'Added to monitoring.':'Finding dismissed. No investigation was started.')}catch(e){setError((e as Error).message)}}
 async function reviewGap(decision:string){if(!selectedGap)return;try{await api(`/gaps/${selectedGap.id}/review`,{decision});setApproved('');if(decision==='Not a gap'){setDetail(null);setWording('')}await boot()}catch(e){setError((e as Error).message)}}
 async function approveUpdate(download=false){if(!selectedGap)return;try{await api<{preview:string}>(`/gaps/${selectedGap.id}/${download?'export':'approve'}`,{wording});if(download){const url=URL.createObjectURL(new Blob([wordDocHtml(selectedGap,wording)],{type:'application/msword'}));const a=document.createElement('a');a.href=url;a.download='documentation-update-request.doc';a.click();URL.revokeObjectURL(url)}else {setNotice('');setApproved(wording);setData(d=>d?{...d,approved:{...d.approved,[selectedGap.id]:wording}}:d)}}catch(e){setError((e as Error).message)}}
 const patternId=(p:Pattern)=>p.product+'-'+p.pattern;
 const counts:Record<Page,number>={health:data?.health?data.health.report.products.flatMap(p=>p.issues).filter(i=>!data.health_reviews[i.id]).length:0,investigations:data?.runs.filter(r=>r.review==='Pending review').length||0,knowledge:data?.knowledge?data.knowledge.gaps.filter(g=>!data.reviews[g.id]).length:0,opportunities:data?data.opportunities.filter(p=>!data.explored[patternId(p)]).length:0};
 const presetStart=(days:number)=>{const d=new Date(data!.end);d.setDate(d.getDate()-(days-1));const iso=d.toISOString().slice(0,10);return iso<data!.start?data!.start:iso};
 const datePresets=[{label:'Last 7 days',start:()=>presetStart(7)},{label:'Last 30 days',start:()=>presetStart(30)},{label:'All time',start:()=>data!.start}];
 const totalDays=data?Math.round((new Date(data.end).getTime()-new Date(data.start).getTime())/86400000)+1:0;
 const banners=<>{error&&<div role="alert" className="mb-5 flex flex-wrap items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><TriangleAlert size={19} className="shrink-0"/><div className="flex-1"><p className="font-semibold">We couldn’t complete that action</p><p className="mt-1 leading-6">{error}</p></div><button className="secondary" disabled={!!busy} onClick={()=>lastRequest?launch(lastRequest):boot().then(()=>setError('')).catch(e=>setError(e.message))}><RefreshCw size={14}/>Retry</button></div>}{busy&&busy.originPage===page&&<div role="status" className="mb-5 flex items-center gap-3 rounded-xl border border-pulse-100 bg-pulse-50 p-4 text-sm text-pulse-700"><LoaderCircle className="animate-spin" size={18}/><div><p className="font-semibold">{busy.payload.kind==='health'?'Reviewing product health':busy.payload.kind==='knowledge'?'Comparing product guidance':busy.payload.kind==='draft'?(busy.payload.feedback?'Rewriting your update':'Drafting your update'):'Investigating the evidence'}…</p><p className="mt-1 text-xs">{busy.step?busy.step+'…':'You can browse other pages while this finishes.'}</p></div></div>}{notice&&<div role="status" className="mb-5 flex gap-2 text-sm text-pulse-700"><Check size={16}/>{notice}</div>}</>;
 return <div className="min-h-screen lg:flex"><a className="pulse-skip" href="#main-content">Skip to content</a><aside className="pulse-sidebar border-b border-slate-200 px-5 py-5 lg:fixed lg:inset-y-0 lg:w-60 lg:border-r lg:py-8"><a href="#health" onClick={()=>go('health')} className="pulse-brand flex items-center gap-3 font-semibold tracking-tight"><span className="rounded-xl bg-slate-900 p-2 text-white"><Layers size={22}/></span>Product Pulse</a><p className="eyebrow mt-9 hidden lg:block">Your workspace</p><nav aria-label="Main navigation" className="mt-3 flex gap-1 overflow-x-auto lg:flex-col">{nav.map(({id,label,icon:Icon})=><button key={id} aria-current={page===id?'page':undefined} onClick={()=>go(id)} className={'flex shrink-0 items-center justify-between gap-3 rounded-xl px-3 py-3 text-sm font-medium '+(page===id?'bg-white text-slate-900':'text-slate-500 hover:bg-slate-50')}><span className="flex items-center gap-3"><Icon size={18}/>{label}</span>{!!counts[id]&&<span className="rounded-full bg-pulse-600 px-1.5 py-0.5 text-[10px] font-bold text-white">{counts[id]}</span>}</button>)}</nav><div className="mt-8 hidden rounded-2xl border border-slate-200 bg-white p-4 lg:absolute lg:bottom-8 lg:left-5 lg:right-5 lg:block"><ShieldCheck size={20} className="mb-3 text-slate-900"/><p className="text-sm font-semibold text-slate-900">AI investigates.<br/>PM decides.</p><p className="mt-2 text-xs leading-5 text-slate-500">Your judgment comes first.<br/>Nothing is published automatically.</p></div></aside>
 <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 lg:ml-60"><header className="pulse-topbar flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/70 px-6 py-4 lg:px-10"><div className="flex items-center gap-2 text-sm text-slate-400">Workspace<ChevronRight size={14}/><span className="text-slate-700">{nav.find(n=>n.id===page)?.label}</span></div><div className="flex items-center gap-3"><span className="hidden text-xs text-slate-400 sm:block">Synthetic demo data</span>{page!=='health'&&page!=='knowledge'&&<><label className="sr-only" htmlFor="global-product">Product</label><select id="global-product" value={product} onChange={e=>{setProduct(e.target.value);setDetail(null)}}><option>All products</option>{data?.products.map(p=><option key={p}>{p}</option>)}</select></>}</div></header>
 <div className={page==='health'||page==='knowledge'?'health-workspace mx-auto px-5 py-6 sm:px-6':'mx-auto max-w-6xl px-5 py-8 sm:px-8 lg:px-10'}><div className="pulse-heading mb-7 flex flex-wrap items-start justify-between gap-5"><div><p className="eyebrow mb-2">{nav.find(n=>n.id===page)?.label}</p><h1 className="page-title">{titles[page][0]}</h1><p className="muted mt-2">{titles[page][1]}</p></div>{page==='health'&&<button className="primary" disabled={!!busy||!data} onClick={()=>launch({kind:'health',products:data?.products||[],start,end})}><Sparkles size={16}/>Run Health Scan</button>}{page==='knowledge'&&<div className="knowledge-check-action"><p className="text-xs text-slate-500">Last checked: {knowledge?.checked_at?when(knowledge.checked_at):knowledge?'Time unavailable':'Not yet checked'}</p><button className="primary" disabled={!!busy||!data} onClick={()=>launch({kind:'knowledge',products:scoped})}><Sparkles size={16}/>Check Knowledge Consistency</button></div>}{page==='investigations'&&<button className="primary" disabled={!!busy||!data} onClick={()=>show({type:'new'})}><Plus size={16}/>New investigation</button>}</div>{banners}
 {!data&&!error&&<Empty title="Opening your workspace"><LoaderCircle className="mx-auto animate-spin"/></Empty>}
 {data&&page==='health'&&<><div className="pulse-filters mb-6 flex flex-wrap items-center gap-3 text-sm"><span className="text-slate-500">Review period</span><input aria-label="Review start date" type="date" min={data.start} max={data.end} value={start} onChange={e=>{setStart(e.target.value);setActivePreset('')}}/><span className="text-slate-400">to</span><input aria-label="Review end date" type="date" min={start} max={data.end} value={end} onChange={e=>{setEnd(e.target.value);setActivePreset('')}}/><div className="flex gap-1.5">{datePresets.map(p=><button key={p.label} type="button" className={'rounded-lg border px-2.5 py-1 text-xs font-medium '+(activePreset===p.label?'border-pulse-600 bg-pulse-50 text-pulse-700':'border-slate-200 bg-white text-slate-600 hover:bg-slate-50')} onClick={()=>{setStart(p.start());setEnd(data.end);setActivePreset(p.label)}}>{p.label}</button>)}</div></div>
 {scan?<HealthDashboard scan={scan} data={data} onReview={p=>show({type:'issue',product:p.product_name,issue:primaryIssue(p)})} onKnowledge={()=>go('knowledge')} launch={launch} busy={!!busy}/>:<Empty title="Start with a health scan" icon={<Activity size={26}/>}><p>Get a clear picture of what needs attention across your products. Choose a review period above, then run your health scan.</p><div className="mt-5 flex flex-wrap justify-center gap-2"><Badge>Product performance</Badge><Badge>Customer feedback</Badge><Badge>API health</Badge></div></Empty>}
 </>}
 {data&&page==='investigations'&&<>{data.runs.filter(r=>scoped.includes(r.product)).length?<div className="space-y-3">{[...data.runs].reverse().filter(r=>scoped.includes(r.product)).map(run=><button key={run.id} className="card flex w-full items-center justify-between gap-4 text-left hover:border-pulse-600" onClick={()=>show({type:'run',run})}><div><Badge tone={run.status==='completed'?(classificationTone[run.classification]||'neutral'):'neutral'}>{run.status==='completed'?run.classification:'Incomplete review'}</Badge><h2 className="mt-3 text-base font-semibold">{short(run.complaint,120)}</h2><p className="muted mt-1">{run.product} · {run.customer||'Product issue'} · {run.day}</p></div><span className="hidden text-xs text-slate-500 sm:block">{run.review}</span><ChevronRight className="shrink-0 text-slate-400" size={20}/></button>)}</div>:<Empty title="Start with a customer question" icon={<MessageSquare size={25}/>}><p>Describe an issue, or investigate a signal from Product Health. Your findings and review history will appear here.</p><button className="link mt-4" onClick={()=>show({type:'new'})}>Start an investigation<ArrowRight size={14}/></button></Empty>}</>}
 {data&&page==='knowledge'&&<KnowledgeDashboard data={data} knowledge={knowledge||null} matches={!!knowledgeMatches} product={product} onProduct={value=>{setProduct(value);setDetail(null)}} error={error} onReview={gap=>show({type:'gap',gap})} onSource={viewSource}/>}
 {data&&page==='opportunities'&&<>{data.opportunities.filter(p=>scoped.includes(p.product)).length?<div className="space-y-4">{data.opportunities.filter(p=>scoped.includes(p.product)).map(p=><article key={patternId(p)} className="card"><Badge>Emerging pattern</Badge><h2 className="mt-3 text-lg font-semibold">{p.pattern.replaceAll('_',' ').toLowerCase()}</h2><p className="muted mt-1">{p.product} · {p.sessions.length} sessions across {p.runs.length} investigations</p><p className="my-4 text-sm text-slate-600">Repeated friction at the same step may be worth exploring.</p><button className="link" onClick={()=>{show({type:'pattern',pattern:p});setNotes(data.explored[patternId(p)]||'')}}>Explore opportunity<ArrowRight size={15}/></button></article>)}</div>:<Empty title="Patterns emerge as you investigate" icon={<Compass size={25}/>}><p>Related customer experiences will appear here after investigations uncover repeated responses. These are opportunities to explore—not roadmap decisions.</p><button className="link mt-4" onClick={()=>go('investigations')}>Go to investigations<ArrowRight size={14}/></button></Empty>}</>}
 {page!=='knowledge'&&<footer className="mt-12 border-t border-slate-200/70 pt-4 text-xs text-slate-400">AI-powered product intelligence for Product Managers · Reviews run only when requested.</footer>}</div></main>
 {detail&&!source&&<Drawer title={detail.type==='new'?'New investigation':detail.type==='gap'?'Review knowledge gap':detail.type==='pattern'?'Explore opportunity':'Review finding'} onClose={()=>setDetail(null)}>{banners}
 {detail.type==='new'&&<InvestigationForm products={data?.products||[]} selected={product} day={data?.start||''} busy={!!busy} onSubmit={launch}/>}
 {detail.type==='issue'&&scan&&<FindingReview data={data!} product={detail.product} issue={detail.issue} scan={scan} findingReview={findingReview} dismissing={dismissing} setDismissing={setDismissing} dismissReason={dismissReason} setDismissReason={setDismissReason} busy={!!busy} viewSource={viewSource} reviewFinding={reviewFinding} launch={launch}/>}
 {detail.type==='run'&&<RunReview run={detail.run} notes={notes} setNotes={setNotes} busy={!!busy} tab={tab} setTab={setTab} viewSource={viewSource} reviewRun={reviewRun} launch={launch} onReturnHome={()=>go('health')}/>}
 {selectedGap&&<GapReview gap={selectedGap} draft={draft} gapReview={gapReview} wording={wording} setWording={setWording} rewordFeedback={rewordFeedback} setRewordFeedback={setRewordFeedback} approved={approved} busy={!!busy} viewSource={viewSource} reviewGap={reviewGap} launch={launch} approveUpdate={approveUpdate}/>}
 {detail.type==='pattern'&&<><Badge>Potential opportunity</Badge><h2 className="text-2xl font-semibold">{detail.pattern.pattern.replaceAll('_',' ').toLowerCase()}</h2><p className="muted">{detail.pattern.product} · {detail.pattern.sessions.length} distinct sessions</p><EvidenceList records={Object.values(detail.pattern.evidence)} onView={viewSource}/><p className="text-sm leading-6">Explore whether clearer guidance or recovery support would help at this step. Repeated responses do not establish a root cause or overall prevalence.</p><label htmlFor="exploration" className="label">What would you like to learn?</label><textarea id="exploration" className="w-full" rows={4} value={notes} onChange={e=>setNotes(e.target.value)}/><button className="primary" onClick={async()=>{try{await api('/opportunities/explore',{pattern_id:patternId(detail.pattern),notes});await boot();setNotice('Exploration notes saved.')}catch(e){setError((e as Error).message)}}}>Save exploration notes</button></>}
 </Drawer>}
 {source&&<Drawer title="Supporting evidence" onClose={()=>setSource(null)}><p className="eyebrow">{source.text?docName(source.metadata?.source||source.source):source.signal_type||'Customer activity'}</p><h2 className="text-xl font-semibold">{source.metric_name||source.incident_id||source.action||source.product_name||'Product documentation'}</h2>{source.signal_type?.includes('metric')?<Metric r={source}/>:<MarkdownText text={source.text||source.complaint_text||source.details||source.result||''}/>}{source.session_id&&detail?.type==='run'&&<Timeline events={detail.run.events.filter(e=>e.session_id===source.session_id&&e.customer_id===source.customer_id)} onView={viewSource}/>}<p className="muted">{source.timestamp?when(source.timestamp):''}</p><p className="text-xs text-slate-400">{source.evidence_id||source._evidence?.evidence_id||`${source.metadata?.source||source.source||''} · lines ${source.metadata?.line_start||source.line_start||'—'}–${source.metadata?.line_end||source.line_end||'—'}`}</p>{sourceText&&<details className="muted"><summary>View complete source document</summary><div className="mt-4 rounded-xl border border-slate-200 bg-white p-5"><MarkdownText text={sourceText}/></div></details>}{detail?.type!=='gap'&&page!=='knowledge'&&<Raw data={source}/>}</Drawer>}
 </div>
}
const QUICK_ACTIONS=[{label:'Shorter',feedback:'Shorten this draft substantially. Remove repetition and unnecessary words while preserving every authoritative requirement.'},{label:'Customer-friendly',feedback:'Rewrite this draft for customers in plain, friendly language. Use direct sentences and replace jargon while preserving every authoritative requirement.'},{label:'More formal',feedback:'Rewrite this draft in a formal, professional documentation tone. Use precise language and no conversational phrasing while preserving every authoritative requirement.'}];
function GapReview({gap,draft,gapReview,wording,setWording,rewordFeedback,setRewordFeedback,approved,busy,viewSource,reviewGap,launch,approveUpdate}:{gap:Gap;draft?:Draft;gapReview?:string;wording:string;setWording:(v:string)=>void;rewordFeedback:string;setRewordFeedback:(v:string)=>void;approved:string;busy:boolean;viewSource:(r:Evidence)=>void;reviewGap:(d:string)=>void;launch:(p:JobPayload)=>void;approveUpdate:(download?:boolean)=>void}){
 const isApproved=!!approved&&approved===wording;
 const [editing,setEditing]=useState(!isApproved);
 const toolbar=useRef<HTMLDivElement>(null);
 useEffect(()=>{if(isApproved){setEditing(false);toolbar.current?.closest('[role="dialog"]')?.scrollTo({top:0});toolbar.current?.focus({preventScroll:true})}},[isApproved]);
 const status=isApproved?'Approved — ready for handoff':gapReview==='Not a gap'?'Rejected gap':gapReview==='Confirmed'?(draft?'Draft ready for your approval':'Gap confirmed — ready to draft'):'Potential gap — needs your review';
 return <>
  <div ref={toolbar} tabIndex={-1} className="gap-review-toolbar">
   <p role="status" className="font-semibold text-sm">{status}</p>
   <div className="flex flex-wrap gap-2">
    {gapReview!=='Confirmed'?<><button className="secondary" disabled={busy} onClick={()=>reviewGap('Not a gap')}>Reject Gap</button><button className="primary" disabled={busy} onClick={()=>reviewGap('Confirmed')}><Check size={16}/>Confirm Gap</button></>:!draft?<button className="primary" disabled={busy} onClick={()=>launch({kind:'draft',gap_id:gap.id})}><Sparkles size={16}/>Draft Update</button>:isApproved?<><button className="primary" disabled={busy} onClick={()=>approveUpdate(true)}>Download Word</button><button className="secondary" disabled={busy} onClick={()=>{setEditing(true);requestAnimationFrame(()=>document.getElementById('wording')?.focus())}}>Make changes</button></>:<button className="primary" disabled={!wording.trim()||busy} onClick={()=>approveUpdate()}>Approve wording</button>}
   </div>
  </div>
  <div><h2 className="text-xl font-semibold">{gap.title}</h2><p className="muted mt-1">{gap.product} · {docName(gap.file)}</p></div>
  {gapReview!=='Confirmed'?<>
   <div className="grid gap-4 sm:grid-cols-2"><section className="card border-pulse-100"><p className="eyebrow text-pulse-700">Source of Truth</p><div className="mt-3"><Quote text={gap.truth_evidence.text}/></div><button className="link mt-3 text-xs" onClick={()=>viewSource(gap.truth_evidence)}>View source<ArrowUpRight size={13}/></button></section><section className="card"><p className="eyebrow">{docName(gap.file)}</p><div className="mt-3"><Quote text={gap.current_evidence.text}/></div><button className="link mt-3 text-xs" onClick={()=>viewSource(gap.current_evidence)}>View source<ArrowUpRight size={13}/></button></section></div>
   <div><h3 className="font-semibold">Why it may be inconsistent</h3><p className="muted mt-2">{gap.why}</p></div>
  </>:!draft?<p className="muted">The gap is confirmed. Choose Draft Update above to prepare replacement wording for your approval.</p>:<div id="draft-editor" className="space-y-4">
   {isApproved&&!editing?<section className="card"><h3 className="eyebrow mb-3">Approved wording</h3><MarkdownText text={wording}/></section>:<div><label className="label" htmlFor="wording">Proposed replacement wording</label><textarea id="wording" className="w-full" rows={5} value={wording} onChange={e=>setWording(e.target.value)}/><div className="mt-2 flex flex-wrap gap-1.5">{QUICK_ACTIONS.map(q=><button key={q.label} className="secondary px-2.5 py-1 text-xs" disabled={busy} onClick={()=>launch({kind:'draft',gap_id:gap.id,wording,feedback:q.feedback})}>{q.label}</button>)}</div><div className="mt-2 flex flex-wrap items-start gap-2"><input className="min-w-0 flex-1" aria-label="Rewrite instructions" placeholder="Describe another change…" value={rewordFeedback} onChange={e=>setRewordFeedback(e.target.value)}/><button className="secondary shrink-0" disabled={busy||!rewordFeedback.trim()} onClick={()=>launch({kind:'draft',gap_id:gap.id,wording,feedback:rewordFeedback})}><Sparkles size={14}/>Rewrite with AI</button></div></div>}
   <p className="text-xs text-slate-500">{isApproved?'Approved for download. Nothing has been published automatically.':'Review the wording, then approve it using the action above. Editing approved wording requires approval again.'}</p>
   <details className="gap-supporting"><summary>Compare with current guidance</summary><p className="eyebrow mt-3 mb-2">Current {docName(gap.file)}</p><MarkdownText text={gap.current_evidence.text||''}/><button className="link mt-3 text-xs" onClick={()=>viewSource(gap.current_evidence)}>View source<ArrowUpRight size={13}/></button></details>
   <details className="gap-supporting"><summary>Why this update is needed</summary><p className="muted mt-3">{gap.why}</p><button className="link mt-3 text-xs" onClick={()=>viewSource(gap.truth_evidence)}>View Source of Truth<ArrowUpRight size={13}/></button></details>
  </div>}
 </>
}

function FindingReview({data,product,issue,scan,findingReview,dismissing,setDismissing,dismissReason,setDismissReason,busy,viewSource,reviewFinding,launch}:{data:Bootstrap;product:string;issue?:Issue;scan:Health;findingReview?:{decision:string;reason:string};dismissing:boolean;setDismissing:(v:boolean)=>void;dismissReason:string;setDismissReason:(v:string)=>void;busy:boolean;viewSource:(r:Evidence)=>void;reviewFinding:(d:string,reason?:string)=>void;launch:(p:JobPayload)=>void}){
 const p=scan.report.products.find(pr=>pr.product_name===product);
 const view=p?healthView(p,scan,data):null;
 const complaints=view?.complaints||[],incidents=view?.incidents||[],productMetric=view?.primary.latest;
 return <>
  {view&&<span className="health-status" data-tone={view.bucket}>{healthLabels[view.bucket]}</span>}
  <h2 className="text-2xl font-semibold">{product}</h2>
  <p className="muted">{scan.scope.start} – {scan.scope.end}</p>
  <p className="text-sm">{issue&&<strong>Finding on {issue.date}: </strong>}{short(issue?.finding||p?.summary||'',160)}</p>
  {view&&<div className="flex flex-wrap items-center gap-3"><button className="primary" disabled={busy} onClick={()=>launch(investigationPayload(view,scan))}>Investigate finding<ArrowRight size={16}/></button><p className="text-xs text-slate-500">Understand customer impact and contributing factors.</p></div>}
  {view&&<section className="card" aria-label="Product metric readings"><ProductMetricReadings view={view} onSource={viewSource}/></section>}
  {view&&<ApiHealthDetails view={view} onSource={viewSource}/>}
  <div>
   <p className="eyebrow mb-2">Signals behind this finding</p>
   <div className="space-y-3">


    {!!incidents.length&&<div className="rounded-xl border border-slate-200 p-4"><p className="eyebrow">Incidents</p><p className="mt-1 text-sm text-slate-600">{incidents.length} related incident{incidents.length===1?'':'s'}</p><div className="mt-2 space-y-1">{incidents.map((inc,i)=><button key={i} className="link block text-xs" onClick={()=>viewSource(inc)}>{inc.incident_id}{inc.severity?' · '+inc.severity:''} — {sourceLinkLabel(inc)}<ArrowUpRight size={12}/></button>)}</div></div>}
    {!!complaints.length&&<div className="rounded-xl border border-slate-200 p-4"><p className="eyebrow">Customer Feedback</p><p className="mt-1 text-sm text-slate-600">{complaints.length} related complaint{complaints.length===1?'':'s'}</p><div className="mt-2 space-y-2">{complaints.slice(0,2).map((c,i)=><p key={i} className="text-sm italic leading-6 text-slate-600">“{short(c.complaint_text||'',140)}”</p>)}</div>{complaints.length>2&&<p className="mt-1 text-xs text-slate-400">+{complaints.length-2} similar complaint{complaints.length-2===1?'':'s'}</p>}<details className="muted mt-2"><summary>View all {complaints.length} complaint records</summary><div className="mt-2"><EvidenceList records={complaints} onView={viewSource}/></div></details></div>}
    {!productMetric&&!incidents.length&&!complaints.length&&<p className="muted">No supporting evidence returned for this section.</p>}
   </div>
  </div>

  {issue&&<>
   <div><p className="eyebrow mb-2">Recommended Next Step</p><p className="text-sm leading-6 text-slate-700">{issue.recommendation}</p></div>
   {findingReview?<div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">{findingReview.decision==='monitoring'?'Added to monitoring.':'Dismissed.'}{!!findingReview.reason&&<span> — “{findingReview.reason}”</span>}</div>
   :<div>
     <div className="flex flex-wrap gap-2">

      <button className="secondary" disabled={busy} onClick={()=>reviewFinding('monitoring')}>Monitor</button>
      <button className="secondary" disabled={busy} onClick={()=>setDismissing(true)}>Dismiss</button>
     </div>
     {dismissing&&<div className="mt-3 space-y-2"><label className="label" htmlFor="dismiss-reason">Why are you dismissing this? <span className="text-slate-400">(optional)</span></label><textarea id="dismiss-reason" className="w-full" rows={2} value={dismissReason} onChange={e=>setDismissReason(e.target.value)}/><div className="flex gap-2"><button className="secondary" disabled={busy} onClick={()=>reviewFinding('dismissed',dismissReason)}>Confirm Dismiss</button><button className="link text-xs" onClick={()=>setDismissing(false)}>Cancel</button></div></div>}
     <p className="muted mt-2">Product Health detects. You decide whether it deserves investigation.</p>
    </div>}
  </>}

 </>
}
function RunReview({run,notes,setNotes,busy,viewSource,reviewRun,launch,onReturnHome}:{run:Run;notes:string;setNotes:(v:string)=>void;busy:boolean;tab:string;setTab:(t:string)=>void;viewSource:(r:Evidence)=>void;reviewRun:(d:string)=>void;launch:(p:JobPayload)=>void;onReturnHome:()=>void}){
 const unavailable=run.status==='unavailable';
 return <>
  {unavailable?<>
   <Badge tone={run.retryable?'warning':'neutral'}>{run.retryable?'Investigation paused':'Investigation unavailable'}</Badge>
   <h2 className="text-2xl font-semibold leading-snug">{run.retryable?'INVESTIGATION PAUSED':'INVESTIGATION UNAVAILABLE'}</h2>
   <p className="muted">{run.error||"Product Pulse couldn't complete the analysis."}</p>
   <p className="text-sm leading-6 text-slate-700">{run.retryable?'Your investigation and evidence have been preserved.':'The evidence gathered so far has been preserved.'}</p>
   <div className="flex flex-wrap gap-2">
    {run.retryable
     ?<button className="primary" disabled={busy} onClick={()=>launch({kind:'investigation',product:run.product,complaint:run.complaint,customer:run.customer,day:run.day!=='All available dates'?run.day:null,context:{...run.investigation_context,origin:'Retry after service failure'}})}><RefreshCw size={16}/>Retry Investigation</button>
     :<button className="primary" onClick={onReturnHome}>Return to Product Health</button>}
   </div>
  </>:<InvestigationAnalysis run={run} viewSource={viewSource}/>}
  {!unavailable&&!!run.recommendation.length&&<div><p className="eyebrow mb-2">Recommended next step</p><ul className="space-y-1.5">{run.recommendation.map((step,i)=><li key={i} className="flex gap-2 text-sm leading-6 text-slate-800"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400"/><span>{step}</span></li>)}</ul><p className="mt-2 text-xs italic text-slate-400">The agent recommends. The PM decides.</p></div>}
  {!unavailable&&<div><label className="label" htmlFor="review-notes">Add context or ask Product Pulse to investigate something else</label><textarea id="review-notes" className="w-full" placeholder="Check whether other customers experienced the same error…" value={notes} onChange={e=>setNotes(e.target.value)} rows={3}/></div>}
  {!unavailable&&<div><p className="eyebrow mb-3">Does this finding look right?</p><div className="flex flex-wrap gap-2"><button className="primary" disabled={busy||run.status!=='completed'} onClick={()=>reviewRun('Confirmed')}><Check size={16}/>Confirm Finding</button><button className="secondary" disabled={busy||run.status!=='completed'} onClick={()=>launch({kind:'investigation',prior_run_id:run.id,question:notes})}>Investigate Further</button><button className="secondary" disabled={busy||run.status!=='completed'} onClick={()=>reviewRun('Disagreed')}>Disagree</button></div><p className="muted mt-2">{run.review}. Your review does not change products or send a customer response.</p></div>}

  {unavailable&&<details className="muted"><summary>Technical details</summary><div className="mt-3 rounded-xl bg-slate-100 p-4 text-xs text-slate-600"><p>Category: {run.failure_category||'unknown'}</p><p className="mt-1">Retryable: {String(!!run.retryable)}</p><p className="mt-1 break-words">{run.technical_error}</p></div></details>}

 </>
}
function InvestigationForm({products,selected,day,busy,onSubmit}:{products:string[];selected:string;day:string;busy:boolean;onSubmit:(p:JobPayload)=>void}){
 const [product,setProduct]=useState(products.includes(selected)?selected:products.includes('Bank Account Management')?'Bank Account Management':products[0]);const [complaint,setComplaint]=useState(''),[customer,setCustomer]=useState(''),[date,setDate]=useState(day),[time,setTime]=useState('');
 function submit(e:FormEvent){e.preventDefault();onSubmit({kind:'investigation',product,complaint,customer,day:date||null,approximate_time:date&&time?time:null})}
 return <form onSubmit={submit} className="space-y-5"><h2 className="text-2xl font-semibold">What would you like to understand?</h2><p className="muted">Describe the customer complaint or product issue. Add a customer ID to reconstruct their journey.</p><div><label className="label" htmlFor="investigate-product">Product</label><select id="investigate-product" className="w-full" value={product} onChange={e=>setProduct(e.target.value)}>{products.map(p=><option key={p}>{p}</option>)}</select></div><div><label className="label" htmlFor="complaint">Complaint or issue</label><textarea id="complaint" className="w-full" rows={4} required placeholder="e.g. My bank verification failed and I couldn’t use my account for a payment." value={complaint} onChange={e=>setComplaint(e.target.value)}/></div><div><label className="label" htmlFor="customer">Customer ID <span className="text-slate-400">(optional)</span></label><input id="customer" className="w-full" placeholder="e.g. C1001" value={customer} onChange={e=>setCustomer(e.target.value)}/></div><div className="grid grid-cols-1 gap-4 sm:grid-cols-2"><div><label className="label" htmlFor="date">Approximate date</label><input id="date" className="w-full" type="date" value={date} onChange={e=>setDate(e.target.value)}/></div><div><label className="label" htmlFor="time">Time (optional)</label><input id="time" className="w-full" type="time" value={time} onChange={e=>setTime(e.target.value)}/></div></div><button className="primary w-full" disabled={busy||!complaint.trim()} type="submit"><Search size={16}/>Investigate</button><button type="button" className="link text-xs" onClick={()=>{setProduct('Bank Account Management');setCustomer('C1001');setDate('2026-09-03');setTime('09:17');setComplaint('I tried to add my bank account, but verification failed and I could not use it for payment.')}}>Use sample complaint · C1001</button></form>
}
