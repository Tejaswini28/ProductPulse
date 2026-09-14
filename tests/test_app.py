from datetime import date
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pulse.data import load_data
from pulse.docs import Documentation,knowledge_gaps,draft_update
from pulse.analysis import health_issues,investigate,opportunities
from streamlit.testing.v1 import AppTest
ROOT=Path(__file__).resolve().parents[1]

def test_real_data_and_issues():
    data=load_data()
    assert len(data['product_health'])==90
    issues=health_issues(data)
    assert {i['product'] for i in issues if i['kind']=='service'}=={'Bank Account Management','Balance Assist Plan'}
    assert not health_issues(data,'Balance Assist Plan',date(2026,9,7),date(2026,9,7))
    assert all(i['evidence'].evidence_id.notna().all() for i in issues)

def test_investigation_and_deduplication():
    data=load_data();docs=Documentation()
    run=investigate(data,docs,'Bank Account Management','Verification failed','C1001',date(2026,9,3))
    assert run['classification']=='Technical / Service Issue'
    assert set(run['events'].customer_id)=={'C1001'}
    missing=investigate(data,docs,'Bank Account Management','Cannot verify','C9999',date(2026,9,3))
    assert missing['classification']=='Insufficient Evidence'
    allrun=investigate(data,docs,'Bank Account Management','Review verification',day=date(2026,9,3))
    patterns=opportunities([allrun,allrun])
    assert patterns[0]['sessions']==set(allrun['events'][allrun['events'].error_code=='BANK_VERIFY_TIMEOUT'].session_id)
    assert len(patterns[0]['runs'])==1

def test_gap_gating():
    gaps=knowledge_gaps(Documentation())
    assert len(gaps)==3
    with pytest.raises(ValueError):draft_update(gaps[0],False)
    assert 'verification succeeds' in draft_update(gaps[0],True)

def app():
    at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    assert not at.exception
    return at

def button(at,label):
    return next(b for b in at.button if b.label==label)

def test_navigation_and_investigation(monkeypatch):
    from test_ai_connection import mock_agent
    calls=[]
    def factory(root):
        calls.append(1)
        return mock_agent(root)
    monkeypatch.setattr('pulse.investigation_service.live_agent',factory)
    at=app()
    assert not calls
    button(at,'Investigate').click().run()
    assert not at.exception
    assert at.radio(key='nav').value=='Investigate'
    assert at.text_area(key='form_complaint').value
    assert len(calls)==1  # The overview button starts the queued investigation once.
    assert not at.json
    assert not any('tool activity' in e.label.lower() for e in at.expander)
    at.run()
    assert len(calls)==1  # An unrelated rerun does not trigger a paid call.
    button(at,'Confirm Finding').click().run()
    assert not at.exception
    assert at.session_state['runs'][0]['review']=='Confirmed'
    button(at,'Investigate Further').click().run()
    assert not at.exception
    assert 'Further question:' in at.text_area(key='form_complaint').value
    assert len(calls)==2  # PM follow-up starts a fresh evidence loop.
    followup=at.session_state['runs'][-1]['investigation_context']
    assert followup['origin']=='Investigate Further'
    assert followup['prior_report']==at.session_state['runs'][0]['report']
    at.radio(key='nav').set_value('Insights').run()
    assert not at.exception
    button(at,'Explore Opportunity').click().run()
    assert not at.exception
    assert at.session_state['explored']

def test_knowledge_approval(monkeypatch):
    from test_other_agents import knowledge_model
    from pulse.knowledge_agent import run_knowledge_consistency
    def fake_scan(products,on_event=None):
        return run_knowledge_consistency(products,model=knowledge_model(),on_event=on_event)
    monkeypatch.setattr('pulse.knowledge_agent.run_knowledge_consistency',fake_scan)
    monkeypatch.setattr('pulse.knowledge_agent.generate_update_draft',lambda gap,confirmed: {'proposed_wording':gap['truth_evidence']['text']})
    at=app()
    at.radio(key='nav').set_value('Knowledge Health').run()
    assert not at.exception
    button(at,'Check Knowledge Consistency').click().run()
    assert not at.exception
    gid=at.session_state['knowledge_scan']['gaps'][0]['id']
    assert at.button(key='draft-'+gid).disabled
    at.button(key='confirm-'+gid).click().run()
    at.button(key='draft-'+gid).click().run()
    assert not at.exception
    assert at.get('download_button')[0].disabled
    at.button(key='approve-'+gid).click().run()
    assert not at.exception
    assert not at.get('download_button')[0].disabled
    at.text_area(key='wording-'+gid).set_value('Changed draft wording').run()
    assert at.get('download_button')[0].disabled
    at.button(key='not-'+gid).click().run()
    assert not at.exception
    assert gid not in at.session_state['drafts']

def test_health_scan_runs_only_on_click(monkeypatch):
    calls=[]
    def scan(products,start,end,on_event=None):
        calls.append(products)
        return {'run_id':'test-health','status':'completed','report':{'summary':'Review complete.','products':[
            {'product_name':p,'status':'Monitor','summary':'Review the evidence.','limitations':['Synthetic data.'],
             'evidence_refs':[],'issues':[]} for p in products]},'evidence':{},'activity':[]}
    monkeypatch.setattr('pulse.health_agent.run_product_health',scan)
    at=app()
    assert not calls
    button(at,'Run Health Scan').click().run()
    assert not at.exception
    assert len(calls)==1 and len(calls[0])==3
    assert not at.json
    assert not any('agent activity' in e.label.lower() for e in at.expander)
    at.run()
    assert not at.exception
    assert len(calls)==1
