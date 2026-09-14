"""Transparent, conservative demo analysis. Does not claim to be the live LLM agent."""
from uuid import uuid4
import pandas as pd
from .data import subset

PRODUCT_DROP = 5.0  # Percentage points, for the supplied percentage-rate metrics only.
API_RISE = 3.0
MIN_COMPLAINTS = 3

def health_issues(tables, product=None, start=None, end=None):
    health=subset(tables['product_health'],product,start,end)
    issues=[]
    for (name,day), group in health.groupby(['product_name','day']):
        complaints=group[group.signal_type=='complaint']
        pm=group[(group.signal_type=='product_metric') & ((group.baseline-group.value)>=PRODUCT_DROP)]
        api=group[(group.signal_type=='api_metric') & ((group.value-group.baseline)>=API_RISE)]
        incidents=group[(group.signal_type=='incident') & group.severity.isin(['SEV1','SEV2'])]
        # A substantial metric change needs a second signal and reported customer impact.
        if not pm.empty and not api.empty and len(complaints)>=MIN_COMPLAINTS:
            evidence=pd.concat([pm,api,incidents,complaints]).drop_duplicates('evidence_id')
            issues.append(dict(id=f'{name}-{day}',product=name,day=day,status='Needs attention',
                title=f"{pm.iloc[0].component}: success declined alongside API errors",
                detail=f"{len(complaints)} complaint records · {pm.iloc[0].metric_name} {pm.iloc[0].value:g}% vs {pm.iloc[0].baseline:g}% baseline",
                recommendation='Investigate customer impact and verify the relationship to the service event.',
                evidence=evidence,kind='service'))
        elif len(complaints)>=MIN_COMPLAINTS:
            sessions=subset(tables['customer_sessions'],name,day,day)
            restricted=sessions[sessions.error_code=='DATE_NOT_AVAILABLE']
            if restricted.session_id.nunique()>=3:
                evidence=pd.concat([complaints,restricted],ignore_index=True)
                issues.append(dict(id=f'{name}-{day}',product=name,day=day,status='Experience review',
                    title='Repeated friction around unavailable payment dates',
                    detail=f'{len(complaints)} complaint records · {restricted.session_id.nunique()} sessions with unavailable-date responses',
                    recommendation='Review clarity of payment-date guidance; this pattern alone does not establish a service outage.',
                    evidence=evidence,kind='experience'))
    return sorted(issues,key=lambda i:(i['kind']!='service',i['day']))

def investigate(tables, docs, product, complaint, customer='', day=None, approximate_time=None, extra_question=''):
    if not complaint.strip(): raise ValueError('Describe the issue or complaint first.')
    if product not in set(tables['product'].product_name): raise ValueError('Choose a known product.')
    events=subset(tables['customer_sessions'],product,day,day)
    if customer.strip(): events=events[events.customer_id.str.casefold()==customer.strip().casefold()]
    if approximate_time is not None and day is not None:
        center=pd.Timestamp.combine(day,approximate_time)
        events=events[(events.timestamp>=center-pd.Timedelta(hours=2)) & (events.timestamp<=center+pd.Timedelta(hours=2))]
    events=events.sort_values('timestamp')
    # Daily metrics/incident records are shown as same-day context, not exact overlap.
    health=subset(tables['product_health'],product,day,day)
    metrics=health[health.signal_type.isin(['product_metric','api_metric'])]
    incidents=health[health.signal_type=='incident']
    complaints=health[health.signal_type=='complaint']
    related=complaints[complaints.customer_id.str.casefold()!=customer.strip().casefold()] if customer.strip() else complaints
    documentation=docs.search(product,complaint)
    codes=set(events.error_code)
    finding='Insufficient Evidence'
    summary='The available evidence does not establish what caused this complaint.'
    refs=[]
    technical=events[events.error_code.isin(['BANK_VERIFY_TIMEOUT','BANK_VERIFY_UNAVAILABLE','SCHEDULING_503','SCHEDULING_500'])]
    if not technical.empty:
        finding='Technical / Service Issue'
        summary='The recorded session contains service-error responses. These support a service issue; the underlying root cause remains unconfirmed.'
        refs=technical.evidence_id.tolist()
    elif 'DATE_NOT_AVAILABLE' in codes:
        finding='Customer Experience Issue'
        summary='Sessions record unavailable-date responses. Review the explanation shown to the customer; the response alone does not establish a technical defect.'
        refs=events[events.error_code=='DATE_NOT_AVAILABLE'].evidence_id.tolist()
    elif 'NOT_ELIGIBLE' in codes and documentation:
        finding='Expected Product Behavior'
        summary='The recorded eligibility response is NOT_ELIGIBLE. The product documentation describes offer suppression for ineligible customers; review whether the complaint matches that event.'
        refs=events[events.error_code=='NOT_ELIGIBLE'].evidence_id.tolist()
    if events.empty:
        summary='No matching customer session was found in the selected scope. Health signals alone cannot explain this individual complaint.'
    if finding=='Insufficient Evidence':
        recommendation='Obtain the session identifier, timing, and supporting service evidence before reaching a conclusion.'
    else:
        recommendation='Review the cited session and documentation, then confirm the finding or request more evidence.'
    return dict(id=str(uuid4()),product=product,complaint=complaint,customer=customer,day=str(day) if day else 'All available dates',
                extra_question=extra_question,events=events,metrics=metrics,incidents=incidents,related=related,
                complaints=complaints,docs=documentation,classification=finding,summary=summary,refs=refs,
                recommendation=recommendation,review='Pending review',notes='',mode='Local evidence review')

def opportunities(runs):
    grouped={}
    for run in runs:
        if run['review']=='Disagreed' or run.get('status','completed')!='completed': continue
        for code, group in run['events'][run['events'].error_code!=''].groupby('error_code'):
            key=(run['product'],code)
            item=grouped.setdefault(key,dict(product=key[0],pattern=code,sessions=set(),complaints=set(),evidence={},runs=set()))
            item['sessions'].update(group.session_id)
            item['runs'].add(run['id'])
            for _,r in group.iterrows(): item['evidence'][r.evidence_id]=r.to_dict()
            matching=run['complaints'][run['complaints'].customer_id.isin(group.customer_id)]
            item['complaints'].update(matching.record_id)
    return [item for item in grouped.values() if len(item['sessions'])>=2]
