"""Automated checks for the failure_handling and human_in_loop rows of
data/product_pulse_golden_eval_dataset.csv. These 9 cases need no LLM call —
they test tool resilience and PM-decision plumbing directly — so they run
in every pytest pass, unlike the agentic rows (see scripts/evaluate.py).
"""
import csv,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import api as web
from pulse.agent_tools import build_tools,with_retries
import pytest

GOLDEN=Path(__file__).resolve().parents[1]/'data'/'product_pulse_golden_eval_dataset.csv'

def golden_case(test_case_id):
    with GOLDEN.open() as f:
        for row in csv.DictReader(f):
            if row['test_case_id']==test_case_id:return row
    raise KeyError(f'{test_case_id} not found in golden dataset')

@pytest.fixture
def client():
    with web.LOCK:web.SESSIONS.clear()
    with TestClient(web.app) as c:
        c.headers['X-Pulse-Request']='1';c.get('/api/bootstrap');yield c

# ---- failure_handling ---------------------------------------------------

def test_FAIL_001_unknown_customer_returns_no_matches_not_a_crash():
    case=golden_case('FAIL-001')
    tools={t.name:t for t in build_tools(None)}
    result=tools['find_customer_session'].invoke({'customer_id':'C9999999-does-not-exist'})
    assert result['status']=='no_matches',case['expected_classification']
    assert result['records']==[]

def test_FAIL_002_tool_recovers_after_one_transient_failure():
    case=golden_case('FAIL-002')
    calls=[]
    def flaky():
        calls.append(1)
        if len(calls)<2:raise ValueError('transient metrics lookup failure')
        return {'status':'ok','metric':'api_error_rate'}
    result=with_retries(flaky)
    assert result['status']=='ok',case['expected_classification']
    assert len(calls)==2

def test_FAIL_003_tool_degrades_gracefully_after_retry_also_fails():
    case=golden_case('FAIL-003')
    calls=[]
    def always_fails():
        calls.append(1)
        raise ValueError('metrics tool unavailable')
    result=with_retries(always_fails)
    assert result['status']=='error',case['expected_classification']
    assert 'error' in result and result['records']==[]
    assert len(calls)==2  # one initial call, one retry — matches "One retry also fails" in the golden row

def test_FAIL_004_rag_unavailable_returns_error_not_exception():
    case=golden_case('FAIL-004')
    tools={t.name:t for t in build_tools(None)}  # retriever=None simulates Pinecone unavailable
    result=tools['search_product_docs'].invoke({'query':'Payment Flex eligibility rules'})
    assert result['status']=='error',case['expected_classification']
    assert 'Initialize the RAG retriever' in result['error']

# ---- human_in_loop --------------------------------------------------------

def _fake_run(rid='r1',status='completed',product='Balance Assist Plan'):
    return {'id':rid,'product':product,'complaint':'x','customer':'','day':'2026-09-06','status':status,
        'classification':'Technical / Service Issue','summary':'s','recommendation':'r','review':'Pending review',
        'notes':'','findings':[],'missing_evidence':[],'evidence_conflicts':[],'refs':[],'evidence':{},
        'events':[],'metrics':[],'incidents':[],'docs':[],'related':[],'report':{'product_name':product}}

def test_HITL_001_confirm_finding_persists_pm_decision(client):
    case=golden_case('HITL-001')
    state=next(iter(web.SESSIONS.values()));state['runs']['r1']=_fake_run()
    r=client.post('/api/investigations/r1/review',json={'decision':'Confirmed'})
    assert r.status_code==200,case['expected_classification']
    assert r.json()['review']=='Confirmed'

def test_HITL_002_investigate_further_carries_prior_state_forward(client,monkeypatch):
    case=golden_case('HITL-002')
    state=next(iter(web.SESSIONS.values()));state['runs']['r1']=_fake_run(status='completed')
    state['runs']['r1']['investigation_context']={'timeframe':{'start':'2026-09-02','end':'2026-09-08'},'affected_apis':['Payment Scheduling API']}
    captured={}
    def fake_investigate(product,complaint,customer,day,approx,on_event=None,investigation_context=None):
        captured.update(product=product,complaint=complaint,context=investigation_context)
        return _fake_run(rid='r2')
    monkeypatch.setattr(web,'investigate_with_agent',fake_investigate)
    r=client.post('/api/jobs',json={'kind':'investigation','prior_run_id':'r1','question':'Check whether retries succeeded'})
    assert r.status_code==202,case['expected_classification']
    jid=r.json()['id']
    for _ in range(30):
        job=client.get('/api/jobs/'+jid).json()
        if job['status']!='running':break
        time.sleep(.01)
    assert job['status']=='completed'
    assert captured['context']['origin']=='Investigate Further'
    assert captured['context']['timeframe']=={'start':'2026-09-02','end':'2026-09-08'}
    assert captured['context']['affected_apis']==['Payment Scheduling API']
    assert captured['context']['pm_question']=='Check whether retries succeeded'
    assert 'Follow-up:' in captured['complaint']  # original complaint retained, not restarted from scratch

def test_HITL_002_investigate_further_refuses_on_incomplete_prior(client):
    state=next(iter(web.SESSIONS.values()));state['runs']['r1']=_fake_run(status='incomplete')
    r=client.post('/api/jobs',json={'kind':'investigation','prior_run_id':'r1','question':'retry?'})
    assert r.status_code==409

def test_HITL_003_disagree_excludes_finding_from_confirmed_state(client):
    case=golden_case('HITL-003')
    state=next(iter(web.SESSIONS.values()));state['runs']['r1']=_fake_run()
    r=client.post('/api/investigations/r1/review',json={'decision':'Disagreed'})
    assert r.status_code==200,case['expected_classification']
    assert r.json()['review']=='Disagreed'

def test_HITL_004_confirm_gap_unlocks_draft_update_only(client,monkeypatch):
    case=golden_case('HITL-004')
    monkeypatch.setattr(web,'generate_update_draft',lambda gap,confirmed,**kw:{'proposed_wording':'x','reason':'x','truth_ref':gap['truth_ref']})
    state=next(iter(web.SESSIONS.values()))
    gap={'id':'g1','product':'Payment Flex','why':'x','truth_ref':'data/product_source_of_truth.md:lines-1-1',
        'truth_evidence':{'source':'data/product_source_of_truth.md','line_start':1,'text':'x'},'current_evidence':{'source':'data/faq.md'}}
    state['knowledge']={'status':'completed','gaps':[gap]}
    assert client.post('/api/jobs',json={'kind':'draft','gap_id':'g1'}).status_code==409,'draft must stay locked before confirmation'
    r=client.post('/api/gaps/g1/review',json={'decision':'Confirmed'})
    assert r.status_code==200,case['expected_classification']
    assert state['gap_reviews']['g1']=='Confirmed'
    assert client.post('/api/jobs',json={'kind':'draft','gap_id':'g1'}).status_code==202  # unlocked now that the gap is confirmed

def test_HITL_005_reject_gap_blocks_documentation_draft(client):
    case=golden_case('HITL-005')
    state=next(iter(web.SESSIONS.values()))
    gap={'id':'g1','product':'Payment Flex','why':'x','truth_ref':'data/product_source_of_truth.md:lines-1-1',
        'truth_evidence':{'source':'data/product_source_of_truth.md','line_start':1,'text':'x'},'current_evidence':{'source':'data/faq.md'}}
    state['knowledge']={'status':'completed','gaps':[gap]}
    r=client.post('/api/gaps/g1/review',json={'decision':'Not a gap'})
    assert r.status_code==200,case['expected_classification']
    assert client.post('/api/jobs',json={'kind':'draft','gap_id':'g1'}).status_code==409
