"""Run with: python -m streamlit run app.py"""
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
from pulse.data import ROOT,load_data,subset,fingerprint
from pulse.docs import Documentation,knowledge_gaps,draft_update,update_request
from pulse.analysis import health_issues,opportunities
from pulse.investigation_service import investigate_with_agent
from pulse.health_agent import run_product_health
from pulse.knowledge_agent import run_knowledge_consistency,generate_update_draft
from pulse.ui import style,badge,heading,metrics,records,doc_evidence,evidence_detail,concise,evidence_cards,raw_data,session_journeys,confidence_label,excerpt

st.set_page_config(page_title='Product Pulse',page_icon='◉',layout='wide',initial_sidebar_state='expanded')
style()
st.info("[Open the new Product Pulse workspace](http://127.0.0.1:8000) · This is the earlier Streamlit demo.")
try:
    tables=load_data()
    version=fingerprint()+':agent-design-v2'
except (OSError,ValueError) as error:
    st.error(f'Unable to load Product Pulse data: {error}')
    st.stop()
docs=Documentation()
products=sorted(tables['product'].product_name.unique())
health=tables['product_health']
first_day,last_day=health.day.min(),health.day.max()
for key,default in [('nav','Overview / Product Health'),('runs',[]),('gap_reviews',{}),('drafts',{}),('draft_details',{}),('approvals',{}),('explored',[]),('health_scans',{}),('knowledge_scan',None)]:
    if key not in st.session_state: st.session_state[key]=default
if st.session_state.get('dataset_version',version)!=version:
    # Old evidence must not silently retain approvals after files change.
    st.session_state.update(runs=[],gap_reviews={},drafts={},draft_details={},approvals={},active_run=None,health_scans={},knowledge_scan=None)
st.session_state.dataset_version=version

def review_run(run_id, decision):
    run=next(r for r in st.session_state.runs if r['id']==run_id)
    if run.get('status')!='completed':
        return
    notes=st.session_state.get('review-notes-'+run_id,'')
    run.update(review=decision,notes=notes)
    if decision=='Further investigation requested':
        st.session_state.form_complaint=run['complaint']+'\nFurther question: '+notes
        st.session_state.form_product=run['product']
        st.session_state.form_customer=run['customer']
        st.session_state.form_use_date=run['day']!='All available dates'
        if run['day']!='All available dates':
            st.session_state.form_date=datetime.strptime(run['day'],'%Y-%m-%d').date()
        st.session_state.pending_investigation=dict(product=run['product'],complaint=st.session_state.form_complaint,customer=run['customer'],day=st.session_state.form_date if st.session_state.form_use_date else None, investigation_context={
            'origin':'Investigate Further','prior_report':run.get('report',{}),
            'prior_run_id':run['id'],'pm_question':notes,
            'missing_evidence':run.get('missing_evidence',[])})

def open_investigation(product,day,complaint,context=None):
    st.session_state.nav='Investigate'
    st.session_state.form_product=product
    st.session_state.form_complaint=complaint
    st.session_state.form_customer=''
    st.session_state.form_date=day
    st.session_state.form_use_date=True
    st.session_state.active_run=None
    st.session_state.pending_investigation=dict(product=product,complaint=complaint,day=day,investigation_context=context)

with st.sidebar:
    st.markdown('<div class="brand"><span class="brand-mark">↗</span> Product Pulse</div>',unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">Workspace</div>',unsafe_allow_html=True)
    st.radio('Workspace', ['Overview / Product Health','Investigate','Knowledge Health','Insights','Evaluation'],key='nav',label_visibility='collapsed',format_func=lambda name:'Opportunities' if name=='Insights' else name)
    st.divider()
    st.markdown('<div class="principle"><strong>AI investigates.<br>PM decides.</strong></div>',unsafe_allow_html=True)
    st.caption('Evidence first. Decisions stay with you.')
    with st.expander('About this demo'):
        st.write('Synthetic data · AI-assisted investigations')
        st.caption(f'{first_day:%b %d} – {last_day:%b %d, %Y}')
        st.caption('Explore sample product data. Reviews run when you request them; this demo does not monitor live services.')
        st.caption('Review decisions and investigations last for this browser session. Download approved requests to retain them.')

st.title('Product Pulse')
st.markdown('<div class="hero-sub">AI-powered product intelligence for Product Managers</div>',unsafe_allow_html=True)

if st.session_state.nav=='Overview / Product Health':
    heading('What needs my attention?','Review product health and choose what to investigate.')
    c1,c2=st.columns([1,2])
    selected=c1.selectbox('Product',['All products']+products)
    dates=c2.date_input('Review period',value=(first_day,last_day),min_value=first_day,max_value=last_day)
    if len(dates)!=2:
        st.info('Select both the start and end of the review period.');st.stop()
    start,end=dates
    scoped=subset(health,selected,start,end)
    issues=health_issues(tables,selected,start,end)
    scan_products=products if selected=='All products' else [selected]
    scan_key=f'{selected}:{start}:{end}'
    if st.button('Run Health Scan',type='primary'):
        with st.spinner('Reviewing product health. This may take a moment…'):
            scan=run_product_health(scan_products,start,end)
            st.session_state.health_scans[scan_key]=scan
    scan=st.session_state.health_scans.get(scan_key)
    st.caption(f'Sample data · {start:%b %d}–{end:%b %d, %Y}')
    if scan and scan['status']=='completed':
        for brief in scan['report']['products']:
            with st.container(border=True):
                badge(brief['status'],'attention' if brief['status']=='Needs Attention' else 'review')
                st.subheader(brief['product_name'])
                items=brief['issues']
                if not items:
                    concise(brief['summary'])
                    evidence_cards(scan['evidence'],brief['evidence_refs'],limit=2)
                    st.write('**Recommendation:** Review the available evidence before deciding whether to investigate.')
                for number,issue in enumerate(items):
                    concise(issue['finding'])
                    st.caption(issue['severity']+' · '+', '.join(issue.get('affected_components',[brief['product_name']]))+' · '+issue['date'])
                    evidence_cards(scan['evidence'],issue['evidence_refs'],limit=3)
                    st.markdown('**Recommendation**')
                    concise(issue['recommendation'],label='Read full recommendation',limit=150)
                    if issue['investigate']:
                        st.button('Investigate',key=f"ai-health-{scan['run_id']}-{brief['product_name']}-{number}",type='primary',
                            on_click=open_investigation,args=(brief['product_name'],datetime.strptime(issue['date'],'%Y-%m-%d').date(),issue['finding'],{'origin':'Product Health','status':brief['status'],'issue':issue}))
                    else:st.caption('No deeper investigation recommended.')
                if brief['limitations']:
                    with st.expander('What remains uncertain'):
                        for limitation in brief['limitations']:st.write(limitation)
        raw_data({'report':scan['report'],'evidence':scan['evidence'],'activity':scan.get('activity',[])})
    elif scan:
        st.error('We couldn’t finish the review. Try again or narrow the products and dates.')
        raw_data({'error':scan.get('error'),'activity':scan.get('activity',[])})
    else:
        st.info('Run a health scan for a reviewed finding. These preliminary signals can help you choose where to start.')
        for issue in issues:
            with st.container(border=True):
                badge('Preliminary signal','review')
                st.subheader(issue['title'])
                st.caption(f"{issue['product']} · {issue['day']:%b %d, %Y}")
                evidence_cards({r['evidence_id']:r for r in issue['evidence'].to_dict('records')},limit=3)
                st.markdown('**Recommendation**')
                concise(issue['recommendation'],label='Read full recommendation',limit=150)
                st.button('Investigate',key='issue-'+issue['id'],type='primary',on_click=open_investigation,
                    args=(issue['product'],issue['day'],issue['title'],{'origin':'Supporting signal','finding':issue['detail'],'recommendation':issue['recommendation']}))
        if not issues:st.caption('No preliminary signals were flagged. Run a scan to review the available context.')
    with st.expander('Explore product trends',expanded=False):
        complaints=scoped[scoped.signal_type=='complaint']
        if not complaints.empty:
            trend=complaints.groupby(['day','product_name']).size().unstack(fill_value=0)
            trend=trend.reindex(pd.date_range(start,end).date,fill_value=0)
            st.line_chart(trend)
            st.caption('Supplied complaint records per day. Missing records do not establish zero complaints.')
        records(scoped[scoped.signal_type.isin(['product_metric','api_metric'])],'Product and API observations')
        records(scoped[scoped.signal_type=='incident'],'Incident context')
        raw_data(scoped)

elif st.session_state.nav=='Investigate':
    heading('What actually happened?','Investigate an issue or complaint and review the evidence behind the finding.')
    if 'form_use_date' not in st.session_state:st.session_state.form_use_date=True
    with st.expander('Describe an issue to investigate',expanded=not (st.session_state.runs or st.session_state.get('pending_investigation'))):
        with st.form('investigation_form'):
            cols=st.columns(2)
            product=cols[0].selectbox('Product',products,key='form_product')
            customer=cols[1].text_input('Customer ID (optional)',key='form_customer',placeholder='e.g. C1001')
            complaint=st.text_area('What did the customer report?',key='form_complaint',placeholder='Describe the complaint or issue to investigate.',height=100)
            with st.expander('Date and time (optional)'):
                cols=st.columns(3)
                use_date=cols[0].checkbox('Use an approximate date',key='form_use_date')
                day=cols[1].date_input('Approximate date',value=first_day,key='form_date')
                use_time=cols[2].checkbox('Use an approximate time',value=False)
                clock=st.time_input('Approximate time',value=datetime.strptime('09:30','%H:%M').time())
            submitted=st.form_submit_button('Investigate',type='primary')
    pending=st.session_state.pop('pending_investigation',None)  # Consume an explicit trigger exactly once.
    if submitted or pending:
        payload=pending or dict(product=product,complaint=complaint,customer=customer,
                                day=day if use_date else None,approximate_time=clock if use_time and use_date else None)
        with st.spinner('Investigating the issue and checking supporting evidence…'):
            try:
                run=investigate_with_agent(**payload)
                st.session_state.runs.append(run)
                st.session_state.active_run=run['id']
            except ValueError as error:
                st.error(str(error))
    runs=st.session_state.runs
    if runs:
        ids=[r['id'] for r in runs]
        active=st.session_state.get('active_run')
        selection=st.selectbox('Investigation history',ids,index=ids.index(active) if active in ids else len(ids)-1,
            format_func=lambda rid: next(f"{r['product']} · {r['customer'] or 'Product issue'} · {r['day']}" for r in runs if r['id']==rid))
        run=next(r for r in runs if r['id']==selection)
        if run.get('status')!='completed':
            st.error('This investigation is incomplete. Retry or narrow the issue and date range.')
        with st.container(border=True):
            badge(run['classification'],'review')
            st.caption(confidence_label(run))
            st.subheader('What Product Pulse found')
            concise(run['summary'],limit=200)
            st.caption(f"{run['product']} · {run['day']} · {run['review']}")
            if run.get('missing_evidence') or run.get('evidence_conflicts'):
                st.warning('Open questions remain. A root cause should not be assumed.')
                with st.expander('Review missing or conflicting evidence'):
                    for missing in run.get('missing_evidence',[]):st.write(missing)
                    for conflict in run.get('evidence_conflicts',[]):
                        st.write(conflict['statement'])
                        evidence_cards(run['evidence'],conflict['evidence_refs'],limit=2)
            st.markdown('**Why / supporting evidence**')
            findings=run.get('findings',[])
            for finding in findings[:2]:
                st.caption(finding['kind'].capitalize())
                concise(finding['statement'],label='Read full observation',limit=170)
            if len(findings)>2:
                with st.expander(f'Review {len(findings)-2} more observations'):
                    for finding in findings[2:]:
                        st.write(finding['kind'].capitalize()+': '+finding['statement'])
                        evidence_cards(run['evidence'],finding['evidence_refs'],limit=2)
            evidence_cards(run.get('evidence',{}),run.get('refs',[]),limit=3)
            st.markdown('**Recommendation**')
            recommendation=' '.join(run['recommendation']) if isinstance(run['recommendation'],list) else run['recommendation']
            concise(recommendation or 'Resolve the open questions, then investigate again.',label='Read full recommendation',limit=170)
            notes=st.text_area('Your notes or follow-up question',value=run['notes'],key='review-notes-'+run['id'])
            columns=st.columns(3)
            for col,label,value in zip(columns,['Confirm Finding','Investigate Further','Disagree'],['Confirmed','Further investigation requested','Disagreed']):
                col.button(label,key=label+run['id'],type='primary' if label=='Confirm Finding' else 'secondary',on_click=review_run,args=(run['id'],value),disabled=run.get('status')!='completed')
            st.caption('Review records a PM decision only. No customer messages or product changes are made.')
        st.subheader('Explore the evidence')
        journey,service,knowledge,complaints_tab=st.tabs(['Customer journey','Service health','Expected behavior','Customer complaints'])
        with journey:session_journeys(run['events'])
        with service:
            supporting=pd.concat([run['metrics'],run['incidents']])
            evidence_cards({r['evidence_id']:r for r in supporting.to_dict('records')},limit=3)
        with knowledge:
            if not run['docs']:st.caption('Expected behavior could not be verified from documentation.')
            for item in run['docs'][:2]:doc_evidence(item)
            if len(run['docs'])>2:
                with st.expander(f"View {len(run['docs'])-2} more documentation passages"):
                    for item in run['docs'][2:]:doc_evidence(item)
        with complaints_tab:
            with st.container(border=True):
                st.caption('Reported issue · '+(run['customer'] or 'Product-level review'))
                concise(run['complaint'],label='Read complete complaint')
                st.caption('The report describes the problem to investigate; it does not establish the cause.')
            evidence_cards({r['evidence_id']:r for r in run['related'].to_dict('records')},limit=2)
        raw_data({'report':run.get('report',{}),'evidence':run.get('evidence',{}),'activity':run.get('activity',[]),'error':run.get('error')})
    else:
        with st.container(border=True):
            st.subheader('Start with a question. Leave with evidence.')
            st.write('Choose a product and describe the issue. Add a customer ID to reconstruct a specific session.')
            st.caption('Try Bank Account Management · C1001 · September 3, 2026.')

elif st.session_state.nav=='Knowledge Health':
    heading('Is our product knowledge still accurate?','Check consistency with the authoritative Product Source of Truth.')
    knowledge_products=st.multiselect('Products to compare',products,default=products)
    if st.button('Check Knowledge Consistency',type='primary',disabled=not knowledge_products):
        with st.spinner('Comparing product guidance. This may take a moment…'):
            scan=run_knowledge_consistency(knowledge_products)
            st.session_state.knowledge_scan=scan
            st.session_state.gap_reviews={};st.session_state.drafts={};st.session_state.draft_details={};st.session_state.approvals={}
    scan=st.session_state.knowledge_scan
    if scan and set(scan['scope']['products'])!=set(knowledge_products):
        st.info('Selection changed. Run a new comparison for these products.')
        scan=None
    gaps=scan.get('gaps',[]) if scan and scan['status']=='completed' else []
    if scan:
        if scan['status']=='completed':
            concise(scan['report']['summary'],label='Read comparison overview',limit=170)
            with st.expander('Review scope and limitations'):
                for note in scan['report']['coverage_notes']:st.write(note)
        else:st.error(scan.get('error') or 'The comparison could not complete. Check service access and retry.')
    st.caption('Review each potential gap, confirm it, then draft an update for approval.')
    if not scan: st.info('Run a knowledge comparison to identify potential gaps.')
    elif scan['status']=='completed' and not gaps: st.info('No potential gaps were found in this review. See review scope and limitations for coverage.')
    for gap in gaps:
        gid=gap['id']; status=st.session_state.gap_reviews.get(gid,'Needs PM review')
        with st.container(border=True):
            badge(status,'review')
            st.subheader(gap['title'])
            st.caption(gap['product']+' · '+gap['file'])
            left,right=st.columns(2)
            with left:
                st.markdown('**Source of Truth**')
                doc_evidence(gap['truth_evidence'],'View source',why='Authoritative rule for product behavior.')
            with right:
                st.markdown('**Downstream section reviewed**' if gap['kind']=='Missing information' else '**Current guidance**')
                doc_evidence(gap['current_evidence'],'View source',why='Compare this guidance with the authoritative rule.')
            st.markdown('**Why it matters**')
            concise(gap['why'],label='Read full explanation',limit=180)
            st.markdown('**Recommendation**')
            st.write('Confirm whether this is a real gap before drafting replacement guidance.')
            cols=st.columns(3)
            if cols[0].button('Not a Gap',key='not-'+gid):
                st.session_state.gap_reviews[gid]='Not a gap'
                st.session_state.drafts.pop(gid,None);st.session_state.draft_details.pop(gid,None);st.session_state.approvals.pop(gid,None)
                st.session_state.pop('wording-'+gid,None)
                st.rerun()
            if cols[1].button('Confirm Gap',key='confirm-'+gid):
                st.session_state.gap_reviews[gid]='Confirmed';st.rerun()
            if cols[2].button('Draft Update',key='draft-'+gid,disabled=status!='Confirmed',type='primary'):
                try:
                    with st.spinner('Drafting wording from the confirmed gap…'):
                        generated=generate_update_draft(gap,status=='Confirmed')
                    st.session_state.drafts[gid]=generated['proposed_wording']
                    st.session_state.draft_details[gid]=generated
                    st.session_state['wording-'+gid]=generated['proposed_wording']
                    st.session_state.approvals.pop(gid,None)
                    st.rerun()
                except Exception:
                    st.error('The draft could not be generated. Check model access and retry; no update has been approved.')
            if gid in st.session_state.drafts and status=='Confirmed':
                wording=st.text_area('Proposed replacement wording',value=st.session_state.drafts[gid],key='wording-'+gid,height=120)
                details=st.session_state.draft_details.get(gid,{})
                preview=update_request(gap,wording,reason=details.get('reason'),truth_ref=details.get('truth_ref'))
                with st.expander('Documentation Update Request preview',expanded=True): st.markdown(preview)
                approved=st.session_state.approvals.get(gid)==preview
                if st.button('Approve wording',key='approve-'+gid,disabled=not wording.strip()):
                    st.session_state.approvals[gid]=preview;st.rerun()
                st.download_button('Export approved request',data=preview,file_name=f'product-pulse-{gid}-update.md',mime='text/markdown',disabled=not approved,key='export-'+gid)
                st.caption('Editing wording invalidates approval. Export downloads a request; it does not publish documentation or notify an owner.')
    if scan:raw_data({'report':scan.get('report'),'evidence':scan.get('evidence',{}),'activity':scan.get('activity',[])})
    with st.expander('Reference library · Source of Truth and supporting documents'):
        with st.container(border=True):
            badge('Authoritative')
            st.subheader('Product Source of Truth')
            st.caption('product_source_of_truth.md · designated authority for product behavior and business rules')
            with st.expander('View Source of Truth'):
                path=ROOT/'data/product_source_of_truth.md'
                if path.exists(): st.markdown(path.read_text())
                else: st.warning('Source of Truth file is missing; comparisons are unavailable.')
        st.caption('Use the Source of Truth to review whether a proposed gap needs a documentation update.')
        for filename in ['api_documentation.md','agent_procedures.md','product_faq.md']:
            with st.expander('View source document · '+filename):
                path=ROOT/'data'/filename
                if path.exists(): st.markdown(path.read_text())
                else: st.warning('Document unavailable.')

elif st.session_state.nav=='Insights':
    heading('Opportunities worth exploring','Emerging patterns from investigations, ready for your judgment.')
    patterns=opportunities(st.session_state.runs)
    st.caption('Patterns remain provisional until reviewed. Disagreed findings are excluded.')
    if not patterns:
        with st.container(border=True):
            st.subheader('Your evidence will build the picture')
            st.write('Run a product-level investigation to compare sessions. Recurring patterns appear when at least two distinct sessions share an error or response code.')
            st.button('Start an investigation',on_click=lambda:st.session_state.update(nav='Investigate'))
    for item in patterns:
        pid=item['product']+'-'+item['pattern']
        with st.container(border=True):
            badge('Potential opportunity','review')
            st.subheader(item['pattern'].replace('_',' ').capitalize())
            st.caption(item['product'])
            st.write(f"{len(item['complaints'])} complaint records · {len(item['sessions'])} distinct sessions · {len(item['runs'])} investigations")
            st.write('The same response recurs across the investigated sessions. It may point to a step worth improving.')
            st.caption('This pattern does not establish root cause or prevalence across all customers.')
            evidence_cards(item['evidence'],limit=2)
            st.markdown('**Recommendation**')
            st.write('Explore clearer guidance or recovery support at this step, and validate the need with customers.')
            if st.button('Explore Opportunity',key=pid):
                if pid not in st.session_state.explored: st.session_state.explored.append(pid)
            if pid in st.session_state.explored:
                st.text_area('Exploration notes',key='explore-'+pid,placeholder='What would you like to learn? What evidence would validate this opportunity?')
                st.caption('Exploration only. Requirements drafting can be added later; no roadmap commitment has been created.')

else:
    heading('Evaluation results','Scored against data/product_pulse_golden_eval_dataset.csv, the independent answer key.')
    results_path=ROOT/'eval_results'/'latest.csv'
    if not results_path.exists():
        with st.container(border=True):
            st.subheader('No evaluation run yet')
            st.write('Generate results with:')
            st.code('.venv/bin/python scripts/evaluate.py',language='bash')
            st.caption('Makes real OpenAI/Pinecone calls for the 15 agentic cases — not free, run deliberately.')
    else:
        results=pd.read_csv(results_path)
        st.caption(f'{len(results)} golden scenarios · file last updated {datetime.fromtimestamp(results_path.stat().st_mtime):%b %d, %Y %H:%M}')
        agentic=results[results.eval_type.isin(['product_health','investigation','knowledge_consistency'])]
        fail=results[results.eval_type=='failure_handling']
        hitl=results[results.eval_type=='human_in_loop']
        st.markdown('**Core quality**')
        metrics([
            ('Classification accuracy',f"{100*agentic.classification_correct.mean():.0f}%" if len(agentic) else 'n/a'),
            ('Retrieval accuracy',f"{agentic.retrieval_score.dropna().mean():.0f}%" if agentic.retrieval_score.notna().any() else 'n/a'),
            ('Evidence accuracy',f"{agentic.evidence_accuracy.dropna().mean():.0f}%" if agentic.evidence_accuracy.notna().any() else 'n/a'),
            ('Groundedness',f"{agentic.groundedness_score.dropna().mean():.1f} / 5" if agentic.groundedness_score.notna().any() else 'n/a'),
            ('Completeness',f"{agentic.completeness_score.dropna().mean():.1f} / 5" if agentic.completeness_score.notna().any() else 'n/a'),
            ('Correct abstention',f"{100*agentic.abstention_correct.mean():.0f}%" if len(agentic) else 'n/a'),
        ])
        st.markdown('**Reliability**')
        metrics([
            ('Tool failure recovery',f"{int(fail.tool_failure_recovered.sum())} / {len(fail)}"),
            ('Human-in-the-loop compliance',f"{int(hitl.hitl_compliant.sum())} / {len(hitl)}"),
        ])
        ph=results[results.eval_type=='product_health'];doc=results[results.eval_type=='knowledge_consistency']
        ph_pos=ph[ph.expected_classification=='Needs Attention'];ph_neg=ph[ph.expected_classification=='Healthy']
        doc_pos=doc[doc.expected_classification=='Potential Knowledge Gap'];doc_neg=doc[doc.expected_classification=='No Gap']
        st.markdown('**Product Health**')
        metrics([
            ('Issue detection recall',f"{100*ph_pos.classification_correct.mean():.0f}%" if len(ph_pos) else 'n/a'),
            ('False positive rate',f"{100*(1-ph_neg.classification_correct.mean()):.0f}%" if len(ph_neg) else 'n/a'),
        ])
        st.markdown('**Knowledge Consistency**')
        metrics([
            ('Gap detection recall',f"{100*doc_pos.classification_correct.mean():.0f}%" if len(doc_pos) else 'n/a'),
            ('False positive rate',f"{100*(1-doc_neg.classification_correct.mean()):.0f}%" if len(doc_neg) else 'n/a'),
        ])
        st.divider()
        st.markdown('**Per-case results**')
        show_failures_only=st.checkbox('Show only failed cases')
        table=results[results.passed==False] if show_failures_only else results
        st.dataframe(table,use_container_width=True,hide_index=True)
        st.caption('classification_correct / retrieval_score / abstention_correct / tool_failure_recovered / hitl_compliant are deterministic checks. evidence_accuracy / groundedness_score / completeness_score are LLM-as-judge scores.')
