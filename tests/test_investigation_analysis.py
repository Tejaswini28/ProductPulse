from datetime import date
import pytest
from pulse.agent import InvestigationReport, validate_investigation
from pulse.agent_tools import build_tools
from pulse.investigation_analysis import session_review
from pulse.investigation_service import investigate_with_agent
from test_ai_connection import mock_agent


def event(session, result='FAILED', customer='C1', page='Scheduling'):
    return dict(product_name='Example',session_id=session,customer_id=customer,page=page,
                service_called='Scheduling API',result=result,timestamp='2026-09-06 12:00:00',
                _evidence={'source':'data/customer_sessions.csv'})


def test_session_counts_deduplicate_retries_and_do_not_treat_navigation_as_completion():
    evidence={'a':event('S1'),'b':event('S1'),'c':event('S2',customer='C2'),
              'd':event('S3','SUCCESS',customer='C3',page='Home'),
              'e':{**event('S4'), 'product_name':'Other'}}
    result=session_review(evidence,'Example')
    assert result['reviewed_sessions']==3
    assert result['matching_sessions']==2
    assert result['matching_customers']==2
    assert result['failure_step']=='Scheduling'
    assert len(result['sessions'])==3
    assert session_review({},'Example')['failure_step'] is None


def test_product_cohort_tool_returns_sessions_without_customer_filter_and_respects_dates():
    tool=next(t for t in build_tools(None) if t.name=='find_customer_session')
    result=tool.invoke({'product_name':'Bank Account Management','start_time':'2026-09-03','end_time':'2026-09-04'})
    assert len(result['session_ids'])>1
    assert all(r['product_name']=='Bank Account Management' and r['timestamp'].startswith('2026-09-03') for r in result['records'])
    assert tool.invoke({})['status']=='error'


def candidate():
    def finding(*refs, **extra):return dict(statement='Supported observation.',kind='observation',evidence_refs=list(refs),**extra)
    report=InvestigationReport(product_name='Example',classification='Technical / Service Issue',summary='Recorded failure.',
        findings=[finding('event')],missing_evidence=[],recommended_next_steps=[],analysis=dict(
            common_journey=[finding('event')],dependency_health=[finding('api',api='Scheduling API',status='Degraded')],
            periods=[finding('api','event',phase=p) for p in ['Before','During','After']],
            complaint_themes=[finding('complaint')],related_incidents=[finding('incident','event')],
            expected_behavior=[finding('truth','doc')]))
    evidence={'event':event('S1'),'api':{'signal_type':'api_metric','component':'Scheduling API'},
              'catalog':{'product_name':'Example','dependent_api':'Scheduling API'},
              'complaint':{'signal_type':'complaint'},'incident':{'signal_type':'incident'},
              'truth':{'metadata':{'source':'data/product_source_of_truth.md'}},
              'doc':{'metadata':{'source':'data/api_documentation.md'}}}
    return report,evidence


def test_analysis_sections_validate_all_citations():
    report,evidence=candidate()
    validate_investigation(report,evidence)
    assert report.classification=='Technical / Service Issue'
    report.analysis.common_journey[0].evidence_refs=['invented']
    with pytest.raises(ValueError):validate_investigation(report,evidence)


@pytest.mark.parametrize('missing',['api_dependency','after','api_docs','session'])
def test_missing_comparison_dependency_docs_or_sessions_abstains(missing):
    report,evidence=candidate()
    if missing=='api_dependency':evidence['other']={'product_name':'Example','dependent_api':'Profile API'}
    if missing=='after':report.analysis.periods=report.analysis.periods[:2]
    if missing=='api_docs':report.analysis.expected_behavior[0].evidence_refs=['truth']
    if missing=='session':report.analysis.periods[0].evidence_refs=['api']
    validate_investigation(report,evidence)
    assert report.classification=='Insufficient Evidence'
    assert report.missing_evidence


def test_api_status_cannot_be_supported_by_catalog_only():
    report,evidence=candidate()
    report.analysis.dependency_health[0].evidence_refs=['catalog']
    with pytest.raises(ValueError,match='API status requires readings'):validate_investigation(report,evidence)


def test_handoff_period_is_used_instead_of_unknown_date(monkeypatch):
    import pulse.investigation_service as service
    original=service.run_investigation
    requests=[]
    def capture(request,agent,on_event):
        requests.append(request)
        return original(request,agent,on_event)
    monkeypatch.setattr(service,'run_investigation',capture)
    context={'timeframe':{'start':'2026-09-02','end':'2026-09-08'}}
    run=investigate_with_agent('Bank Account Management','Verification failed',agent=mock_agent(),investigation_context=context)
    assert '2026-09-02 inclusive to 2026-09-09 exclusive' in requests[0]
    assert 'Date unknown' not in requests[0]
    assert run['timeframe']==context['timeframe']
    assert run['session_review']['reviewed_sessions']==2
