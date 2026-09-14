"""Read-only access to the synthetic source files. No generated observations."""
from pathlib import Path
import hashlib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    'product.csv': {'product_id','product_name','feature','dependent_api','key_metric','expected_baseline_pct','product_description'},
    'product_health.csv': {'record_id','timestamp','product_name','signal_type','component','metric_name','value','baseline','severity','customer_id','complaint_text','incident_id','details'},
    'customer_sessions.csv': {'customer_id','session_id','timestamp','product_name','action','result','error_code','service_called','session_url'},
}

def load_data(root=ROOT):
    tables = {}
    for filename, required in REQUIRED.items():
        frame = pd.read_csv(Path(root)/'data'/filename, dtype=str, keep_default_na=False)
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f'{filename} is missing columns: {sorted(missing)}')
        frame['source'] = 'data/' + filename
        frame['source_row'] = range(2, len(frame)+2)
        frame['evidence_id'] = [f'{filename}:row-{row}' for row in frame.source_row]
        if 'timestamp' in frame:
            frame['timestamp'] = pd.to_datetime(frame.timestamp, errors='raise')
            frame['day'] = frame.timestamp.dt.date
        for col in ('value','baseline','expected_baseline_pct'):
            if col in frame:
                frame[col] = pd.to_numeric(frame[col].replace('', None), errors='raise')
        tables[filename.removesuffix('.csv')] = frame
    return tables

def subset(frame, product=None, start=None, end=None):
    result = frame
    if product and product != 'All products':
        result = result[result.product_name == product]
    if start is not None:
        result = result[result.day >= start]
    if end is not None:
        result = result[result.day <= end]
    return result.copy()

def fingerprint(root=ROOT):
    digest = hashlib.sha256()
    for p in sorted((Path(root)/'data').glob('*')):
        if p.suffix in {'.csv','.md'}:
            digest.update(p.name.encode()); digest.update(p.read_bytes())
    return digest.hexdigest()[:16]
