import {useState} from 'react';
import {ArrowRight,ArrowUpRight,BookOpen,Check,FileText,ShieldCheck} from 'lucide-react';
import {Badge,Empty,docName} from './components';
import type {Bootstrap,Evidence,Gap,Knowledge} from './types';

const sources=['api_documentation.md','agent_procedures.md','product_faq.md'];
const gapType=(kind:string)=>/missing/i.test(kind)?'Missing Guidance':/outdated|stale/i.test(kind)?'Outdated':/conflict|inconsisten/i.test(kind)?'Conflict':kind;
export function KnowledgeDashboard({data,knowledge,matches,product,onProduct,error,onReview,onSource}:{data:Bootstrap;knowledge:Knowledge|null;matches:boolean;product:string;onProduct:(value:string)=>void;error:string;onReview:(gap:Gap)=>void;onSource:(record:Evidence)=>void}){
 const [sort,setSort]=useState('review');
 const gaps=(matches?knowledge?.gaps||[]:[]).filter(g=>product==='All products'||g.product===product).sort((a,b)=>sort==='name'?a.title.localeCompare(b.title):Number(!!data.reviews[a.id])-Number(!!data.reviews[b.id]));
 const confirmed=gaps.filter(g=>data.reviews[g.id]==='Confirmed').length;
 const rejected=gaps.filter(g=>data.reviews[g.id]==='Not a gap').length;
 const pending=gaps.length-confirmed-rejected;
 const openDocument=(name:string)=>onSource({source:'data/'+name,text:name==='product_source_of_truth.md'?'Authoritative product rules':'Downstream product guidance'});
 const card=(gap:Gap)=><article className="knowledge-gap" key={gap.id}><div className="knowledge-gap-copy"><div className="flex flex-wrap items-center gap-2"><h3><button onClick={()=>onReview(gap)}>{gap.title}</button></h3><Badge tone={gapType(gap.kind)==='Conflict'?'warning':'neutral'}>{gapType(gap.kind)}</Badge>{<Badge tone={data.reviews[gap.id]==='Confirmed'?'good':'neutral'}>{data.reviews[gap.id]==='Not a gap'?'Rejected':data.approved[gap.id]?'Update approved':data.drafts[gap.id]?'Draft ready':data.reviews[gap.id]==='Confirmed'?'Confirmed':'Potential gap'}</Badge>}</div><div className="knowledge-gap-meta"><span>{gap.product}</span><span aria-hidden="true">·</span><button onClick={()=>onSource(gap.current_evidence)}><FileText size={13}/>{docName(gap.file)}<ArrowUpRight size={12}/></button></div><p className="knowledge-explanation" title={gap.why}>{gap.why}</p></div><button className="primary knowledge-review" onClick={()=>onReview(gap)}>Review gap<ArrowRight size={15}/></button></article>;
 return <section className="knowledge-minimal" aria-label="Knowledge comparison results">
  <div className="knowledge-toolbar"><div className="flex flex-wrap items-center gap-3"><label htmlFor="knowledge-product" className="text-sm font-medium">Product</label><select id="knowledge-product" value={product} onChange={e=>onProduct(e.target.value)}><option>All products</option>{data.products.map(p=><option key={p}>{p}</option>)}</select></div>{matches&&<p className="knowledge-summary" aria-label="Knowledge summary">4 docs checked · {pending} potential {pending===1?'gap':'gaps'} · {confirmed} confirmed{rejected>0&&` · ${rejected} rejected`}</p>}</div>
  <div className="knowledge-truth-row"><ShieldCheck size={18}/><strong>Product Source of Truth</strong><span>Authoritative product rules</span><button className="link" onClick={()=>openDocument('product_source_of_truth.md')}>View source<ArrowUpRight size={14}/></button></div>
  <div className="knowledge-checked"><h2>{matches?'Sources checked':'Sources to check'}</h2><div>{sources.map(name=><button key={name} onClick={()=>openDocument(name)}>{matches?<Check size={15}/>:<FileText size={15}/>} {docName(name)}<ArrowUpRight size={12}/></button>)}</div></div>
  {matches?<><div className="knowledge-list-heading"><h2>Gaps to review</h2><div className="flex items-center gap-2"><label htmlFor="knowledge-sort" className="text-xs text-slate-500">Sort by</label><select id="knowledge-sort" value={sort} onChange={e=>setSort(e.target.value)}><option value="review">Needs review first</option><option value="name">Gap title</option></select></div></div>
   {gaps.length?<div className="knowledge-groups">{product==='All products'?Object.entries(Object.groupBy(gaps,g=>g.product)).map(([name,rows])=><section className="knowledge-product-group" key={name} aria-label={name}><h3>{name}<span>{rows!.length} {rows!.length===1?'gap':'gaps'}</span></h3><div className="knowledge-gap-list">{rows!.map(card)}</div></section>):<div className="knowledge-gap-list">{gaps.map(card)}</div>}</div>:<Empty title="No gaps found in this review" icon={<Check size={24}/>}><p>This is an AI comparison, not a guarantee of complete consistency. Review the scope before deciding.</p></Empty>}
   <details className="muted mt-5"><summary>Check scope and limitations</summary>{knowledge?.report.coverage_notes.map((note,i)=><p className="mt-2" key={i}>{note}</p>)}</details>
  </>:<Empty title={error?'Your comparison needs another attempt':'Ready to check your guidance'} icon={<BookOpen size={25}/>}><p>Compare API Documentation, Agent Procedures and FAQ against the Source of Truth. Review potential gaps before drafting any changes.</p></Empty>}

 </section>;
}
