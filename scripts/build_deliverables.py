"""Build the reproducible EDA notebook and report from actual verification evidence."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
r=json.loads((ROOT/'docs/reference_verification.json').read_text(encoding='utf-8'))
cells=[]
def md(text):cells.append({'cell_type':'markdown','metadata':{},'source':text.splitlines(True)})
def code(source,text=None):
    cells.append({'cell_type':'code','metadata':{},'source':source.splitlines(True),'execution_count':sum(c['cell_type']=='code' for c in cells)+1,
                  'outputs':[] if text is None else [{'output_type':'stream','name':'stdout','text':str(text).splitlines(True)}]})
md('# DataPilot AI — Reference dataset exploration\n\nActual source: Online Retail II, Year 2010-2011. Original data is preserved. Recorded outputs below come from the application acceptance run; re-run cells to recalculate them. Installation is already complete.\n')
code("from pathlib import Path\nimport sys\nimport pandas as pd\nROOT = Path.cwd() if (Path.cwd() / 'services').exists() else Path.cwd().parent\nsys.path.insert(0, str(ROOT))\nfrom services.data_loader import DataLoader, inspect_dataset\nfrom services.data_cleaner import prepare_data, analyze_data_quality, DataCleaner, CleaningOptions\nfrom services.duckdb_service import DuckDBService\nfrom ml.rfm import RFMAnalyzer\nfrom ml.segmentation import SegmentationModel\nfrom ml.anomaly_detection import AnomalyDetector\npath = ROOT / 'data/raw/online_retail_II.xlsx'\nraw = DataLoader().load_file(path, sheet_name='Year 2010-2011')\n")
code('print(raw.shape)\nprint(raw.head())\n',str((r['raw_profile']['rows'],r['raw_profile']['columns']))+'\n'+json.dumps(r['raw_profile']['preview']['rows'][:5],indent=2))
code('raw.info()\n',r['raw_profile']['info'])
code('print(raw.describe())\n',json.dumps(r['raw_profile']['statistics'],indent=2))
code('print(raw.isnull().sum())\nprint("Duplicates:", raw.duplicated().sum())\n',json.dumps(r['quality']['missing'],indent=2)+'\nDuplicates: '+str(r['raw_profile']['duplicates']))
code('profile = inspect_dataset(raw)\nprint(profile["schema"].to_string(index=False))\nprint(profile["numeric_columns"], profile["categorical_columns"], profile["datetime_columns"])\n',json.dumps(r['raw_profile']['schema'],indent=2))
md('## Quality before cleaning\nMalformed values are reported. Cancellation and negative-value policies are explicit; missing customers are retained by default.')
code('report = analyze_data_quality(raw)\nprint(report["issues"])\nprint(report["conversions"])\n',json.dumps(r['quality'],indent=2))
md('## Feature engineering and DuckDB\nPrepared data retains all original rows. Revenue is signed. No currency is assumed by the generic application.')
code("prepared = prepare_data(raw)\ndb = DuckDBService()\ndb.register_dataframe(prepared)\nresult = db.execute_query('SELECT Country, SUM(Revenue) AS Revenue FROM sales GROUP BY Country ORDER BY Revenue DESC LIMIT 5')\nprint(result)\ndb.close()\n",json.dumps(r['chat'][0]['table'],indent=2))
md('## Explicit duplicate-only cleaning\nThis policy keeps returns, cancellations, zero-price rows, and missing IDs for review.')
code('cleaned, audit = DataCleaner().clean_with_report(raw, CleaningOptions(remove_duplicates=True))\nprint(audit)\ncleaned.to_csv(ROOT / "data/processed/online_retail_2010_2011_cleaned.csv", index=False)\n',json.dumps(r['cleaning'],indent=2))
md('## Customer analytics and unusual transactions\nRFM has its own documented eligibility rules. Cluster labels come from observed statistics, and anomalies are not fraud claims.')
code('rfm = RFMAnalyzer().analyze(prepared)\ncustomers, stats = SegmentationModel().segment(rfm)\nprint(stats)\n',json.dumps(r['segmentation'],indent=2))
code('anomalies = AnomalyDetector().detect(prepared)\nprint({k:v for k,v in anomalies.items() if k not in {"data", "anomalies"}})\n',json.dumps(r['anomalies'],indent=2))
nb={'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.11'}},'nbformat':4,'nbformat_minor':4}
(ROOT/'notebooks/eda.ipynb').write_text(json.dumps(nb,indent=2,ensure_ascii=False),encoding='utf-8')
metrics='\n'.join('- **'+k+'**: '+str(v) for k,v in r['dashboard_metrics'].items())
report=f"""# DataPilot AI — Technical report

## Delivered scope

The supplied 31-page `datapilot.pdf` was read in full. The user's explicit request superseded its installation/MVP stopping points and its Streamlit interface: all advanced modules are implemented with a separate web frontend. No second `datapilot(1).pdf` was present, so final comparison used the supplied `datapilot.pdf` and the user's expanded requirements.

The original scaffold was inspected first. Placeholder services/pages were completed in place. The existing sibling Python virtual environment was reused; only missing `xlrd` was installed. The original workbook remains unchanged.

## Architecture and numerical integrity

The browser calls a loopback HTTP API. Workspace sessions own raw/prepared/cleaned DataFrames, cached analyses, and bounded conversation memory. Pages are Python presenters; services are UI-independent. Pandas performs preparation and profiling; all generated SQL is validated before DuckDB execution; Plotly renders locally. Ollama receives actual schema and bounded history. Pydantic validates action plans. At most two correction attempts follow the initial plan.

The application renders numerical answers directly from calculated result cells. Ollama can prioritize verified insight facts by index; it cannot alter their numbers. Generated SQL is visible and should still be reviewed for semantic accuracy. Context changes clear prior results. No causal inference is claimed.

## Reference evidence

Source: Online Retail II, worksheet Year 2010-2011. Actual shape: **{r['raw_profile']['rows']:,} × {r['raw_profile']['columns']}**. Duplicate rows: **{r['raw_profile']['duplicates']:,}**. Missing cells: **{r['raw_profile']['missing']:,}**.

Prepared-view metrics (all source rows retained, signed revenue):

{metrics}

Duplicate-only cleaning retains **{r['cleaning']['after_rows']:,}** rows and removes **{r['cleaning']['removed_rows']:,}**. The export is `data/processed/online_retail_2010_2011_cleaned.csv`.

RFM: **{sum(row['Customers'] for row in r['segmentation']['statistics']['rows']):,}** eligible customers. Isolation Forest: **{r['anomalies']['count']:,}** potential unusual transactions among **{r['anomalies']['rows_checked']:,}** scored rows. These values describe this run and its configured policies, not constants embedded in the application.

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
| Automatic insights | insight_service.py, {r['insight_count']} calculated reference analyses |
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
"""
(ROOT/'docs/technical_report.md').write_text(report,encoding='utf-8')
print('EDA notebook and technical report created from calculated evidence.')
