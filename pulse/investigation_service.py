"""Run the real agent and adapt only its returned evidence for Streamlit."""
from datetime import date,datetime,timedelta
from uuid import uuid4
import pandas as pd
import json
from .data import ROOT, load_data
from .agent import run_investigation
from .rag import live_agent
from .errors import describe
from .investigation_analysis import session_review


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
    timeframe=(investigation_context or {}).get('timeframe') or {}
    if timeframe.get('start') and timeframe.get('end'):
        start=date.fromisoformat(timeframe['start']); end=date.fromisoformat(timeframe['end'])
        if start>end: raise ValueError('Select a valid investigation date range.')
        request+=f'\nInvestigation period: {start} inclusive to {end+timedelta(days=1)} exclusive. Review customer sessions, complaints, metrics and incidents in this same period. Do not expand it silently.'
    elif day:
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
        if isinstance(error,SetupError):
            result={'run_id':str(uuid4()),'status':'incomplete','error':str(error),'evidence':{},'activity':[],'messages':[]}
        else:
            failure=describe(error,stage='investigation_analysis',model='gpt-4.1-mini')
            result={'run_id':str(uuid4()),'status':failure['status'],'error':failure['message'],'retryable':failure['retryable'],
                'failure_category':failure['category'],'technical_error':failure['technical_error'],'evidence':{},'activity':[],'messages':[]}
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
        analysis=report.get('analysis'),session_review=session_review(evidence,product),
        timeframe=timeframe,docs=documents,classification=report.get('classification','No completed finding'),
        summary=report.get('summary',result.get('error','No completed report.')),
        findings=report.get('findings',[]),missing_evidence=report.get('missing_evidence',[]),
        evidence_conflicts=report.get('evidence_conflicts',[]),investigation_context=investigation_context,
        refs=sorted({ref for finding in report.get('findings',[]) for ref in finding['evidence_refs']}),
        recommendation=report.get('recommended_next_steps',[]),
        review='Pending review' if result['status']=='completed' else 'Incomplete — review unavailable',
        notes='',mode='AI investigation · GPT-4.1 mini',status=result['status'],
        retryable=result.get('retryable',False),failure_category=result.get('failure_category'),technical_error=result.get('technical_error'),
        activity=result.get('activity',[]),evidence=evidence,error=result.get('error'),report=report)
