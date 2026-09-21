import type {Bootstrap,Evidence,Health,Issue,JobPayload} from './types';
export type Product=Health['report']['products'][number];
export type Bucket='attention'|'monitor'|'recovered'|'healthy';
export const labels:Record<Bucket,string>={attention:'Needs Attention',monitor:'Monitor',recovered:'Recently Recovered',healthy:'Healthy'};
export const buckets:Bucket[]=['attention','monitor','recovered','healthy'];
const key=(s='')=>s.toLowerCase().replace(/\s+api$/,'').trim();
const id=(r:Evidence)=>r.evidence_id||r._evidence?.evidence_id||'';
const unique=(rows:Evidence[])=>[...new Map(rows.map((r,i)=>[r.incident_id||id(r)||String(i),r])).values()];
const dated=(rows:Evidence[])=>rows.filter(r=>r.timestamp&&Number.isFinite(Date.parse(r.timestamp))).sort((a,b)=>a.timestamp!.localeCompare(b.timestamp!));
const rate=(r:Evidence)=>/rate|availability|percent/i.test(r.metric_name||'');
export const value=(r?:Evidence)=>r?.value==null?'Not supplied':`${r.value}${rate(r)?'%':''}`;
export const baseline=(r?:Evidence)=>r?.baseline==null?'Not supplied':`${r.baseline}${rate(r)?'%':''}`;
export const delta=(r?:Evidence)=>r?.value==null||r.baseline==null?'':`${r.value-r.baseline>=0?'+':''}${(r.value-r.baseline).toFixed(1)} ${rate(r)?'pts':'units'}`;
// Display-only classification. Unknown metric direction/baseline is never assumed healthy.
function deviation(r:Evidence){
 if(r.value==null||r.baseline==null)return null;
 const name=r.metric_name||'';
 if(/error|fail|latency/i.test(name))return r.value-r.baseline;
 if(/success|availability/i.test(name))return r.baseline-r.value;
 return null;
}
function tolerance(r:Evidence){return Math.max(.1,Math.min(2,Math.abs(r.baseline||0)*.2))}
function seriesState(rows:Evidence[],issues:Issue[]){
 const series=dated(rows);const latest=series.at(-1);const bad=series.filter(r=>deviation(r)!=null&&deviation(r)!>tolerance(r));
 const meaningful=bad.filter(r=>issues.some(i=>i.evidence_refs.includes(id(r))||i.affected_components.some(c=>key(c)===key(r.component))));
 const status=!latest||deviation(latest)==null?'unknown':deviation(latest)!>tolerance(latest)?'degraded':meaningful.length?'recovered':'healthy';
 const lastBad=bad.at(-1);const recovery=status==='recovered'&&lastBad?series.find(r=>r.timestamp!>lastBad.timestamp!&&deviation(r)!=null&&deviation(r)!<=tolerance(r)):undefined;
 return {series,latest,status,firstBad:bad[0],lastBad,recovery,meaningful:meaningful.length>0};
}
export function healthView(p:Product,scan:Health,data:Bootstrap){
 const all=unique(Object.values(scan.evidence).filter(r=>r.product_name===p.product_name));
 const current=all.filter(r=>r.timestamp&&r.timestamp.slice(0,10)>=scan.scope.start&&r.timestamp.slice(0,10)<=scan.scope.end);
 const catalog=(data.product_catalog||[]).filter(r=>r.product_name===p.product_name);
 const context=all.filter(r=>r.dependent_api);
 const names=[...new Set([...catalog,...context].map(r=>r.dependent_api).filter(Boolean) as string[])];
 const observed=current.filter(r=>r.signal_type==='api_metric');
 for(const r of observed){if(r.component&&!names.some(n=>key(n)===key(r.component)))names.push(r.component)}
 const apis=names.map(name=>{
  const rows=observed.filter(r=>key(r.component||r.dependent_api)===key(name));
  const groups=Object.groupBy(rows,r=>r.metric_name||'Unknown metric');
  const metrics=Object.values(groups).map(rs=>seriesState(rs!,p.issues));
  const status=metrics.some(m=>m.status==='degraded')?'degraded':!metrics.length||metrics.some(m=>m.status==='unknown')?'unknown':metrics.some(m=>m.status==='recovered')?'recovered':'healthy';
  const error=metrics.find(m=>/error rate/i.test(m.latest?.metric_name||''));
  const bad=metrics.flatMap(m=>m.series.filter(r=>deviation(r)!=null&&deviation(r)!>tolerance(r))).sort((a,b)=>a.timestamp!.localeCompare(b.timestamp!));
  const recoveries=metrics.filter(m=>m.meaningful).map(m=>m.recovery).filter(Boolean) as Evidence[];
  const incidents=current.filter(r=>r.signal_type==='incident'&&key(r.component)===key(name));
  return {name,status,metrics,error,peak:error?Math.max(...error.series.filter(r=>r.value!=null).map(r=>r.value!)):undefined,firstBad:bad[0],lastBad:bad.at(-1),recovery:status==='recovered'?dated(recoveries).at(-1):undefined,incidents};
 });
 const primaryIssue=[...p.issues].sort((a,b)=>({High:0,Medium:1,Low:2}[a.severity]??3)-({High:0,Medium:1,Low:2}[b.severity]??3))[0];
 const productRows=current.filter(r=>r.signal_type==='product_metric');
 const candidate=productRows.find(r=>primaryIssue?.evidence_refs.includes(id(r)))||productRows.find(r=>p.evidence_refs.includes(id(r)))||productRows[0];
 const primary=seriesState(productRows.filter(r=>r.metric_name===candidate?.metric_name&&r.component===candidate?.component),p.issues);
 const issueReadings=primary.series.filter(r=>r.timestamp?.slice(0,10)===primaryIssue?.date);
 const atIssue=issueReadings.find(r=>primaryIssue?.evidence_refs.includes(id(r)))||issueReadings.at(-1);
 const productGroups=Object.values(Object.groupBy(productRows,r=>`${r.component}|${r.metric_name}`)).map(rs=>seriesState(rs!,p.issues));
 const degraded=apis.filter(a=>a.status==='degraded');const recovered=apis.filter(a=>a.status==='recovered');const unknown=apis.filter(a=>a.status==='unknown');
 const unknownAffected=apis.some(a=>a.status==='unknown'&&p.issues.some(i=>i.affected_components.some(c=>key(c)===key(a.name))));
 const unresolvedIssue=p.issues.some(i=>!current.some(r=>(i.evidence_refs.includes(id(r))||i.affected_components.some(c=>key(c)===key(r.component)))&&(r.signal_type==='product_metric'||r.signal_type==='api_metric')));
 const recoveredProduct=productGroups.some(m=>m.status==='recovered');
 let bucket:Bucket=p.status==='No Significant Issue'?'healthy':p.status==='Needs Attention'?'attention':'monitor';
 if(degraded.length||productGroups.some(m=>m.status==='degraded'))bucket='attention';
 else if(p.issues.length&&(recovered.length||recoveredProduct)&&!unresolvedIssue&&!unknownAffected)bucket='recovered';
 else if(bucket==='healthy'&&(!apis.length||unknown.length||!primary.latest||p.status==='Insufficient Evidence'))bucket='monitor';
 const apiSummary=[degraded.length?`${degraded.length} degraded`:'',recovered.length?`${recovered.length} recently recovered`:'',unknown.length?`${unknown.length} without readings`:''].filter(Boolean).join(' · ')||(apis.length?'All healthy':'Dependencies not supplied');
 const days=(Date.parse(scan.scope.end)-Date.parse(scan.scope.start))/86400000+1;
 const priorStart=new Date(Date.parse(scan.scope.start)-days*86400000).toISOString().slice(0,10);
 const prior=all.filter(r=>r.timestamp&&r.timestamp.slice(0,10)>=priorStart&&r.timestamp.slice(0,10)<scan.scope.start);
 const complaints=current.filter(r=>r.signal_type==='complaint'),incidents=current.filter(r=>r.signal_type==='incident');
 return {p,primaryIssue,primary,atIssue,apis,bucket,apiSummary,catalogKnown:catalog.length>0,complaints,incidents,current,priorCount:prior.length?prior.filter(r=>r.signal_type==='complaint').length:null,priorStart,driver:apis.find(a=>primaryIssue?.affected_components.some(c=>key(c)===key(a.name)))||apis.find(a=>a.metrics.some(m=>m.meaningful))};
}
export type HealthView=ReturnType<typeof healthView>;
export function investigationPayload(view:HealthView,scan:Health,question?:string):JobPayload{
 const affected=view.apis.filter(a=>a.status==='degraded'||a.status==='recovered'||view.p.issues.some(i=>i.affected_components.some(c=>key(c)===key(a.name))));
 return {kind:'investigation',product:view.p.product_name,complaint:question||view.primaryIssue?.finding||view.p.summary,day:null,start:scan.scope.start,end:scan.scope.end,context:{origin:'Product Health',timeframe:{start:scan.scope.start,end:scan.scope.end},issue:view.primaryIssue,findings:view.p.issues,affected_apis:affected.map(a=>a.name),dependent_apis:view.apis.map(a=>({name:a.name,status:a.status})),complaints:view.complaints,metrics:view.current.filter(r=>r.signal_type?.endsWith('_metric')),incidents:view.incidents}};
}
