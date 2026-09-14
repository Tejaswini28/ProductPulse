"""Reusable Streamlit presentation components."""
from html import escape
import pandas as pd
import streamlit as st

CSS='''<style>
.journey{list-style:none;padding:0;margin:14px 0;}
.journey li{display:flex;gap:16px;border-left:2px solid #c5ddd8;padding:0 0 18px 16px;margin-left:5px;}
.journey time{font-size:13px;color:#637780;min-width:40px;padding-top:3px;}
.journey span{font-size:14px;color:#637780;}
.journey li:last-child{padding-bottom:0;}

@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stApp {font-family:'DM Sans',sans-serif;}
.stApp {background:#f7f9fb;color:#172e38;}
.block-container {max-width:1280px;padding:2.4rem 3rem 4rem;}
[data-testid="stSidebar"] {background:#fff;border-right:1px solid #e1e8ec;}
[data-testid="stSidebar"] .block-container {padding:2rem 1.3rem;}
h1 {font-size:2.35rem!important;font-weight:700!important;letter-spacing:-1.2px;}
h2 {font-size:1.7rem!important;letter-spacing:-.6px;}
h3 {font-size:1.15rem!important;font-weight:600!important;}
p,li,[data-testid="stWidgetLabel"] p {font-size:1rem;line-height:1.65;}
[data-testid="stVerticalBlockBorderWrapper"]>div {border-color:#e0e7ed!important;border-radius:14px!important;background:white;}
[data-testid="stMetric"] {padding:.35rem .25rem;}
[data-testid="stMetricValue"] {font-size:2rem!important;font-weight:600;color:#173e48;}
[data-testid="stMetricLabel"] {color:#637680;}
.stButton>button {border-radius:8px;min-height:42px;font-weight:600;}
.stButton>button[kind="primary"] {background:#126d68;border-color:#126d68;}
.stButton>button[kind="secondary"] {background:white;border-color:#d5dfe4;color:#254650;}
[data-testid="stCaptionContainer"] {color:#637780;}
.brand {display:flex;align-items:center;gap:10px;font-weight:700;font-size:21px;letter-spacing:-.6px;margin-bottom:28px;}
.brand-mark {background:#126d68;color:white;border-radius:11px;padding:5px 11px;font-size:23px;}
.eyebrow {font-size:11px;font-weight:700;letter-spacing:1.6px;color:#69818a;margin:12px 0 5px;text-transform:uppercase;}
.pill {display:inline-block;border-radius:30px;padding:4px 10px;font-size:12px;font-weight:600;background:#e9f4f0;color:#216455;margin-bottom:12px;}
.pill.attention {background:#fff1e4;color:#985623;}
.pill.review {background:#eef0fd;color:#5c55a4;}
.hero-sub {color:#637780;font-size:16px;margin-top:-12px;margin-bottom:24px;}
.principle {border-left:3px solid #53a99a;background:#eef7f4;padding:14px 16px;border-radius:0 8px 8px 0;font-size:14px;color:#29544e;}
.source {font-size:12px;color:#647d87;margin-top:8px;}
hr {border-color:#e4eaee;margin:1.6rem 0;}
@media(max-width:800px){.block-container{padding:1.5rem 1rem;}h1{font-size:1.8rem!important;}}
</style>'''

def style(): st.markdown(CSS,unsafe_allow_html=True)
def badge(text,kind=''):
    st.markdown(f'<span class="pill {escape(kind)}">{escape(text)}</span>',unsafe_allow_html=True)
def heading(title,subtitle):
    st.header(title)
    st.caption(subtitle)
def metrics(items):
    for col,(label,value) in zip(st.columns(len(items)),items):
        with col:
            with st.container(border=True): st.metric(label,value)
# Presentation only: no model calls, retrieval, or modification of evidence.
import json
import math
import re
from pathlib import Path
from .data import ROOT

RAW_LABEL='Technical details / View raw data'
DOC_NAMES={'product_source_of_truth.md':'Product Source of Truth','api_documentation.md':'API Documentation',
           'agent_procedures.md':'Agent Procedures','product_faq.md':'FAQ'}

def clean(value,default=''):
    if value is None: return default
    if isinstance(value,float) and math.isnan(value): return default
    return str(value)

def excerpt(text,limit=210):
    """Short verbatim preview, with an ellipsis—not a new AI summary."""
    text=' '.join(clean(text).split())
    if len(text)<=limit:return text
    return text[:limit].rsplit(' ',1)[0]+'…'

def concise(text,label='Read full finding',limit=210):
    st.write(excerpt(text,limit))
    if len(' '.join(clean(text).split()))>limit:
        with st.expander(label):st.write(text)

def raw_data(payload):
    with st.expander(RAW_LABEL,expanded=False):
        if isinstance(payload,pd.DataFrame):st.dataframe(payload,hide_index=True,width='stretch')
        else:st.code(json.dumps(payload,default=str,ensure_ascii=False,indent=2),language='json')

def stamp(value):
    if not clean(value):return 'Time not supplied'
    try:return pd.Timestamp(value).strftime('%b %d, %Y · %H:%M')
    except (ValueError,TypeError):return clean(value)

def metric_copy(record):
    """Use only supplied values; do not infer significance or metric direction."""
    try:
        current,baseline=float(record['value']),float(record['baseline'])
        if not math.isfinite(current) or not math.isfinite(baseline):raise ValueError()
    except (KeyError,ValueError,TypeError):
        return clean(record.get('value'),'Not supplied'),'Baseline unavailable; change cannot be assessed.'
    # These synthetic metrics are rates. Unknown units stay explicit.
    rate='rate' in clean(record.get('metric_name')).lower()
    unit='%' if rate else ''
    delta=current-baseline
    direction='above' if delta>0 else 'below' if delta<0 else 'at'
    interpretation=(f'{abs(delta):g} '+('percentage points' if rate else 'units')+f' {direction} baseline.' if delta else 'At the supplied baseline.')
    name=clean(record.get('metric_name')).lower()
    if delta and rate and 'error' in name:
        interpretation+= ' More errors than baseline.' if delta>0 else ' Fewer errors than baseline.'
    elif delta and rate and 'success' in name:
        interpretation+= ' More successful completions than baseline.' if delta>0 else ' Fewer successful completions than baseline.'
    return f'{current:g}{unit} current · {baseline:g}{unit} baseline',interpretation

def source_reference(record,reference=''):
    return reference or clean(record.get('evidence_id')) or clean(record.get('_evidence',{}).get('evidence_id'))

def evidence_card(record,reference='',why=None):
    if not record:
        st.caption('Supporting evidence is unavailable for this review.');return
    if 'metadata' in record or ('text' in record and 'source' in record):
        item={**record.get('metadata',{}),'text':record.get('text','')}
        if 'source' in record:item={**record,**item,'source':record['source']}
        doc_evidence(item,why=why);return
    kind=clean(record.get('signal_type'))
    context=stamp(record.get('timestamp'))
    if kind in ('api_metric','product_metric'):
        label='API health' if kind=='api_metric' else 'Product metric'
        title=clean(record.get('metric_name'),'Metric observation')
        value,interpretation=metric_copy(record)
        context=clean(record.get('component'))+' · '+context
        significance=why or interpretation+' This observation alone does not establish a cause.'
    elif kind=='complaint':
        label='Customer complaint';title=excerpt(record.get('complaint_text'),120)
        value=clean(record.get('customer_id'),'Customer not identified')
        significance=why or 'Shows the problem reported by a customer; the cause still needs verification.'
    elif kind=='incident':
        label='Incident';title=clean(record.get('incident_id'),'Incident record')
        value=clean(record.get('severity'),'Severity not supplied')+' severity · '+clean(record.get('component'))
        end=record.get('end_time') or record.get('resolved_at')
        context+=' → '+stamp(end) if end else ' · End time not supplied'
        significance=why or 'Provides service context for this period; exact overlap with a customer attempt is not established.'
    elif record.get('session_id'):
        label='Customer activity';title=clean(record.get('action'),'Recorded customer action')
        value=clean(record.get('result')).replace('_',' ').capitalize()
        context=clean(record.get('customer_id'))+' · '+context
        significance=why or 'Shows what the customer did and the recorded outcome.'
    else:
        label='Product context';title=clean(record.get('product_name'),'Supporting evidence')
        value=clean(record.get('dependent_api') or record.get('component') or record.get('details'))
        significance=why or 'Connects the product to the services involved in this review.'
    with st.container(border=True):
        st.caption(label)
        st.markdown('**'+title+'**')
        if value:st.write(value)
        st.caption(context)
        st.write(excerpt(significance,170))
        with st.expander('View evidence'):
            if kind=='complaint':st.write(record.get('complaint_text',''))
            elif kind=='incident':st.write(record.get('details','No incident description supplied.'))
            elif kind in ('api_metric','product_metric'):st.write(metric_copy(record)[1])
            elif record.get('session_id'):st.write(clean(record.get('action'))+' → '+clean(record.get('result')))
            if why:st.write(why)
            ref=source_reference(record,reference)
            if ref:st.caption('Source: '+ref)
            raw_data(record)

def evidence_cards(evidence,refs=None,limit=3):
    """Progressive disclosure with explicit overflow; never silently discard evidence."""
    selected=[(ref,evidence[ref]) for ref in dict.fromkeys(refs if refs is not None else evidence) if ref in evidence]
    if not selected:st.caption('No supporting records were returned for this finding.');return
    # Prefer diverse evidence types before displaying additional records.
    first=[];rest=[];seen=set()
    for pair in selected:
        record=pair[1]
        kind=record.get('signal_type') or ('documentation' if 'metadata' in record else 'session' if record.get('session_id') else 'context')
        if kind not in seen:first.append(pair);seen.add(kind)
        else:rest.append(pair)
    ordered=first+rest
    for col,(ref,record) in zip(st.columns(min(limit,len(ordered))),ordered[:limit]):
        with col:evidence_card(record,ref)
    if len(ordered)>limit:
        with st.expander(f'View {len(ordered)-limit} more supporting records'):
            for ref,record in ordered[limit:]:evidence_card(record,ref)

def records(frame,label='View evidence'):
    with st.expander(label):
        if frame.empty:st.caption('No supporting records in this scope.');return
        if 'session_id' in frame and 'action' in frame:session_journeys(frame)
        else:
            for _,r in frame.iterrows():evidence_card(r.to_dict())
        raw_data(frame)

def doc_evidence(item,label='View source',why=None):
    filename=Path(clean(item.get('source'))).name
    title=DOC_NAMES.get(filename,filename or 'Product documentation')
    text=clean(item.get('text'))
    section=next((line.lstrip('# ').strip() for line in text.splitlines() if line.startswith('## ')),'Relevant passage')
    if section=='Relevant passage' and filename in DOC_NAMES:
        path=ROOT/'data'/filename
        if path.exists():
            lines=path.read_text(encoding='utf-8-sig').splitlines()
            try:
                preceding=lines[:max(0,int(item.get('line_start',1)))]
                section=next((line.lstrip('# ').strip() for line in reversed(preceding) if line.startswith('## ')),section)
            except (ValueError,TypeError):pass
    # Avoid using Markdown headings as the entire excerpt.
    passage=' '.join(line for line in text.splitlines() if line.strip() and not line.startswith('#'))
    with st.container(border=True):
        st.caption(title+' · '+section)
        st.write(excerpt(passage,260) or 'No excerpt supplied.')
        st.caption(why or 'Defines expected behavior used to assess the finding.')
        with st.expander(label):
            if filename in DOC_NAMES:
                path=ROOT/'data'/filename
                if path.exists():
                    lines=path.read_text(encoding='utf-8-sig').splitlines()
                    try:
                        start=max(0,int(item.get('line_start',1))-1);end=min(len(lines),int(item.get('line_end',len(lines))))
                        # Render the actual source section, rather than a model-generated quote.
                        st.markdown('\n'.join(lines[start:end]))
                        st.caption(f'{title} · lines {start+1}–{end}')
                    except (ValueError,TypeError):st.caption('Source location is unavailable.')
                else:st.caption('Source document unavailable.')
            else:st.caption('Source document is not in the local reference library.')
            raw_data(item)

def session_journeys(frame,limit=2):
    if frame.empty:st.caption('No customer journey evidence was returned.');return
    groups=list(frame.sort_values('timestamp').groupby('session_id',sort=False))
    def journey(session,events):
        first,last=events.iloc[0],events.iloc[-1]
        with st.container(border=True):
            st.caption('Customer journey · '+clean(first.get('customer_id')))
            st.markdown('**'+clean(last.get('action'))+' → '+clean(last.get('result')).replace('_',' ').capitalize()+'**')
            st.caption(f'{stamp(first.timestamp)} → {pd.Timestamp(last.timestamp):%H:%M} · {len(events)} recorded steps')
            st.write('Shows the sequence leading to the last recorded outcome; later activity may be unavailable.')
            # The first four actual steps are visible. Remaining steps stay chronological on expansion.
            def steps(rows):
                html='<ol class="journey">'
                for _,event in rows.iterrows():
                    html+=f'<li><time>{escape(pd.Timestamp(event.timestamp).strftime("%H:%M"))}</time><div><strong>{escape(clean(event.get("action")))}</strong><br><span>{escape(clean(event.get("result")).replace("_"," ").capitalize())}</span></div></li>'
                st.markdown(html+'</ol>',unsafe_allow_html=True)
            steps(events.iloc[:4])
            if len(events)>4:
                with st.expander(f'Continue journey · {len(events)-4} more steps'):steps(events.iloc[4:])
            with st.expander('View evidence'):
                st.caption('Session '+clean(session))
                for _,event in events.iterrows():
                    st.write(f'{stamp(event.timestamp)} · {clean(event.get("action"))} · {clean(event.get("error_code"),"No error code supplied")}')
                    st.caption('Source: '+source_reference(event.to_dict()))
                raw_data(events)
    for session,events in groups[:limit]:journey(session,events)
    if len(groups)>limit:
        with st.expander(f'View {len(groups)-limit} more customer journeys'):
            for session,events in groups[limit:]:journey(session,events)

def confidence_label(run):
    # The existing agent has no calibrated confidence field. Do not manufacture a score.
    if run.get('status')!='completed':return 'Confidence: unavailable · review incomplete'
    if run.get('classification')=='Insufficient Evidence':return 'Confidence: insufficient evidence for a conclusion'
    return 'Confidence: not scored · assess the supporting evidence'

def evidence_detail(record,reference=''):
    evidence_card(record,reference)
