# Product Pulse — React workspace

TypeScript, React 19 and Tailwind CSS replace Streamlit as the primary demo interface. The existing three Python agents remain shared with the notebook. FastAPI is a local transport layer, not another agent.

## Run the built app

From Product Pulse:

```bash
.venv/bin/python -m pip install -r requirements-web.txt
.venv/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. The saved `frontend/dist` build needs no Node runtime to serve. API keys remain in the existing `.env`; they are never sent to the browser. Use one API worker for this session-local demo.

## PM journey

- **Product Health:** select products and dates → Run Health Scan → Review finding → Investigate.
- **Investigations:** New investigation → describe the complaint (or use the sample C1001 complaint) → review evidence → Confirm Finding, Investigate Further, or Disagree.
- **Knowledge Health:** Check Knowledge Consistency → Review gap → compare Source of Truth and downstream guidance → Confirm Gap → Draft Update → edit → Approve wording → Download approved request.
- **Opportunities:** review repeated responses across investigations → explore supporting sessions → save exploration notes.

One primary action per workspace; details open in a focused panel. Escape closes the panel. Evidence sources open separately and return to the finding. No agent runs on navigation. Explicit jobs can finish while the PM browses another page. API errors appear with a retry action and do not imply zero gaps. Confidence is not scored by the existing agent and is labeled accordingly.

The server validates confirmation and exact-preview approval before export; UI disabling is not the only gate. Review state is isolated by an HttpOnly browser-session cookie and held in server memory. Restarting the server loses reviews. Source changes invalidate prior approvals. This localhost demo has no production account authentication or persistent review database.

## Knowledge comparison fix

The reproduced failure was `Authoritative quote not found`: the model combined three real but non-contiguous source bullets into one quotation. The validator now verifies each complete bullet individually and marks omitted source content with `[…]`. Invented or unmatched text still fails validation. Prompts request one contiguous excerpt. The live Bank Account Management comparison completed after this fix.

## Frontend development

Requires Node 22.12+ (the delivered build used Node 22.23.2).

```bash
cd frontend
npm ci
npm run dev
```

Vite serves http://127.0.0.1:5173 and proxies `/api` to the Python service on port 8000. Run `npm run build` to refresh the static app served by Python. React uses [createRoot](https://react.dev/reference/react-dom/client/createRoot); Tailwind uses the [Vite integration](https://tailwindcss.com/docs/installation/using-vite).

## Tests

```bash
.venv/bin/python -m pytest tests -q
cd frontend
npm test
```

Browser tests require the API running on port 8000 and local Google Chrome at the path in `playwright.config.ts`. They mock model outputs; they do not incur AI charges. Python tests exercise server-side approval gates, source allowlisting, session isolation, and the quotation regression. Test fixtures contain synthetic evidence only.

## Files

- `frontend/src/App.tsx`: navigation, review panels and user-triggered jobs.
- `frontend/src/components.tsx`: evidence cards, timelines, source text and accessible drawers.
- `api.py`: session-local jobs, existing service calls, server-side review/export gates.
- `pulse/knowledge_agent.py`: the targeted quotation-validation fix.
- `app.py`: the earlier Streamlit interface retained for comparison.
- `product_pulse_rag.ipynb`: the same Python tools and agents, independently runnable.

## UI theme

The frontend uses the Clean Light palette: background `#F8FAFC`, sidebar `#EEF3F8`, navy headings `#17233C`, slate body text `#334155`, secondary text `#64748B`, and teal primary buttons `#0F766E`. White cards, DM Sans body text, and Outfit headings complete the theme. Health statuses retain distinct amber, rose, and green accents. Shared color tokens and controls live in `frontend/src/index.css`; reusable badges, empty states, and detail drawers live in `frontend/src/components.tsx`. Google Fonts supplies the typefaces, with system-font fallbacks when offline.

Run the responsive UI checks against a running frontend with `cd frontend && npx playwright test theme.spec.ts`. Set `PULSE_UI_URL` to override the default `http://127.0.0.1:8000`. These checks mock the bootstrap response and do not call the agents or require local demo data.

The Product Health overview renders compact product rows in `frontend/src/HealthDashboard.tsx`, with four status filters and a scan-insights column. Each row shows the latest available product/API reading in the scan window and counts of returned complaint/incident records. Charts use dated evidence only; missing readings and trends are labeled explicitly. Search filters product names and findings; sorting supports attention level and product name. Product names and row arrows open the existing finding review.

Knowledge Health uses `frontend/src/KnowledgeDashboard.tsx` for compact, document-focused gap reviews. The summary counts pending, confirmed, and rejected gaps in the selected product scope; successful comparisons validate all four documents. All-products results group gaps by product. Source links remain compact, and each gap opens the existing confirm/reject → draft → approve flow. Successful checks save a timezone-aware `checked_at` timestamp; failed retries retain the previous check. Run `npx playwright test knowledge-layout.spec.ts theme.spec.ts` from `frontend` to verify the layout and review entry points.

Product Health now uses `frontend/src/healthView.ts` to derive display-only summaries from the scan’s dated evidence and existing dependency catalog. Cards show a primary product metric, API coverage/status, complaint comparison, and incidents. Unknown dependencies remain explicit. Recovery requires a linked scan finding and subsequent near-baseline evidence; current degradation takes priority. Near-baseline tolerance and observation-time limitations are disclosed in the API detail view. The backend only exposes existing catalog rows in bootstrap; agent prompts, tools, source data, and findings are unchanged. Ask Product Pulse and Investigate send timeframe, affected API names, findings, metrics, complaints, and incidents as context to the existing Investigation Agent.
