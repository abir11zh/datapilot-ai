# DataPilot AI — Technical report

This report records the original delivery and its 2026-09-23 verification. The subsequent interface, provider and hosting upgrade is documented in [upgrade_verification.md](upgrade_verification.md), which supersedes the original deployment and test-count descriptions below.

## Delivered scope

The supplied 31-page `datapilot.pdf` was read in full. The user's explicit request superseded its installation/MVP stopping points and its Streamlit interface: all advanced modules are implemented with a separate web frontend. No second `datapilot(1).pdf` was present, so final comparison used the supplied `datapilot.pdf` and the user's expanded requirements.

The original scaffold was inspected first. Placeholder services/pages were completed in place. The existing sibling Python virtual environment was reused; only missing `xlrd` was installed. The original workbook remains unchanged.

## Architecture and numerical integrity

The browser calls a loopback HTTP API. Workspace sessions own raw/prepared/cleaned DataFrames, cached analyses, and bounded conversation memory. Pages are Python presenters; services are UI-independent. Pandas performs preparation and profiling; all generated SQL is validated before DuckDB execution; Plotly renders locally. Ollama receives actual schema and bounded history. Pydantic validates action plans. At most two correction attempts follow the initial plan.

The application renders numerical answers directly from calculated result cells. Ollama can prioritize verified insight facts by index; it cannot alter their numbers. Generated SQL is visible and should still be reviewed for semantic accuracy. Context changes clear prior results. No causal inference is claimed.

## Reference evidence

Source: Online Retail II, worksheet Year 2010-2011. Actual shape: **541,910 × 8**. Duplicate rows: **5,268**. Missing cells: **136,534**.

Prepared-view metrics (all source rows retained, signed revenue):

- **Rows**: 541910
- **Columns**: 15
- **Total Revenue**: 9747765.933999237
- **Orders**: 25900
- **Customers**: 4372
- **Products**: 4070
- **Average Order Value**: 376.3616190733581

Duplicate-only cleaning retains **536,642** rows and removes **5,268**. The export is `data/processed/online_retail_2010_2011_cleaned.csv`.

RFM: **4,338** eligible customers. Isolation Forest: **10,838** potential unusual transactions among **541,910** scored rows. These values describe this run and its configured policies, not constants embedded in the application.

## ML definitions

Recency is days since last eligible purchase, measured one day after the latest valid purchase. Frequency counts distinct invoices. Monetary sums positive eligible purchase revenue. Missing IDs/dates, cancellations, and nonpositive purchases are excluded with counts reported. KMeans uses log1p, StandardScaler, a fixed seed, and explained mean-versus-median labels. Labels may repeat across clusters and are heuristic. Isolation Forest uses deterministic sampling and reports incomplete-feature exclusions.

## Requirement coverage

| Requirement | Implementation / evidence |
|---|---|
| CSV/Excel, sheet selection, complete EDA | data_loader.py, Dataset Explorer, eda.ipynb |
| Raw preservation, quality report, explicit cleaning | data_cleaner.py, Data Quality, export |
| Features and generic schema inference | prepare_data(), manual type controls |
| DuckDB and SQL before AI | duckdb_service.py, SQL workspace, SQL tests |
| Local Ollama and structured plans | llm_service.py, sql_generator.py, live acceptance queries |
| Read-only safety | sqlparse checks, function allowlist, restricted relations, external access disabled |
| Verified answers and Plotly charts | agent_service.py, evidence rendering, chart_service.py |
| Conversation and follow-ups | memory_service.py, live UK exclusion and chart follow-up |
| Automatic insights | insight_service.py, 14 calculated reference analyses |
| RFM, KMeans, business labels, segment chat | ml/, segments table and live agent query |
| Isolation Forest | anomaly_detection.py, real-workbook run |
| Adaptive dashboard and filters | dashboard.py and separate frontend |
| Tests, documentation, notebook, demo | tests/, README, docs/demo.md, notebook, verification JSON |

## Performance and operation

First XLSX parsing is expensive on this machine; later reference loads use a modification-keyed local Parquet cache. Session analytics are cached. SQL results are capped at 1,000 displayed rows and queries are interrupted after 15 seconds; full data is aggregated before truncation. Raw chart builders use the first 1,000 active rows and say so. Ollama summaries are bounded. The supplied workbook is over 500,000 rows and was exercised without truncating the analytical input.

## Security boundaries and limitations

A loopback-only server, same-origin checks, HttpOnly SameSite session cookies, text escaping, validated SQL, disabled external access, and bounded execution reduce local risks. This is not a public multitenant service. No authentication, durable chat database, deployment hardening, or semantic-SQL correctness guarantee is claimed. Uploaded files still require memory. SQL syntax support is deliberately conservative. Business currency, timezone, and refund conventions require user interpretation. Statistical anomalies are not fraud, and segment labels are not validated churn predictions.

## Verification artifacts

`reference_verification.json` contains actual profiles, quality counts, query results, generated SQL, and timings. `eda.ipynb` reproduces exploration and retains outputs from that evidence. `demo.md` provides a presentation walkthrough. Tests cover SQL rejection/allowance, non-destructive cleaning, generic data, RFM values, deterministic clustering/anomalies, mocked LLM corrections, actual aggregation, and conversation continuity.

## Final verification — 2026-09-23

- 62 pytest tests passed (15.95 seconds).
- Compilation, imports, and JavaScript syntax checks passed.
- All 11 EDA notebook code cells were executed against the original workbook; no error outputs.
- All seven live chat acceptance cases passed, including context retention, missing information, segment queries, and monthly totals.
- Final dashboard and segmentation were inspected in the browser with no console errors.
- Screenshots: `screenshots/dashboard.png` and `screenshots/segmentation.png`.
- Actual package versions and concise results are recorded in `final_verification.json`.
