from datetime import date
import json
from pathlib import Path
import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.documents import Document
from pulse.agent import build_investigation_agent
from pulse.agent_tools import build_tools
from pulse.investigation_service import investigate_with_agent
from pulse.rag import corpus_namespace, settings, SetupError
ROOT=Path(__file__).resolve().parents[1]
class MockModel(FakeMessagesListChatModel):
    def bind_tools(self,tools,**kwargs): return self
class Retriever:
    def invoke(self,query):
        return [Document(page_content='Verification must succeed before payment.',metadata={'source':'data/product_source_of_truth.md','line_start':20,'line_end':20})]
def mock_agent(root=ROOT,bad_reference=False):
    tools=build_tools(Retriever(),root)
    context=tools[0].invoke({'product_name':'Bank Account Management'})
    ref=context['records'][0]['_evidence']['evidence_id']
    calls=[('get_product_context',{'product_name':'Bank Account Management'}),
           ('get_product_health',{'product_name':'Bank Account Management','start_time':'2026-09-03','end_time':'2026-09-04'}),
           ('find_customer_session',{'customer_id':'C1001'}),('find_customer_session',{'customer_id':'C1002'}),
           ('search_product_docs',{'query':'Bank Account Management verification'})]
    responses=[AIMessage(content='',tool_calls=[dict(name=name,args=args,id=str(i))]) for i,(name,args) in enumerate(calls)]
    report=dict(product_name='Bank Account Management',classification='Insufficient Evidence',summary='More evidence is needed.',
        findings=[dict(statement='Product context was retrieved.',kind='observation',evidence_refs=['fake-ref' if bad_reference else ref])],
        missing_evidence=['Root cause not established.'],recommended_next_steps=['Review evidence.'])
    responses.append(AIMessage(content='',tool_calls=[dict(name='InvestigationReport',args=report,id='report')]))
    return build_investigation_agent(MockModel(responses=responses),tools)

def test_real_service_with_mocked_model():
    activity=[]
    run=investigate_with_agent('Bank Account Management','Verification failed',day=date(2026,9,3),agent=mock_agent(),on_event=activity.append)
    assert run['status']=='completed'
    assert run['mode'].startswith('AI investigation')
    assert run['docs'][0]['text']=='Verification must succeed before payment.'
    assert run['events'].session_id.nunique()==2
    assert run['findings'][0]['evidence_refs'][0] in run['evidence']
    assert len([e for e in activity if e['phase']=='requested'])==5
    assert run['review']=='Pending review'

def test_bad_citation_never_approved():
    run=investigate_with_agent('Bank Account Management','Verification failed',agent=mock_agent(bad_reference=True))
    assert run['status']=='validation_failed'
    assert not run['report']

def test_namespace_stable_and_keys_required(tmp_path):
    assert corpus_namespace()==corpus_namespace()
    from unittest.mock import patch
    with patch.dict('os.environ',{},clear=True):
        with pytest.raises(SetupError):settings(tmp_path)

def test_error_no_local_fallback(monkeypatch):
    def fail(root):raise RuntimeError('fake-secret-should-not-appear')
    monkeypatch.setattr('pulse.investigation_service.live_agent',fail)
    run=investigate_with_agent('Bank Account Management','Verification failed')
    assert run['status']=='incomplete'
    assert run['events'].empty and not run['report']
    assert 'fake-secret' not in run['summary']

def test_agent_budget_stops_without_a_report():
    from pulse.agent import run_investigation
    tools=build_tools(Retriever(),ROOT)
    messages=[AIMessage(content='',tool_calls=[dict(name='get_product_context',args={'product_name':'Bank Account Management'},id=f'loop-{i}')]) for i in range(15)]
    result=run_investigation('Investigate indefinitely',build_investigation_agent(MockModel(responses=messages),tools))
    assert result['status']=='incomplete'
    assert result['pm_review']=='not_ready'
    successful=[m for m in result['messages'] if getattr(m,'name',None)=='get_product_context' and '"records"' in m.content]
    assert len(successful)==10
