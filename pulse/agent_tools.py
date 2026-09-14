"""Seven evidence tools shared by Streamlit and the notebook."""
import csv, json, math
from collections import Counter
from datetime import datetime
from pathlib import Path
from langchain.tools import tool
from .data import ROOT

def build_tools(retriever, root=ROOT):
    """Create isolated tools for one agent; no process-global retriever or key state."""
    TOOLS_DATA_DIR = Path(root) / "data"

    _REQUIRED_COLUMNS = {
        "product.csv": {"product_id", "product_name", "product_description", "feature",
                        "dependent_api", "key_metric", "expected_baseline_pct"},
        "product_health.csv": {"record_id", "timestamp", "product_name", "signal_type",
                               "component", "metric_name", "value", "baseline", "severity",
                               "customer_id", "complaint_text", "incident_id", "details"},
        "customer_sessions.csv": {"customer_id", "session_id", "timestamp", "product_name",
                                  "page", "action", "result", "error_code", "service_called",
                                  "session_url"},
    }

    def _required(value: str, name: str) -> str:
        if not value.strip():
            raise ValueError(f"{name} must not be blank.")
        return value.strip()

    def _timestamp(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            raise ValueError("Use timestamps without a timezone, matching the demo CSV clock.")
        return parsed

    def _load_rows(filename: str) -> list[dict]:
        path = TOOLS_DATA_DIR / filename
        if not path.is_file():
            raise FileNotFoundError(f"Missing {path}. Set TOOLS_DATA_DIR to Product Pulse/data.")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            missing = _REQUIRED_COLUMNS[filename] - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"{filename}: missing columns {sorted(missing)}")
            records = []
            for row_number, row in enumerate(reader, start=1):
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"Malformed CSV record in {filename}, data row {row_number}.")
                row = {key: value.strip() for key, value in row.items()}
                for field in ("value", "baseline", "expected_baseline_pct"):
                    if field in row:
                        row[field] = float(row[field]) if row[field] else None
                        if row[field] is not None and not math.isfinite(row[field]):
                            raise ValueError(f"Non-finite {field} in {filename}, data row {row_number}.")
                if "timestamp" in row:
                    _timestamp(row["timestamp"])
                identity = row.get("record_id") or row.get("session_id") or row.get("product_id")
                row["_evidence"] = {
                    "source": f"data/{filename}",
                    "data_row": row_number,
                    "evidence_id": f"{filename}:{identity}:row-{row_number}",
                }
                records.append(row)
        return records

    def _select(rows: list[dict], filters: dict, start_time=None, end_time=None) -> list[dict]:
        start = _timestamp(start_time) if start_time is not None else None
        end = _timestamp(end_time) if end_time is not None else None
        if start is not None and end is not None and start >= end:
            raise ValueError("start_time must be earlier than end_time.")
        wanted = {k: _required(v, k).casefold() for k, v in filters.items() if v is not None}
        selected = []
        for row in rows:
            if any(row.get(k, "").casefold() != value for k, value in wanted.items()):
                continue
            if start is not None or end is not None:
                when = _timestamp(row["timestamp"])
                if (start is not None and when < start) or (end is not None and when >= end):
                    continue
            selected.append(row)
        return sorted(selected, key=lambda row: row.get("timestamp", ""))

    def _result(filename: str, rows: list[dict], filters: dict) -> dict:
        return {
            "status": "ok" if rows else "no_matches",
            "source": f"data/{filename}",
            "filters": filters,
            "record_count": len(rows),
            "records": rows,
        }

    def _health_records(product_name, signal_type=None, start_time=None, end_time=None,
                        customer_id=None, component=None):
        filters = {"product_name": _required(product_name, "product_name"),
                   "signal_type": signal_type, "customer_id": customer_id, "component": component}
        rows = _select(_load_rows("product_health.csv"), filters, start_time, end_time)
        result = _result("product_health.csv", rows, {
            **filters, "start_time": start_time, "end_time": end_time,
        })
        result["counts_by_signal_type"] = dict(Counter(row["signal_type"] for row in rows))
        return result


    @tool
    def get_product_context(product_name: str) -> dict:
        """Get product description, features, dependent APIs and expected baselines.

        product_name: Exact product name, case-insensitive. Returns source records,
        not an assessment of current health.
        """
        filters = {"product_name": _required(product_name, "product_name")}
        return _result("product.csv", _select(_load_rows("product.csv"), filters), filters)
    @tool
    def get_product_health(product_name: str, start_time: str | None = None,
                  end_time: str | None = None) -> dict:
        """Get all health evidence for a product: complaints, product metrics, API metrics, and incidents.

        Product/component/ID filters are exact and case-insensitive.
        Optional ISO timestamps use an inclusive start and exclusive end, without timezone.
        Returns all matching evidence records; no matches does not prove no issue exists.
        """
        return _health_records(product_name, None, start_time, end_time)
    @tool
    def get_complaints(product_name: str, start_time: str | None = None,
                  end_time: str | None = None, customer_id: str | None = None) -> dict:
        """Get customer complaint records for a product, optionally for one customer.

        Product/component/ID filters are exact and case-insensitive.
        Optional ISO timestamps use an inclusive start and exclusive end, without timezone.
        Returns all matching evidence records; no matches does not prove no issue exists.
        """
        return _health_records(product_name, 'complaint', start_time, end_time, customer_id=customer_id)
    @tool
    def get_incidents(product_name: str, start_time: str | None = None,
                  end_time: str | None = None) -> dict:
        """Get incident records for a product during an optional time window.

        Product/component/ID filters are exact and case-insensitive.
        Optional ISO timestamps use an inclusive start and exclusive end, without timezone.
        Returns all matching evidence records; no matches does not prove no issue exists.
        """
        return _health_records(product_name, 'incident', start_time, end_time)
    @tool
    def get_api_metrics(product_name: str, start_time: str | None = None,
                  end_time: str | None = None, component: str | None = None) -> dict:
        """Get API metric observations and their supplied baselines, optionally for one component.

        Product/component/ID filters are exact and case-insensitive.
        Optional ISO timestamps use an inclusive start and exclusive end, without timezone.
        Returns all matching evidence records; no matches does not prove no issue exists.
        """
        return _health_records(product_name, 'api_metric', start_time, end_time, component=component)
    @tool
    def find_customer_session(customer_id: str, product_name: str | None = None,
                              session_id: str | None = None, start_time: str | None = None,
                              end_time: str | None = None) -> dict:
        """Retrieve a customer's session events chronologically, with source references.

        customer_id is required. Product and session IDs are optional exact,
        case-insensitive filters. ISO start_time is inclusive and end_time exclusive;
        use timestamps without timezone, matching the CSV clock.
        """
        filters = {"customer_id": _required(customer_id, "customer_id"),
                   "product_name": product_name, "session_id": session_id}
        rows = _select(_load_rows("customer_sessions.csv"), filters, start_time, end_time)
        result = _result("customer_sessions.csv", rows, {
            **filters, "start_time": start_time, "end_time": end_time,
        })
        result["session_ids"] = sorted({row["session_id"] for row in rows})
        result["event_counts_by_result"] = dict(Counter(row["result"] for row in rows))
        return result
    @tool
    def search_product_docs(query: str) -> dict:
        """Search product Markdown for expected behavior, business rules and API guidance.

        query: A specific natural-language question including the product name.
        Returns retrieved passages and source metadata in similarity order.
        Retrieval is not exhaustive; no result does not establish absence of a rule.
        """
        query = _required(query, "query")
        if retriever is None:
            raise RuntimeError("Initialize the RAG retriever by running notebook sections 2–7 first.")
        docs = retriever.invoke(query)
        records = [{"citation_label": f"[{i}]", "evidence_ref": f"{doc.metadata['source']}:lines-{int(doc.metadata['line_start'])}-{int(doc.metadata['line_end'])}", "text": doc.page_content,
                    "metadata": dict(doc.metadata)}
                   for i, doc in enumerate(docs, start=1)]
        return {"status": "ok" if records else "no_matches", "query": query,
                "record_count": len(records), "records": records}
    return [get_product_context, get_product_health, get_complaints, get_incidents, get_api_metrics, find_customer_session, search_product_docs]
