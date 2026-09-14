# Product Pulse agent design

**AI investigates. PM decides.** Product Pulse has exactly three core agents. CSV files, customer sessions, metrics, incidents, full document reads, and Pinecone RAG are tools or evidence sources—not agents. Insights aggregates investigation evidence; drafting is a confirmation-gated model call.

| Agent | Goal | Start action | Output |
|---|---|---|---|
| Product Health | What needs my attention? | Run Health Scan | One brief per requested product: status, correlated findings, affected components, citations, and an investigation recommendation. |
| Investigation | What actually happened, and what evidence supports it? | Investigate / Investigate Further | Classification, cited observations or hypotheses, missing evidence, unresolved cited conflicts, and recommended next steps. |
| Knowledge Consistency | Is our product knowledge still accurate and consistent? | Check Knowledge Consistency | Potential conflicts, missing guidance, or outdated guidance, with authoritative and downstream excerpts and an explanation. |

## Product Health

Review all requested products and the selected period. Correlate complaint patterns, anomalies, product deterioration, dependent API health, and incidents. Small metric fluctuations alone do not warrant an issue. Python calculates record counts and metric deltas; the agent interprets significance conservatively. Historical correlation never proves a current outage or root cause. Affected components must appear in cited evidence, with the product itself available when finer attribution is unknown.

## Investigation

Investigate either a surfaced issue or a specific complaint. The model selects among product context, complaints, sessions, product/API metrics, incidents, and Pinecone documentation. Reconstruct the customer journey when applicable, align time windows, compare expected product/API behavior, and use further tool calls when they can resolve gaps.

Allowed classifications are Expected Product Behavior, Technical / Service Issue, Customer Experience Issue, Knowledge / Documentation Issue, and Insufficient Evidence. A report admitting missing evidence needed for its finding, unresolved factual conflicts, or only hypotheses is classified Insufficient Evidence. Unknown citations fail validation. Validators check declared uncertainty and source identity; they cannot guarantee the model notices every conflict or makes every semantic inference correctly.

Source of Truth can resolve an authority conflict with downstream guidance: that may support Knowledge / Documentation Issue. Unresolved factual contradictions require abstention. Health handoffs retain issue context; follow-ups retain the prior report and PM question. Prior reports are leads, not registered evidence: source records must be retrieved again before citation.

The PM can Confirm Finding, Investigate Further, or Disagree. Confirmation does not establish that a hypothesis is a proven root cause and does not trigger an external action.

## Knowledge Consistency

Product Source of Truth is authoritative. Compare meaning against API Documentation, Agent Procedures, and FAQ. Read all four local documents before completing a comparison; Pinecone supports focused searches. A missing-guidance claim must explain relevance to the reviewed section's purpose. Age alone is not proof of outdated content.

Every gap includes actual authoritative and downstream quotations, source references, product, kind, and explanation. The PM selects Not a Gap or Confirm Gap. Draft Update is enabled only after confirmation. The resulting editable wording, reason, and Source of Truth reference feed a Documentation Update Request. Exact-preview approval is required for download; editing invalidates approval. Nothing is published or sent.

## Execution boundary

User actions start agents. Inside a run, tools are selected autonomously, bounded by ten evidence-tool calls and twelve model calls. There is no background scheduler, source-specific agent, or automatic health-to-investigation launch. Models have no tools to make roadmap decisions, publish documentation, send complaint responses, create commitments, or take customer-impacting actions.

Streamlit shows plain-language progress and evidence on demand. Notebook sections 30–33 run the same services and expose tool activity; section 35 explains the current contracts. RAG indexing, embedding settings, CSV data, and retrieval tools remain unchanged.
