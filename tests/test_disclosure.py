from datetime import date
from test_app import app,button
from pulse.data import load_data
from pulse.ui import metric_copy,confidence_label

def assert_raw_is_collapsed(node,technical=False):
    label=getattr(node,'label','')
    if label=='Technical details / View raw data':
        technical=True
        assert not node.proto.expanded
    if getattr(node,'type','') in ('dataframe','json','code'):
        assert technical, 'Raw data appeared outside Technical details'
    for child in getattr(node,'children',{}).values():assert_raw_is_collapsed(child,technical)

def test_metric_interpretation_and_unscored_confidence():
    value,interpretation=metric_copy({'metric_name':'Verification Success Rate','value':70,'baseline':98})
    assert value=='70% current · 98% baseline'
    assert '28 percentage points below baseline' in interpretation
    assert 'Fewer successful completions' in interpretation
    assert 'not scored' in confidence_label({'status':'completed','classification':'Technical / Service Issue'})
    assert 'insufficient evidence' in confidence_label({'status':'completed','classification':'Insufficient Evidence'})

def test_health_issue_card_and_raw_disclosure(monkeypatch):
    data=load_data()['product_health']
    rows=data[(data.product_name=='Bank Account Management') & (data.day==date(2026,9,3))].to_dict('records')
    evidence={r['evidence_id']:r for r in rows}
    issue={'finding':'Verification attempts need attention','severity':'High','date':'2026-09-03',
        'affected_components':['Bank Account Management'],'evidence_refs':list(evidence),
        'recommendation':'Investigate the verification failures.','investigate':True}
    def scan(*args,**kwargs):
        return {'status':'completed','run_id':'cards','report':{'summary':'Review','products':[{
            'product_name':'Bank Account Management','status':'Needs Attention','summary':'Review',
            'issues':[issue],'evidence_refs':list(evidence),'limitations':[]}]},'evidence':evidence,'activity':[]}
    monkeypatch.setattr('pulse.health_agent.run_product_health',scan)
    at=app()
    button(at,'Run Health Scan').click().run()
    assert not at.exception
    assert any('Verification attempts' in m.value for m in at.markdown)
    assert any('View evidence'==e.label for e in at.expander)
    assert_raw_is_collapsed(at._tree)

def test_journey_and_review_flow_keep_raw_hidden(monkeypatch):
    from test_ai_connection import mock_agent
    monkeypatch.setattr('pulse.investigation_service.live_agent',lambda root:mock_agent(root))
    at=app();button(at,'Investigate').click().run()
    assert not at.exception
    assert any('class="journey"' in m.value for m in at.markdown)
    assert any('Confidence: insufficient evidence' in c.value for c in at.caption)
    assert not button(at,'Confirm Finding').disabled
    assert_raw_is_collapsed(at._tree)
