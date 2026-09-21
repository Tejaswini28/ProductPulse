from datetime import date
import pytest
from pulse.agent import InvestigationReport,validate_investigation
from pulse.health_agent import HealthReport,validate_health
from pulse.docs import update_request
from pulse.investigation_service import investigate_with_agent
from test_ai_connection import mock_agent

def report(**changes):
    values=dict(product_name='Bank Account Management',classification='Technical / Service Issue',
        summary='A service issue occurred.',findings=[dict(statement='A service error was recorded.',kind='observation',evidence_refs=['a'])],
        missing_evidence=[],evidence_conflicts=[],recommended_next_steps=['Review supporting evidence.'])
    values.update(changes)
    return InvestigationReport(**values)

@pytest.mark.parametrize('changes',[
    {'missing_evidence':['Session timing is missing.']},
    {'evidence_conflicts':[dict(statement='Two records disagree about completion.',kind='observation',evidence_refs=['a','b'])]},
    {'findings':[dict(statement='An outage may explain this.',kind='hypothesis',evidence_refs=['a'])]},
])
def test_inconclusive_reports_abstain(changes):
    candidate=report(**changes)
    validate_investigation(candidate,{'a':{},'b':{}})
    assert candidate.classification=='Insufficient Evidence'
    assert 'does not support a conclusive finding' in candidate.summary

def test_old_summary_without_customer_analysis_abstains():
    candidate=report()
    validate_investigation(candidate,{'a':{}})
    assert candidate.classification=='Insufficient Evidence'

def test_conflicting_evidence_must_be_retrieved():
    candidate=report(evidence_conflicts=[dict(statement='Conflict',kind='observation',evidence_refs=['a','invented'])])
    with pytest.raises(ValueError,match='References not found'):validate_investigation(candidate,{'a':{}})

def test_health_component_must_be_supported():
    candidate=HealthReport(summary='Review',products=[dict(product_name='Bank Account Management',status='Needs Attention',summary='Review',
        evidence_refs=['a'],limitations=[],issues=[dict(finding='Service errors',affected_components=['Unrelated API'],date='2026-09-03',severity='High',
            evidence_refs=['a'],recommendation='Investigate',investigate=True)])])
    with pytest.raises(ValueError,match='Affected component'):
        validate_health(candidate,{'a':{'product_name':'Bank Account Management','component':'Bank Verification API'}},['Bank Account Management'],date(2026,9,3),date(2026,9,3))

def test_handoff_is_a_lead_and_not_registered_evidence(monkeypatch):
    import pulse.investigation_service as service
    original=service.run_investigation
    requests=[]
    def capture(request,agent,on_event):
        requests.append(request)
        return original(request,agent,on_event)
    monkeypatch.setattr(service,'run_investigation',capture)
    context={'origin':'Product Health','issue':{'finding':'Verification declined','evidence_refs':['prior-scan-only']}}
    run=investigate_with_agent('Bank Account Management','Verification failed',agent=mock_agent(),investigation_context=context)
    assert run['status']=='completed'
    assert 'untrusted leads' in requests[0] and 'prior-scan-only' in requests[0]
    assert 'prior-scan-only' not in run['evidence']
    assert run['investigation_context']==context

def test_update_request_preserves_drafted_reason_and_authority():
    gap={'product':'Example','why':'Original reason','current_evidence':{'source':'data/faq.md'},
         'truth_evidence':{'source':'data/product_source_of_truth.md','line_start':10,'text':'Authoritative rule'}}
    preview=update_request(gap,'Proposed wording',reason='Explain the required prerequisite.',truth_ref='data/product_source_of_truth.md:lines-10-12')
    assert 'Explain the required prerequisite.' in preview
    assert 'data/product_source_of_truth.md:lines-10-12' in preview
    assert 'Original reason' not in preview
