import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import time
from fastapi.testclient import TestClient
import api as web
from pulse.knowledge_agent import verified_excerpt
import pytest

@pytest.fixture
def client():
    with web.LOCK:web.SESSIONS.clear()
    with TestClient(web.app) as c:
        c.headers['X-Pulse-Request']='1';c.get('/api/bootstrap');yield c

def test_quote_repair_checks_each_bullet():
    source='- First real rule.\nOther content.\n- Second real rule.'
    assert verified_excerpt('- First real rule.\n- Second real rule.',source)=='- First real rule.\n[…]\n- Second real rule.'
    with pytest.raises(ValueError):verified_excerpt('- First real rule.\n- Invented rule.',source)

def test_real_failed_quote_is_repaired():
    # The regression is non-contiguous real bullets, not an invalid credential.
    from pulse.knowledge_agent import build_knowledge_tools
    source=build_knowledge_tools()[0].invoke({'document_name':'product_source_of_truth.md'})['records'][1]['text']
    quote='- A newly added bank account must complete verification before it can be used for a payment.\n- A bank account remains unavailable for payment until verification succeeds.\n- Verification is required before first use of a newly added bank account.'
    repaired=verified_excerpt(quote,source)
    assert repaired.count('[…]')==2

def test_bootstrap_has_real_data_no_secrets(client):
    r=client.get('/api/bootstrap')
    assert r.status_code==200
    assert len(r.json()['products'])==3
    assert len(r.json()['signals'])>0
    assert 'OPENAI_API_KEY' not in r.text

def test_draft_and_export_require_server_approval(client):
    state=next(iter(web.SESSIONS.values()))
    gap={'id':'gap1','product':'Bank Account Management','why':'Verification is required','truth_ref':'data/product_source_of_truth.md:lines-20-20',
        'truth_evidence':{'source':'data/product_source_of_truth.md','line_start':20,'text':'Verify before payment.'},'current_evidence':{'source':'data/faq.md'}}
    state['knowledge']={'status':'completed','gaps':[gap]}
    assert client.post('/api/jobs',json={'kind':'draft','gap_id':'gap1'}).status_code==409
    client.post('/api/gaps/gap1/review',json={'decision':'Confirmed'})
    state['drafts']['gap1']={'proposed_wording':'Verify before payment.','reason':'Match product rules.','truth_ref':gap['truth_ref']}
    assert client.post('/api/gaps/gap1/export',json={'wording':'Verify before payment.'}).status_code==409
    assert client.post('/api/gaps/gap1/approve',json={'wording':'Verify before payment.'}).status_code==200
    assert client.post('/api/gaps/gap1/export',json={'wording':'Verify before payment.'}).status_code==200
    assert client.post('/api/gaps/gap1/export',json={'wording':'Changed wording'}).status_code==409
    client.post('/api/gaps/gap1/review',json={'decision':'Not a gap'})
    assert client.post('/api/gaps/gap1/export',json={'wording':'Verify before payment.'}).status_code==409

def test_jobs_are_isolated_and_user_triggered(client,monkeypatch):
    calls=[]
    def health(products,start,end,on_event=None):calls.append(products);return {'status':'completed','report':{'products':[]},'evidence':{}}
    monkeypatch.setattr(web,'run_product_health',health)
    assert not calls
    r=client.post('/api/jobs',json={'kind':'health','products':['Bank Account Management'],'start':'2026-09-03','end':'2026-09-03'})
    assert r.status_code==202
    jid=r.json()['id']
    for _ in range(30):
        result=client.get('/api/jobs/'+jid).json()
        if result['status']!='running':break
        time.sleep(.01)
    assert result['status']=='completed' and len(calls)==1
    other=TestClient(web.app)
    assert other.get('/api/jobs/'+jid).status_code==404

def test_mutations_need_header_and_sources_are_allowlisted(client):
    assert client.post('/api/jobs',json={'kind':'health'},headers={'X-Pulse-Request':''}).status_code==403
    assert client.get('/api/documents/.env').status_code==404
