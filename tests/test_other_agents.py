from pathlib import Path
from datetime import date
import pytest
from langchain_core.messages import AIMessage
from test_ai_connection import MockModel
from pulse.health_agent import run_product_health,validate_health,HealthReport
from pulse.knowledge_agent import build_knowledge_tools,run_knowledge_consistency,generate_update_draft,DOCUMENTS
ROOT=Path(__file__).resolve().parents[1]

def knowledge_model(root=ROOT):
    reader=build_knowledge_tools(root)[0]
    evidence={name:reader.invoke({'document_name':name})['records'] for name in DOCUMENTS}
    truth=next(r for r in evidence[DOCUMENTS[0]] if 'A bank account remains unavailable for payment until verification succeeds.' in r['text'])
    current=next(r for r in evidence['agent_procedures.md'] if 'may still be used for a payment while verification is pending' in r['text'])
    gap=dict(product_name='Bank Account Management',title='Verification guidance conflicts',kind='Conflicting rule',
        truth_ref=truth['evidence_ref'],truth_statement='A bank account remains unavailable for payment until verification succeeds.',
        current_ref=current['evidence_ref'],current_statement='A bank account that has been successfully added may still be used for a payment while verification is pending.',
        explanation='The procedure permits payment while verification is pending.')
    responses=[AIMessage(content='',tool_calls=[dict(name='read_knowledge_document',args={'document_name':name},id=str(i))]) for i,name in enumerate(DOCUMENTS)]
    responses.append(AIMessage(content='',tool_calls=[dict(name='KnowledgeReport',args={'summary':'One potential conflict.','gaps':[gap],'coverage_notes':['All four documents were read.']},id='report')]))
    return MockModel(responses=responses)

def test_health_agent():
    responses=[AIMessage(content='',tool_calls=[dict(name='analyze_health_window',args={'product_name':'Bank Account Management'},id='scan')]),
        AIMessage(content='',tool_calls=[dict(name='HealthReport',args={'summary':'Review needed.','products':[{'product_name':'Bank Account Management','status':'Needs Attention','summary':'Corroborated event.',
            'evidence_refs':['product_health.csv:row-51'],'issues':[{'finding':'Verification declined','affected_components':['Bank Account Management'],'date':'2026-09-03','severity':'High','evidence_refs':['product_health.csv:row-51','product_health.csv:row-57'],'recommendation':'Investigate','investigate':True}], 'limitations':['Daily snapshots.']}]},id='report')])]
    result=run_product_health(['Bank Account Management'],date(2026,9,3),date(2026,9,3),model=MockModel(responses=responses))
    assert result['status']=='completed',result.get('error')
    assert result['report']['products'][0]['issues'][0]['investigate']
    assert result['pm_review']=='awaiting_pm_review'

def test_knowledge_agent_and_quotes():
    result=run_knowledge_consistency(['Bank Account Management'],model=knowledge_model())
    assert result['status']=='completed',result.get('error')
    assert len(result['gaps'])==1
    assert result['gaps'][0]['truth_evidence']['source']=='data/product_source_of_truth.md'
    with pytest.raises(ValueError):generate_update_draft(result['gaps'][0],False)

def test_no_document_traversal():
    reader=build_knowledge_tools()[0]
    with pytest.raises(ValueError):reader.invoke({'document_name':'../.env'})

def test_health_schema_missing_product_rejected():
    report=HealthReport(summary='Unknown',products=[])
    with pytest.raises(ValueError):validate_health(report,{},['Bank Account Management'],date(2026,9,3),date(2026,9,3))

def test_knowledge_rejects_invented_quote_and_incomplete_coverage():
    from pulse.knowledge_agent import KnowledgeReport,validate_knowledge
    result=run_knowledge_consistency(['Bank Account Management'],model=knowledge_model())
    report=KnowledgeReport.model_validate(result['report'])
    report.gaps[0].truth_statement='Invented rule that does not exist.'
    with pytest.raises(ValueError,match='quote not found'):
        validate_knowledge(report,result['evidence'],['Bank Account Management'])
    with pytest.raises(ValueError,match='All four documents'):
        validate_knowledge(report,{},['Bank Account Management'])
