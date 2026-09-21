import type {Evidence,Finding,Run} from './types';
import {Badge} from './components';

const names:Record<string,string>={'Technical / Service Issue':'Technical Issue','Expected Product Behavior':'Expected Behavior','Knowledge / Documentation Issue':'Knowledge Issue'};
function sourceLabel(r:Evidence){
 if(r.session_id)return 'Open customer session';
 if(r.signal_type==='api_metric')return 'Open API dashboard';
 if(r.signal_type==='incident')return 'Open incident';
 const source=r.metadata?.source||r.source||'';
 if(source.includes('product_source_of_truth'))return 'Open Source of Truth';
 if(source.includes('api_documentation'))return 'Open API documentation';
 if(r.signal_type==='complaint')return 'Open complaint';
 return 'Open source';
}
export function InvestigationAnalysis({run,viewSource}:{run:Run;viewSource:(r:Evidence)=>void}){
 const a=run.analysis, cohort=run.session_review;
 function sources(refs:string[]){return <div className="mt-2 flex flex-wrap gap-x-4 gap-y-2">{refs.map(ref=>{const r=run.evidence[ref];return r?<button key={ref} className="link text-xs" onClick={()=>viewSource(r)}>{sourceLabel(r)}{r.session_id?` · ${r.session_id}`:r.incident_id?` · ${r.incident_id}`:r.component?` · ${r.component}`:''} ↗</button>:null})}</div>}
 function findings(items:Finding[]|undefined,empty:string){return items?.length?items.map((f,i)=><div key={i} className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-sm leading-6">{f.statement}{f.kind==='hypothesis'&&' (hypothesis)'}</p>{sources(f.evidence_refs)}</div>):<p className="muted">{empty}</p>}
 return <div className="space-y-5">
  <section><h3 className="font-semibold">1. Investigation finding</h3><div className="mt-2"><Badge tone={run.classification==='Insufficient Evidence'?'warning':'neutral'}>{names[run.classification]||run.classification}</Badge></div><p className="muted mt-2">{run.product} · {run.timeframe?.start?`${run.timeframe.start} – ${run.timeframe.end}`:run.day}</p></section>
  <section><h3 className="font-semibold">2. Customer impact</h3><p className="mt-2 text-sm">{cohort?.reviewed_sessions?cohort.failure_step?`${cohort.matching_sessions} of ${cohort.reviewed_sessions} reviewed sessions (${cohort.matching_customers} of ${cohort.reviewed_customers} customers) recorded a failure at ${cohort.failure_step} · ${cohort.affected_api}.`:`${cohort.reviewed_sessions} sessions from ${cohort.reviewed_customers} customers reviewed. No common explicit failure was recorded; this does not establish successful completion.`:'No customer sessions were retrieved. Customer impact is not established.'}</p>{cohort&&<p className="muted mt-2 text-xs">{cohort.scope_note}</p>}{!!cohort?.sessions.length&&<details className="mt-2"><summary className="text-sm">Reviewed sessions</summary>{cohort.sessions.map(s=><div key={`${s.customer_id}-${s.session_id}`} className="mt-2 text-sm">{s.customer_id} · {s.matches_pattern?'Same failure pattern':'Other observed journey'}{sources(s.evidence_refs.slice(0,1))}</div>)}</details>}</section>
  <section><h3 className="mb-2 font-semibold">3. Common customer journey</h3><ol className="space-y-2 border-l-2 border-slate-200 pl-4">{a?.common_journey?.map((f,i)=><li key={i} className="text-sm"><span className="font-medium">{i+1}. </span>{f.statement}{sources(f.evidence_refs)}</li>)}</ol>{!a?.common_journey?.length&&<p className="muted">A common journey has not been established.</p>}</section>
  <section><h3 className="mb-2 font-semibold">4. Dependency health</h3><div className="space-y-2">{a?.dependency_health?.map(d=><div key={d.api} className={`rounded-xl border bg-white p-4 ${d.status==='Degraded'?'border-red-200':'border-slate-200'}`}><div className="flex justify-between gap-2"><strong className="text-sm">{d.api}</strong><Badge tone={d.status==='Degraded'?'critical':d.status==='Healthy'?'good':d.status==='Unknown'?'warning':'neutral'}>{d.status}</Badge></div><p className="mt-2 text-sm">{d.statement}</p>{sources(d.evidence_refs)}</div>)}</div>{!a?.dependency_health?.length&&<p className="muted">Dependency health has not been established.</p>}</section>
  <section><h3 className="mb-2 font-semibold">5. Before / During / After</h3><div className="grid gap-3 md:grid-cols-3">{(['Before','During','After'] as const).map(phase=><div key={phase}><h4 className="mb-2 text-sm font-semibold">{phase}{phase==='After'?' recovery':''}</h4>{findings(a?.periods?.filter(p=>p.phase===phase),'No supported comparison available.')}</div>)}</div></section>
  <section><h3 className="mb-2 font-semibold">6. Complaint themes</h3><div className="space-y-2">{findings(a?.complaint_themes,'Complaint themes have not been established.')}</div></section>
  <section><h3 className="mb-2 font-semibold">7. Related incidents</h3><div className="space-y-2">{findings(a?.related_incidents,'No incident overlap has been established.')}</div></section>
  <section><h3 className="mb-2 font-semibold">8. Expected behavior</h3><div className="space-y-2">{findings(a?.expected_behavior,'Expected product and API behavior has not been established from retrieved documentation.')}</div></section>
  <section><h3 className="mb-2 font-semibold">9. Product Pulse assessment</h3><p className="mb-3 text-sm leading-6">{run.summary}</p><div className="space-y-2">{findings(run.findings,'No supported finding available.')}</div>{(!!run.missing_evidence.length||!!run.evidence_conflicts.length)&&<div className="mt-3 rounded-xl bg-amber-50 p-4"><h4 className="text-sm font-semibold">What remains uncertain</h4>{run.missing_evidence.map((m,i)=><p key={i} className="mt-2 text-sm">{m}</p>)}{findings(run.evidence_conflicts,'')}</div>}</section>
 </div>
}
