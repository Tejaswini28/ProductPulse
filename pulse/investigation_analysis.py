"""Evidence-only session counts; never read outside the agent's retrieved evidence."""
from collections import defaultdict


def session_review(evidence, product):
    sessions = defaultdict(list)
    for ref, row in evidence.items():
        if (row.get('_evidence', {}).get('source') == 'data/customer_sessions.csv'
                and row.get('product_name', '').casefold() == product.casefold()):
            sessions[(row.get('customer_id'), row.get('session_id'))].append((ref, row))
    patterns = defaultdict(set)
    for key, rows in sessions.items():
        for ref, row in rows:
            if row.get('result', '').upper() in {'FAILED', 'ERROR', 'TIMEOUT'}:
                patterns[(row.get('page') or row.get('action'), row.get('service_called') or 'Unspecified API')].add(key)
    common = max(patterns, key=lambda key: (len(patterns[key]), key), default=None)
    matched = patterns[common] if common else set()
    return {
        'reviewed_sessions': len(sessions),
        'reviewed_customers': len({key[0] for key in sessions}),
        'matching_sessions': len(matched),
        'matching_customers': len({key[0] for key in matched}),
        'failure_step': common[0] if common else None,
        'affected_api': common[1] if common else None,
        'scope_note': 'Counts describe retrieved sessions only, not all customers. Repeated failures in one session count once. Successful steps do not establish journey completion.',
        'sessions': [dict(customer_id=key[0], session_id=key[1], matches_pattern=key in matched,
                          evidence_refs=[ref for ref, _ in sorted(rows, key=lambda item: item[1].get('timestamp', ''))])
                     for key, rows in sorted(sessions.items())],
    }
