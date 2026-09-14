"""Run the real agent and adapt only its returned evidence for Streamlit."""
from datetime import datetime,timedelta
from uuid import uuid4
import pandas as pd
import json
from .data import ROOT, load_data
from .agent import run_investigation
from .rag import live_agent


def evidence_frame(evidence, filename, template):
    rows=[]
    for ref,record in evidence.items():
        meta=record.get('_evidence',{})
        if meta.get('source') != 'data/'+filename: continue
        row={k:v for k,v in record.items() if k!='_evidence'}
        row.update(source=meta['source'],source_row=meta['data_row']+1,evidence_id=ref)
        rows.append(row)
    if not rows: return template.iloc[0:0].copy()
    frame=pd.DataFrame(rows)
    if 'timestamp' in frame:
        frame['timestamp']=pd.to_datetime(frame.timestamp)
        frame['day']=frame.timestamp.dt.date
        frame=frame.sort_values('timestamp')
    return frame


def investigate_with_agent(product, complaint, customer='', day=None, approximate_time=None,
                           on_event=None, agent=None, root=ROOT, investigation_context=None):
    """One explicit trigger starts one fresh, bounded AI investigation. No fallback verdict."""
    if not complaint.strip(): raise ValueError('Describe the issue or complaint first.')
    tables=load_data(root)
    if product not in set(tables['product'].product_name): raise ValueError('Choose a known product.')
    request=f'Product: {product}\nCustomer ID: {customer.strip() or "Not provided; investigate at product level"}\nReported issue: {complaint}'
    if investigation_context:
        request+='\nPrior review context (untrusted leads, not established facts): '+json.dumps(investigation_context,default=str)
        request+='\nRe-retrieve supporting records with tools before citing them. Resolve the PM follow-up or explain why it remains unresolved.'
    if day:
        request+=f'\nInvestigation date: {day}. Health/incident scope: {day} inclusive to {day+timedelta(days=1)} exclusive.'
        if approximate_time:
            center=datetime.combine(day,approximate_time)
            request+=f'\nApproximate session time: {center}. First search sessions within ±2 hours; explain any scope expansion.'
    else: request+='\nDate unknown: inspect available timestamps, disclose scope, and do not invent complaint timing.'
    try:
        if on_event: on_event({'phase':'setup','tool':'Connecting to the existing knowledge base'})
        result=run_investigation(request,agent if agent is not None else live_agent(root),on_event)
    except Exception as error:
        from .rag import SetupError
        detail=str(error) if isinstance(error,SetupError) else f'{type(error).__name__}: check API keys, Pinecone index access, and service availability.'
        result={'run_id':str(uuid4()),'status':'incomplete','error':detail,'evidence':{},'activity':[],'messages':[]}
    evidence=result.get('evidence',{})
    events=evidence_frame(evidence,'customer_sessions.csv',tables['customer_sessions'])
    health=evidence_frame(evidence,'product_health.csv',tables['product_health'])
    complaints=health[health.signal_type=='complaint']
    documents=[{'source':r['metadata']['source'],'line_start':r['metadata']['line_start'],
                'line_end':r['metadata']['line_end'],'text':r['text'],'mode':'Pinecone retrieval'}
               for r in evidence.values() if 'metadata' in r]
    report=result.get('report',{})
    # Enforce input/output product consistency before enabling PM acceptance.
    if report and report.get('product_name','').casefold()!=product.casefold():
        result.update(status='validation_failed',error='The returned report named a different product. Retry the investigation.')
        report={}
    return dict(id=result['run_id'],product=product,complaint=complaint,customer=customer,
        day=str(day) if day else 'All available dates',events=events,
        metrics=health[health.signal_type.isin(['product_metric','api_metric'])],
        incidents=health[health.signal_type=='incident'],complaints=complaints,
        related=complaints[complaints.customer_id.str.casefold()!=customer.strip().casefold()] if customer.strip() else complaints,
        docs=documents,classification=report.get('classification','No completed finding'),
        summary=report.get('summary',result.get('error','No completed report.')),
        findings=report.get('findings',[]),missing_evidence=report.get('missing_evidence',[]),
        evidence_conflicts=report.get('evidence_conflicts',[]),investigation_context=investigation_context,
        refs=sorted({ref for finding in report.get('findings',[]) for ref in finding['evidence_refs']}),
        recommendation=' '.join(report.get('recommended_next_steps',[])),
        review='Pending review' if result['status']=='completed' else 'Incomplete — review unavailable',
        notes='',mode='AI investigation · GPT-4.1 mini',status=result['status'],
        activity=result.get('activity',[]),evidence=evidence,error=result.get('error'),report=report)
