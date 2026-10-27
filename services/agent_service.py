import re
import logging
import pandas as pd
from services.sql_generator import SQLGenerator, QueryPlan
from services.llm_service import LLMService, LLMError
from services.duckdb_service import DuckDBService
from services.data_loader import inspect_dataset
from services.data_cleaner import analyze_data_quality
from services.insight_service import InsightService, result_facts
from services.chart_service import ChartService
from services.memory_service import MemoryService
from services.followup_service import exclude_country
from ml.rfm import RFMAnalyzer
from ml.segmentation import SegmentationModel
from ml.anomaly_detection import AnomalyDetector

log = logging.getLogger(__name__)


class AgentService:
    def __init__(self, df, memory=None, llm=None, segments=None, n_clusters=4):
        self.df = df
        self.n_clusters = n_clusters
        self.memory = memory or MemoryService()
        self.llm = llm or LLMService()
        self.db = DuckDBService()
        self.db.register_dataframe(df)
        if segments is not None:
            self.db.register_dataframe(segments, 'segments')

    def inspect_dataset(self):
        return inspect_dataset(self.df)

    def get_schema(self):
        return self.db.get_schema()

    def execute_sql(self, sql):
        result = self.db.execute_query(sql)
        result.attrs['engine'] = 'DuckDB'
        result.attrs['executed_sql'] = sql
        return result

    def create_chart(self, df, kind, x, y):
        return ChartService().create_chart(df, kind, x, y)

    def calculate_statistics(self):
        n = self.df.select_dtypes(include='number')
        return n.describe().reset_index() if len(n.columns) else pd.DataFrame()

    def find_insights(self):
        return InsightService().generate(self.df)

    def analyze_customers(self):
        return SegmentationModel().segment(RFMAnalyzer().analyze(self.df), self.n_clusters)

    def detect_anomalies(self):
        return AnomalyDetector().detect(self.df)

    def deterministic_plan(self, question):
        q = question.lower().strip().rstrip('?.!')
        exact = {'describe dataset': 'dataset_info', 'dataset info': 'dataset_info', 'show schema': 'dataset_info',
                 'show statistics': 'statistics', 'data quality': 'data_quality',
                 'generate insights': 'insights', 'analyze this dataset and tell me the most important trends': 'insights',
                 'segment customers': 'segmentation', 'detect anomalies': 'anomaly_detection'}
        if q in exact:
            return QueryPlan(action=exact[q])
        products = re.fullmatch(r'(?:what are |show |show me )?(?:the )?(?:top )?(?:(\d+) )?best[- ]selling products', q)
        product_column = next((c for c in ('Description', 'StockCode') if c in self.df), None)
        if products and product_column and 'Quantity' in self.df and pd.api.types.is_numeric_dtype(self.df.Quantity):
            limit = min(1000, max(1, int(products.group(1) or 10)))
            return QueryPlan(action='sql_query', sql=f'SELECT "{product_column}", SUM(Quantity) AS Units FROM sales WHERE "{product_column}" IS NOT NULL GROUP BY "{product_column}" ORDER BY Units DESC LIMIT {limit}', visualization='bar', x=product_column, y='Units')
        if re.fullmatch(r'(?:who are |show |show me )?(?:the )?top customers by revenue', q) and {'CustomerID', 'Revenue'} <= set(self.df):
            return QueryPlan(action='sql_query', sql='SELECT CustomerID, SUM(Revenue) AS Revenue FROM sales WHERE CustomerID IS NOT NULL GROUP BY CustomerID ORDER BY Revenue DESC LIMIT 10', visualization='bar', x='CustomerID', y='Revenue')
        if q == 'how many cancelled transactions are there' and 'IsCancelled' in self.df:
            return QueryPlan(action='sql_query', sql='SELECT COUNT(*) AS CancelledRows FROM sales WHERE IsCancelled = TRUE')
        if re.fullmatch(r'(?:what was |what is |show |show me )?(?:total )?(?:revenue by month|monthly revenue)', q) and {'InvoiceDate', 'Revenue'} <= set(self.df):
            return QueryPlan(action='sql_query', sql="SELECT DATE_TRUNC('month', InvoiceDate) AS RevenueMonth, SUM(Revenue) AS Revenue FROM sales WHERE InvoiceDate IS NOT NULL GROUP BY 1 ORDER BY 1", visualization='line', x='RevenueMonth', y='Revenue')
        if re.fullmatch(r'compare (?:sales (?:in |for )?|revenue (?:in |for )?)?france and germany', q) and {'Country', 'Revenue'} <= set(self.df):
            return QueryPlan(action='sql_query', sql="SELECT Country, SUM(Revenue) AS Revenue FROM sales WHERE Country IN ('France', 'Germany') GROUP BY Country ORDER BY Revenue DESC", visualization='bar', x='Country', y='Revenue')
        segment = re.fullmatch(r'(?:which|show)(?: me)? customers (?:are |seem )?(at risk|inactive|loyal|vip)', q)
        if segment and 'segments' in self.db.tables:
            label = {'at risk': 'At Risk', 'inactive': 'Inactive Customers', 'loyal': 'Loyal Customers', 'vip': 'VIP Customers'}[segment.group(1)]
            return QueryPlan(action='sql_query', sql=f"SELECT CustomerID, Recency, Frequency, Monetary, Segment FROM segments WHERE Segment = '{label}' ORDER BY Monetary DESC LIMIT 100")
        if re.fullmatch(r'how much revenue comes from loyal customers', q) and 'segments' in self.db.tables:
            return QueryPlan(action='sql_query', sql="SELECT Segment, COUNT(*) AS Customers, SUM(Monetary) AS Revenue FROM segments WHERE Segment = 'Loyal Customers' GROUP BY Segment")
        if q == 'compare vip and regular customers' and 'segments' in self.db.tables:
            return QueryPlan(action='sql_query', sql="SELECT CASE WHEN Segment = 'VIP Customers' THEN 'VIP Customers' ELSE 'Other customers (non-VIP)' END AS CustomerGroup, COUNT(*) AS Customers, SUM(Monetary) AS Revenue, AVG(Recency) AS AverageRecency FROM segments GROUP BY 1", visualization='bar', x='CustomerGroup', y='Revenue')
        previous = self.memory.last_plan
        previous_sql = previous.sql if previous else None
        if not previous_sql and self.memory.last_result is not None:
            previous_sql = self.memory.last_result.attrs.get('executed_sql')
        exclusion = re.fullmatch(r'exclude (?:the )?(.+)', q)
        if exclusion and previous_sql and 'Country' in self.df and self.memory.last_result is not None and 'Country' in self.memory.last_result:
            wanted = exclusion.group(1)
            wanted = 'united kingdom' if wanted in {'uk', 'u.k.'} else wanted
            country = next((str(v) for v in self.df.Country.dropna().unique() if str(v).casefold() == wanted.casefold()), None)
            if country:
                revised = exclude_country(previous_sql, country)
                if revised:
                    return QueryPlan(action='sql_query', sql=revised, visualization=previous.visualization, x=previous.x, y=previous.y)
        if re.fullmatch(r'(show|display) (that|it)( as a)? (chart|bar chart|line chart|pie chart)', q) and self.memory.last_result is not None:
            kind = 'line' if 'line' in q else ('pie' if 'pie' in q else 'bar')
            old = self.memory.last_plan
            return QueryPlan(action='chart', visualization=kind, x=old.x, y=old.y)
        limited = re.fullmatch(r'(?:show )?only (\d+)', q)
        if limited and previous_sql:
            limit = min(1000, max(1, int(limited.group(1))))
            sql = previous_sql.strip().rstrip(';')
            sql = re.sub(r'\s+LIMIT\s+\d+\s*$', '', sql, flags=re.I)
            old = self.memory.last_plan
            return QueryPlan(action='sql_query', sql=sql + f' LIMIT {limit}', visualization=old.visualization, x=old.x, y=old.y)
        return None

    def ask(self, question):
        if not question.strip() or len(question) > 4000:
            raise ValueError('Enter a question with at most 4,000 characters.')
        history = self.memory.get_all()
        self.memory.add('user', question)
        # Make segments available before planning customer/segment questions.
        if re.search(r'\b(segment|vip|loyal|at risk|inactive)\b', question, re.I) and 'segments' not in self.db.tables:
            try:
                segments, _ = self.analyze_customers()
                self.db.register_dataframe(segments, 'segments')
            except ValueError as exc:
                return self._answer(str(exc))
        plan = self.deterministic_plan(question)
        error = None
        for attempt in range(3):  # Initial plan plus at most two corrections, including SQL execution errors.
            try:
                if plan is None:
                    plan = SQLGenerator().generate(question, self.get_schema(), history, self.llm, error)
                return self.dispatch(plan)
            except LLMError as exc:
                return self._answer(str(exc) + ' You can still use the dashboard, quality tools, insights, and SQL workspace.')
            except Exception as exc:
                log.warning('Analysis planning failed; attempt=%s error_type=%s', attempt + 1, type(exc).__name__)
                error = f'{type(exc).__name__}: {exc}'
                if plan and plan.sql:
                    error += ' Previous SQL: ' + plan.sql
                plan = None
        return self._answer('The request could not be safely resolved after two corrections. Check column names or rephrase. No unverified answer was produced.')

    def _answer(self, answer, table=None, plan=None, extra=None):
        self.memory.add('assistant', answer, generated_sql=plan.sql if plan else None,
                        result_summary=answer[:2000], visualization=plan.visualization if plan else None)
        return {'answer': answer, 'table': table if table is not None else pd.DataFrame(),
                'sql': plan.sql if plan else None, 'visualization': plan.visualization if plan else None,
                'x': plan.x if plan else None, 'y': plan.y if plan else None, **(extra or {})}

    def dispatch(self, plan):
        extra = {}
        if plan.action == 'clarification':
            # Do not display unverified LLM prose as a data answer.
            missing = [c for c in plan.missing_columns if c not in self.df.columns]
            if missing:
                return self._answer('The dataset does not contain the requested columns: ' + ', '.join(missing) + '. No values can be calculated for them.')
            return self._answer('Please specify the available column and the analysis you need. Available sales columns: ' + ', '.join(self.df.columns) + '. The dataset may not contain the requested information.')
        if plan.action == 'dataset_info':
            table = self.inspect_dataset()['schema']
        elif plan.action == 'statistics':
            table = self.calculate_statistics()
        elif plan.action == 'data_quality':
            table = pd.DataFrame(list(analyze_data_quality(self.df)['issues'].items()), columns=['Issue', 'Count'])
        elif plan.action == 'insights':
            analyses = self.find_insights()
            facts = [a['title'] + ': ' + ' '.join(a['facts']) for a in analyses]
            answer = ' '.join(facts[:5])
            if self.llm.check_connection()['available']:
                try:
                    answer = self.llm.summarize_facts(facts)
                except (LLMError, ValueError):
                    log.warning('Insight selection unavailable; retaining calculated facts')
            return self._answer(answer, extra={'analyses': analyses, 'verified': True,
                                'trace': {'engine': 'DuckDB', 'action': 'insights', 'active_rows': len(self.df)},
                                'findings': facts[:5]})
        elif plan.action == 'segmentation':
            customers, table = self.analyze_customers()
            self.db.register_dataframe(customers, 'segments')
        elif plan.action == 'anomaly_detection':
            data = self.detect_anomalies()
            table = data['anomalies'].head(1000)
            extra['note'] = 'Potential unusual transactions. Statistical anomalies do not establish fraud.'
        elif plan.action == 'chart' and not plan.sql:
            if self.memory.last_result is None:
                return self._answer('Run an analysis first, then ask to chart it.')
            table = self.memory.last_result
        else:
            if not plan.sql:
                raise ValueError('A query is required for this action.')
            table = self.execute_sql(plan.sql)
        facts = result_facts(table)
        extra.update(verified=True, findings=facts,
                     trace={'engine': table.attrs.get('engine', 'Python'), 'action': plan.action,
                            'active_rows': len(self.df), 'returned_rows': len(table),
                            'output_columns': list(table.columns), 'truncated': bool(table.attrs.get('truncated'))})
        if plan.action == 'chart' and table.attrs.get('executed_sql'):
            extra['source_sql'] = table.attrs['executed_sql']
        answer = ' '.join(facts)
        if len(table) > 5:
            answer = f'Showing a summary of the first 5 of {len(table):,} returned rows. ' + answer
        if table.attrs.get('truncated'):
            answer += ' Result limited to 1,000 rows; aggregate or filter for complete comparisons.'
        if not plan.x and len(table.columns) >= 2:
            plan.x = str(table.columns[0]); plan.y = str(table.columns[-1])
        if not plan.visualization and len(table.columns) == 2 and len(table) > 1 and pd.api.types.is_numeric_dtype(table.iloc[:, -1]):
            plan.visualization = 'line' if pd.api.types.is_datetime64_any_dtype(table.iloc[:, 0]) else 'bar'
        self.memory.last_result = table
        self.memory.last_plan = plan
        return self._answer(answer, table, plan, extra)

    def close(self):
        self.db.close()
