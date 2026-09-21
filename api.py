"""Local React API. Python agents remain the single source of business logic.
Run: .venv/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8000
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date,datetime,time
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4
import hashlib,json,math,secrets
import pandas as pd
from fastapi import FastAPI,Request,Response,HTTPException
from fastapi.responses import FileResponse,PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from pulse.data import ROOT,load_data,fingerprint
from pulse.analysis import health_issues,opportunities
from pulse.health_agent import run_product_health
from pulse.investigation_service import investigate_with_agent
from pulse.knowledge_agent import run_knowledge_consistency,generate_update_draft,DOCUMENTS
from pulse.docs import update_request

app=FastAPI(title='Product Pulse',docs_url=None,redoc_url=None)
POOL=ThreadPoolExecutor(max_workers=3)
LOCK=RLock()
SESSIONS={}

def serial(value):
    if isinstance(value,pd.DataFrame):return json.loads(value.to_json(orient='records',date_format='iso'))
    if isinstance(value,dict):return {str(k):serial(v) for k,v in value.items() if k!='messages'}
    if isinstance(value,(list,tuple,set)):return [serial(v) for v in value]
    if isinstance(value,(date,datetime)):return value.isoformat()
    if isinstance(value,float) and not math.isfinite(value):return None
    if hasattr(value,'item'):return serial(value.item())
    return value

def new_state():return {'version':fingerprint(),'jobs':{},'runs':{},'knowledge':None,'gap_reviews':{},'drafts':{},'approved':{},'explored':{},'health':None,'health_reviews':{}}

def finding_id(product_name,issue):
    basis=json.dumps([product_name,issue['finding'],issue['date']],sort_keys=True)
    return hashlib.sha256(basis.encode()).hexdigest()[:16]

@app.middleware('http')
async def browser_session(request:Request,call_next):
    if request.url.path.startswith('/api'):
        # JSON mutations are same-origin and require a custom header. No CORS exposure.
        if request.method!='GET' and request.headers.get('x-pulse-request')!='1':return PlainTextResponse('Missing request header',status_code=403)
        origin=request.headers.get('origin')
        if origin and origin!=str(request.base_url).rstrip('/') and origin not in ('http://127.0.0.1:5173','http://localhost:5173'):
            return PlainTextResponse('Origin not allowed',status_code=403)
        sid=request.cookies.get('pulse_session')
        with LOCK:
            if sid not in SESSIONS:sid=secrets.token_urlsafe(32);SESSIONS[sid]=new_state()
            state=SESSIONS[sid]
            if state['version']!=fingerprint():SESSIONS[sid]=state=new_state()
        request.state.session=state
        response=await call_next(request)
        response.set_cookie('pulse_session',sid,httponly=True,samesite='strict',max_age=86400)
        response.headers['Cache-Control']='no-store'
        return response
    return await call_next(request)

def session(request):return request.state.session

def public_run(run):return serial(run)

def safe_failure(error,stage='job'):
    from pulse.rag import SetupError
    if isinstance(error,SetupError):return str(error)
    from pulse.errors import describe
    return describe(error,stage=stage,model='gpt-4.1-mini')['message']

@app.get('/api/bootstrap')
def bootstrap(request:Request):
    data=load_data();health=data['product_health'];state=session(request)
    return serial({'product_catalog':data['product'].to_dict(orient='records'),'products':sorted(data['product'].product_name.unique()),'start':health.day.min(),'end':health.day.max(),
        'signals':health_issues(data),'runs':list(state['runs'].values()),'knowledge':state['knowledge'],
        'reviews':state['gap_reviews'],'drafts':state['drafts'],'approved':state['approved'],'opportunities':opportunities(list(state['runs'].values())),'explored':state['explored'],
        'health':state['health'],'health_reviews':state['health_reviews']})

class JobRequest(BaseModel):
    kind:Literal['health','investigation','knowledge','draft']
    products:list[str]=Field(default_factory=list)
    start:date|None=None
    end:date|None=None
    product:str=''
    complaint:str=''
    customer:str=''
    day:date|None=None
    approximate_time:time|None=None
    context:dict|None=None
    prior_run_id:str|None=None
    question:str=''
    gap_id:str|None=None
    wording:str=''
    feedback:str=''


def gap_for(state,gid):
    scan=state['knowledge']
    gap=next((g for g in (scan or {}).get('gaps',[]) if g['id']==gid),None)
    if not gap:raise HTTPException(404,'This gap is no longer available. Run a new comparison.')
    return gap

TOOL_LABELS={
    'get_product_context':'Reading product context',
    'get_product_health':'Checking product health metrics',
    'get_complaints':'Reviewing customer complaints',
    'get_incidents':'Checking incident records',
    'get_api_metrics':'Checking dependent API health',
    'find_customer_session':'Reconstructing the customer session',
    'search_product_docs':'Searching product documentation',
    'analyze_health_window':'Analyzing the review period',
    'read_knowledge_document':'Reading product knowledge documents',
}

def track_progress(job):
    def on_event(event):
        phase=event.get('phase')
        if phase not in ('requested','setup'):return
        label=event['tool'] if phase=='setup' else TOOL_LABELS.get(event['tool'],'Gathering evidence')
        with LOCK:job['step']=label
    return on_event

@app.post('/api/jobs',status_code=202)
def start_job(body:JobRequest,request:Request):
    state=session(request);data=load_data();known=set(data['product'].product_name)
    if body.kind in ('health','knowledge') and (not body.products or not set(body.products)<=known):raise HTTPException(422,'Select valid products.')
    if body.kind=='health' and (not body.start or not body.end or body.start>body.end):raise HTTPException(422,'Select a valid date range.')
    if body.kind=='investigation':
        if body.prior_run_id:
            prior=state['runs'].get(body.prior_run_id)
            if not prior or prior['status']!='completed':raise HTTPException(409,'Choose a completed finding to investigate further.')
            body.product=prior['product'];body.customer=prior['customer'];body.complaint=prior['complaint']+'\nFollow-up: '+body.question
            body.day=date.fromisoformat(prior['day']) if prior['day']!='All available dates' else None
            body.context={**(prior.get('investigation_context') or {}),'origin':'Investigate Further','prior_report':prior['report'],'pm_question':body.question}
        if body.start and body.end:
            body.context={**(body.context or {}),'timeframe':{'start':str(body.start),'end':str(body.end)}}
        if body.product not in known or not body.complaint.strip():raise HTTPException(422,'Choose a product and describe the issue.')
    if body.kind=='draft':
        gap=gap_for(state,body.gap_id)
        if state['gap_reviews'].get(body.gap_id)!='Confirmed':raise HTTPException(409,'Confirm the gap before drafting.')
    with LOCK:
        if any(j['status']=='running' for j in state['jobs'].values()):raise HTTPException(409,'A review is already running. Wait for it to finish before starting another.')
        jid=str(uuid4());job={'id':jid,'kind':body.kind,'status':'running','step':None};state['jobs'][jid]=job
    def work():
        try:
            progress=track_progress(job)
            if body.kind=='health':result=run_product_health(body.products,body.start,body.end,on_event=progress)
            elif body.kind=='knowledge':result=run_knowledge_consistency(body.products,on_event=progress)
            elif body.kind=='investigation':result=investigate_with_agent(body.product,body.complaint,body.customer,body.day,body.approximate_time,investigation_context=body.context,on_event=progress)
            else:result=generate_update_draft(gap,True,feedback=body.feedback or None,previous_wording=body.wording or None)
            with LOCK:
                if state['version']!=fingerprint():raise ValueError('Source data changed during the review.')
                if body.kind=='investigation':state['runs'][result['id']]=result
                if body.kind=='health' and result.get('status')=='completed':
                    for p in result['report']['products']:
                        for issue in p['issues']:issue['id']=finding_id(p['product_name'],issue)
                    result['scanned_at']=datetime.now().isoformat()
                    state['health']=result
                if body.kind=='knowledge' and result['status']=='completed':
                    result['checked_at']=datetime.now().astimezone().isoformat()
                    state.update(knowledge=result,gap_reviews={},drafts={},approved={})
                if body.kind=='draft':
                    if state['gap_reviews'].get(body.gap_id)!='Confirmed':raise ValueError('Gap confirmation was withdrawn.')
                    state['drafts'][body.gap_id]=result;state['approved'].pop(body.gap_id,None)
                job.update(status='completed',result=serial(result))
        except Exception as error:job.update(status='failed',error=safe_failure(error,stage=body.kind))
    POOL.submit(work)
    return {'id':jid}

@app.get('/api/jobs/{jid}')
def get_job(jid:str,request:Request):
    job=session(request)['jobs'].get(jid)
    if not job:raise HTTPException(404,'Review not found in this browser session.')
    return job

class Review(BaseModel):
    decision:Literal['Confirmed','Disagreed','Further investigation requested','Not a gap']
    notes:str=''

@app.post('/api/investigations/{rid}/review')
def review_investigation(rid:str,body:Review,request:Request):
    run=session(request)['runs'].get(rid)
    if not run or run['status']!='completed':raise HTTPException(409,'A completed finding is required for review.')
    if body.decision=='Not a gap':raise HTTPException(422,'Choose a finding review action.')
    run.update(review=body.decision,notes=body.notes)
    return public_run(run)

@app.post('/api/gaps/{gid}/review')
def review_gap(gid:str,body:Review,request:Request):
    state=session(request);gap_for(state,gid)
    if body.decision not in ('Confirmed','Not a gap'):raise HTTPException(422,'Choose a gap review action.')
    state['gap_reviews'][gid]=body.decision
    if body.decision=='Not a gap':state['drafts'].pop(gid,None);state['approved'].pop(gid,None)
    return {'decision':body.decision}

def finding_for(state,fid):
    scan=state['health']
    for p in (scan or {}).get('report',{}).get('products',[]):
        for issue in p['issues']:
            if issue['id']==fid:return issue
    raise HTTPException(404,'This finding is no longer available. Run a new health scan.')

class HealthReview(BaseModel):
    decision:Literal['monitoring','dismissed']
    reason:str=''

@app.post('/api/health-findings/{fid}/review')
def review_finding(fid:str,body:HealthReview,request:Request):
    state=session(request);finding_for(state,fid)
    state['health_reviews'][fid]={'decision':body.decision,'reason':body.reason}
    return state['health_reviews'][fid]

class Wording(BaseModel):
    wording:str=Field(min_length=1,max_length=20000)

@app.post('/api/gaps/{gid}/approve')
def approve(gid:str,body:Wording,request:Request):
    state=session(request);gap=gap_for(state,gid);draft=state['drafts'].get(gid)
    if state['gap_reviews'].get(gid)!='Confirmed' or not draft:raise HTTPException(409,'Confirm the gap and draft an update first.')
    if not body.wording.strip():raise HTTPException(422,'Enter proposed wording.')
    preview=update_request(gap,body.wording,draft['reason'],draft['truth_ref'])
    state['approved'][gid]=body.wording
    return {'preview':preview}

@app.post('/api/gaps/{gid}/export')
def export(gid:str,body:Wording,request:Request):
    state=session(request);gap=gap_for(state,gid);draft=state['drafts'].get(gid)
    if state['gap_reviews'].get(gid)!='Confirmed' or not draft:raise HTTPException(409,'Confirm and approve this update first.')
    if state['approved'].get(gid)!=body.wording:raise HTTPException(409,'Approve the current wording before downloading.')
    preview=update_request(gap,body.wording,draft['reason'],draft['truth_ref'])
    return {'preview':preview}

class Exploration(BaseModel):
    pattern_id:str
    notes:str=''

@app.post('/api/opportunities/explore')
def explore(body:Exploration,request:Request):
    state=session(request);valid={p['product']+'-'+p['pattern'] for p in opportunities(list(state['runs'].values()))}
    if body.pattern_id not in valid:raise HTTPException(404,'Pattern unavailable.')
    state['explored'][body.pattern_id]=body.notes
    return {'saved':True}

@app.get('/api/documents/{name}')
def document(name:str):
    if name not in DOCUMENTS:raise HTTPException(404,'Document unavailable.')
    return {'name':name,'text':(ROOT/'data'/name).read_text(encoding='utf-8-sig')}

DIST=ROOT/'frontend/dist'
if DIST.exists():
    app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
    @app.get('/')
    def frontend():return FileResponse(DIST/'index.html')
