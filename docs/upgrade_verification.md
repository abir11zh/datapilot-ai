# DataPilot AI — upgrade implementation and verification

Date: 2026-09-27. This upgrade continues the working application specified by the 31-page `datapilot.pdf` and the subsequent product-design brief. The user explicitly selected a separate web frontend, so the app runs with HTML/CSS/JavaScript and a Python API. Streamlit startup is replaced by verification of that actual application.

The original environment, services, workbook and notebook were preserved. Only the missing production server, Waitress 3.0.2, was installed. No virtual environment was recreated and no blanket reinstall was performed.

## Files created

| Files | Purpose |
|---|---|
| `frontend/ui.js` | Shared escaped rendering, cards, metrics, tables, charts, icons and request/error handling. |
| `services/config.py` | Validated environment configuration, explicit `.env` loading and safe public settings. |
| `services/profile_service.py` | Per-column profiles, distributions, missingness and cardinality. |
| `services/wsgi_service.py` | Production WSGI transport for the existing API. |
| `services/followup_service.py` | Conservative, validated country-exclusion edits to previously executed queries. |
| `tests/test_providers.py`, `tests/test_product.py` | Provider contracts, configuration, cloud behavior, product workflows and regression coverage. |
| `scripts/verify_upgrade.py` | Full reference-workbook and live local-AI acceptance checks. |
| `.env.example`, `DEPLOYMENT.md` | Local/cloud configuration and hosting instructions without real secrets. |
| `Dockerfile`, `.dockerignore` | Non-root Python image containing the app without local datasets or credentials. |
| `.github/workflows/tests.yml` | Linux CI for pytest, compilation and JavaScript syntax checks. |
| `docs/upgrade_verification.md` | This report. |

## Files modified

- `frontend/index.html`, `frontend/styles.css`, `frontend/app.js`: complete interface refresh and connected page workflows.
- `app.py`: shared local/WSGI dispatcher, environment-aware host/origin checks, provider/profile/customer/anomaly endpoints, preview/apply cleaning and safe errors.
- `services/llm_service.py`: local and remote provider abstraction; bounded structured requests and sanitized failures.
- `services/workspace_service.py`: cached profiles, preview tokens, explicit application, preserved filters and invalidation of stale analysis.
- `services/data_loader.py`, `services/data_cleaner.py`: richer schema and quality presentation with calculated scores, dimensions and affected-row samples.
- `services/agent_service.py`, `pages/ai_chat.py`: calculation evidence, execution context, chart reuse, deterministic tools and follow-ups.
- `services/chart_service.py`, `pages/insights.py`: consistent chart theme, visible single-point lines and provider-neutral calculated briefings.
- `pages/dashboard.py`, `services/insight_service.py`: guard numeric calculations when generic files contain text-valued retail column names.
- `ml/anomaly_detection.py`: scores, distributions, source-row selection and population comparisons.
- `prompts/sql_prompt.txt`, `tests/test_agent.py`, `tests/test_anomaly.py`: ranking definitions, conversation regressions and preservation of conflicting input column names.
- `requirements.txt`, `.gitignore`, `README.md`, `docs/demo.md`, `docs/technical_report.md`: server dependency, private-data exclusions and current operating documentation.

## Product changes

| Area | Delivered behavior |
|---|---|
| Design system | Purple primary color, pale workspace background, white cards, readable typography, consistent spacing, shared components, grouped navigation, responsive layouts, useful empty/loading/error states. |
| Dashboard | Adaptive revenue/orders/customers/products/AOV KPIs, time and country charts, product/customer/purchasing patterns, active filter chips and working analysis actions. Values come from the active dataset. |
| Dataset Explorer | Overview/Columns/Statistics/Preview tabs, searchable columns, full-column distributions and missing rates, category/date summaries, SQL workspace and chart builder. |
| Ask DataPilot | Schema-aware suggestions, calculated findings, table/chart/SQL, verified-calculation badge, engine/dataset/view/filter trace, bounded history and follow-ups. Missing columns yield clarification. |
| Data Quality | Transparent quality-score formula, dimensions and affected-row percentages, examples and type-conversion controls. Preview computes a candidate without activation; Apply activates a separate cleaned copy. |
| Automatic Insights | Executive briefing and categorized finding cards backed by actual calculations, supporting tables/SQL and related-question actions. Optional AI selects existing verified facts. |
| Customer Intelligence | RFM and deterministic scaled KMeans, cluster/revenue distributions, statistics, descriptive label rationale, customer lookup/profile, export and segment-aware chat. |
| Anomaly Detection | Isolation Forest scores and flags, rate/count/score KPIs, score distribution, transaction table and selected-row comparisons with the scored population. No fraud claim. |
| Data workflow | CSV/Excel import, worksheet switching, raw/prepared/cleaned views, filtering, cache reuse and downloads. Generic schemas work; retail-specific tools explain missing prerequisites. |
| Provider state | Dynamic local/cloud/unavailable status, actual connection checks, accurate privacy text and a recheck action. Offline analytics remain usable. |

Numerical chat output is rendered from executed result cells. The LLM can select tools and generate SQL, but cannot supply arbitrary numbers for the displayed answer. Validation protects execution; SQL can still misunderstand a question. Live semantic failures and ambiguity found during verification were addressed: customer rankings exclude missing customer IDs; an exact country-exclusion follow-up preserves prior filters, ordering and limits; and best-selling products consistently ranks net units using Description, or StockCode when Description is absent. Complex phrasing still uses the planner and remains subject to semantic uncertainty.

## Deployment and configuration

The same frontend and API run locally or through Waitress. Cloud mode does not require the developer's Windows paths, local workbook or laptop Ollama. Static assets and Plotly are served from the application; there is no frontend build step or CDN dependency.

Local launch in the existing environment:

```powershell
.\launch.ps1
# Or, with the existing virtual environment active:
python app.py
```

Open `http://127.0.0.1:8501`. Local AI defaults to `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://127.0.0.1:11434`, `OLLAMA_MODEL=qwen3:4b`. The app never installs Ollama or pulls a model automatically.

For a hosted Python service, install requirements on that new host and start `python app.py --server waitress`. Required cloud settings are `APP_MODE=cloud` and `PUBLIC_URL=https://your-actual-origin`; `HOST=0.0.0.0` is the cloud default and `PORT` follows the host. Remote chat additionally needs `LLM_PROVIDER=remote`, `REMOTE_LLM_BASE_URL`, `REMOTE_LLM_MODEL` and `REMOTE_LLM_API_KEY`. `REMOTE_LLM_FORMAT=json_object` is the default; compatible providers can use `json_schema`. Set secrets in the hosting platform, never in committed files. `LLM_PROVIDER=disabled` supports an analytics-only deployment.

Optional bounds: `LLM_TIMEOUT_SECONDS=180`, `MAX_UPLOAD_MB=100`, `MAX_SESSIONS=8`, `SESSION_TTL_SECONDS=7200`. See [DEPLOYMENT.md](../DEPLOYMENT.md) and [.env.example](../.env.example) for complete commands and Docker configuration.

The remote adapter uses compatible chat-completions HTTP endpoints, with no OpenAI SDK or required OpenAI service. There is no silent fallback between local and remote providers. Only questions, schema and bounded calculated context are sent to the selected AI provider; full datasets are not included.

## GitHub readiness

The app has CI, portable dependencies, deployment files and a professional README. Ignore rules exclude real datasets, uploads, processed exports, caches, secrets, environments, logs and generated verification evidence. `.env.example` is explicitly included. The project directory must be the repository root; its surrounding Downloads folder must not be published.

No repository was pushed, no public host was provisioned and no project license was asserted. Public publication still requires the user's chosen repository/host and its credentials. This distinction is intentional: deployment files are delivered, but there is no fabricated live public URL.

## Verification

- **85 pytest tests passed.** Coverage includes SQL security, cleaning/raw preservation, RFM, clustering, anomalies, mocked planning/corrections, deterministic follow-ups, ranking definitions, generic-schema edge cases, HTTP routes, isolation, cloud configuration, remote-provider contracts and preview/apply behavior.
- Python compilation, both JavaScript syntax checks and imports of all **25 application modules** passed. The final live server log contained startup entries and no runtime errors.
- Browser checks exercised CSV and two-sheet Excel uploads, generic-column profiling, sheet/view switching, preview/apply cleaning, filters, insights, customer profiles, anomaly comparisons and chat calculation traces.
- Cloud mode was launched with missing AI credentials. The UI correctly showed unavailable AI, explained configuration and continued to accept uploads and calculate analytics. Automated cloud tests also remove reference-data availability and verify host/origin checks and secure-cookie behavior.
- Dashboard responsiveness was measured at requested viewport widths **1920, 1440, 1280, 1024 and 390 pixels**. At each size, document scroll width equaled its client width and five fixture charts rendered. Table regions retain their own horizontal scrolling. Browser console checks returned no warnings/errors during the completed flows.
- The final live acceptance run **passed completely** against Online Retail II, worksheet Year 2010-2011: **541,910 raw rows and 8 original columns**. It exercised the dashboard, quality report, full Revenue profile, customer segmentation/profile, anomaly detection/details and automatic insights.
- **Eleven chat cases passed** with local `qwen3:4b` available. Three turns used live model planning (country rankings, country chart, missing age); the other standard tools/follow-ups used deterministic execution. Eight numerical results matched separately executed reference SQL, both chart requests returned figures, and the unavailable-age question returned clarification with no SQL, value or verified-calculation badge.
- The final run also applied a France filter, previewed duplicate removal without changing the active prepared view, applied the preview, verified that the filter survived, and downloaded the cleaned CSV successfully. The final process exited with code 0 and printed `All upgrade acceptance checks passed.`

| Chat acceptance case | Verified outcome |
|---|---|
| Top five countries by revenue | Ordered values matched independent DuckDB aggregation. |
| Exclude the United Kingdom | Exclusion retained the previous ranking and limit. |
| Show only three | Exclusion remained active and the result limit became three. |
| Show that as a chart | Reused the calculated result and retained execution provenance. |
| Revenue by month | All grouped monthly values matched reference SQL. |
| Ten best-selling products | Net units and product ordering matched reference SQL. |
| Top customers by revenue | Ten identifiable customers; no null-ID customer. |
| Compare France and Germany | Both calculated totals matched reference SQL. |
| Cancelled transaction count | Matched the actual count of cancellation rows. |
| Revenue by country as a bar chart | Validated SQL produced real results and a chart. |
| Customer age | Abstained and requested clarification against the available schema. |

In this final run, reference loading took 9.61 seconds, dashboard calculation 14.91 seconds, segmentation 2.22 seconds and anomaly detection 17.07 seconds. Deterministic chat turns took about 0.9–1.5 seconds; live model turns took 12.03–31.17 seconds with the model warm. Earlier cold/resource-constrained runs were much slower, so these observations are not throughput guarantees.

Local evidence files: `pytest-upgrade.log`, `acceptance-upgrade.log`, `upgrade_chat_verification.json`, `upgrade_verification.json` and screenshots under `docs/screenshots/`. They are generated evidence and excluded from public Git history. The older technical report and its 62-test/seven-chat results remain labeled as historical.

On 2026-09-28, after the interrupted session, the existing application and Ollama services were restarted without installation changes. The health endpoint returned `ok`; the browser loaded all 541,910 rows, five KPIs and six dashboard charts, then confirmed `Local AI connected` for `qwen3:4b`. The final browser console contained no warnings/errors. The delivered view is saved as `docs/screenshots/upgrade-dashboard.png`.

## Remaining limitations

- No hosted-provider credentials or hosting target were supplied. Remote HTTP behavior is covered by mocks; real remote generation and a public deployment have not been tested.
- Docker is not available on this machine, so the Dockerfile has not been built or run here. The production Waitress transport was tested directly on Windows; CI has been authored but has not run on GitHub.
- This is a single-process demonstration app with in-memory sessions, not an authenticated multitenant service. Sessions expire and disappear on restart; multiple replicas require shared state. Private deployments need an access-controlled host and TLS.
- Large uploads and ML jobs still consume memory and request threads. CPU Qwen inference can take over a minute. Query result caps, timeouts and session limits are present, but they are not a substitute for production capacity testing.
- SQL semantics require review. Quality scores, customer labels and anomaly flags are descriptive heuristics, not business guarantees, churn forecasts or fraud determinations.
- Durable saved analyses, natural-language cleaning, authentication, billing and job queues were not added as unsupported UI controls. These optional extensions remain future work.
