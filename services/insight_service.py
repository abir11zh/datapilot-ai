import pandas as pd
from services.duckdb_service import DuckDBService


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def result_facts(df, limit=5):
    if df.empty:
        return ['No matching records were found.']
    facts = []
    for _, row in df.head(limit).iterrows():
        parts = []
        for c, value in row.items():
            if pd.isna(value):
                text = 'missing'
            elif isinstance(value, float):
                text = format(value, ',.4f').rstrip('0').rstrip('.')
            else:
                text = str(value)
            parts.append(f'{c}: {text}')
        facts.append('; '.join(parts) + '.')
    return facts


class InsightService:
    def generate(self, df):
        db = DuckDBService()
        db.register_dataframe(df)
        analyses = []
        cols = set(df)
        numeric_cols = set(df.select_dtypes(include='number').columns)
        product = 'Description' if 'Description' in cols else 'StockCode'
        def add(title, sql, kind='bar'):
            result = db.execute_query(sql)
            analyses.append({'title': title, 'sql': sql, 'table': result, 'kind': kind,
                             'x': result.columns[0], 'y': result.columns[-1],
                             'facts': result_facts(result, 2)})
        try:
            if 'Revenue' in numeric_cols:
                add('Total revenue', 'SELECT SUM(Revenue) AS Revenue FROM sales')
                for c, title in [('Country', 'Revenue by country'), (product, 'Highest-revenue products'), ('CustomerID', 'Top customers')]:
                    if c in cols:
                        add(title, f'SELECT {quote(c)}, SUM(Revenue) AS Revenue FROM sales WHERE {quote(c)} IS NOT NULL GROUP BY {quote(c)} ORDER BY Revenue DESC LIMIT 15')
                if 'InvoiceDate' in cols and pd.api.types.is_datetime64_any_dtype(df.InvoiceDate):
                    add('Revenue by month', "SELECT DATE_TRUNC('month', InvoiceDate) AS Month, SUM(Revenue) AS Revenue FROM sales WHERE InvoiceDate IS NOT NULL GROUP BY 1 ORDER BY 1", 'line')
                    add('Best month', "SELECT DATE_TRUNC('month', InvoiceDate) AS Month, SUM(Revenue) AS Revenue FROM sales WHERE InvoiceDate IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 1")
                if 'InvoiceNo' in cols:
                    add('Average basket', 'SELECT AVG(Basket) AS AverageOrderValue FROM (SELECT InvoiceNo, SUM(Revenue) AS Basket FROM sales WHERE InvoiceNo IS NOT NULL GROUP BY InvoiceNo) AS baskets')
            if {'CustomerID', 'InvoiceNo'} <= cols:
                add('Purchase frequency', 'SELECT CustomerID, COUNT(DISTINCT InvoiceNo) AS Orders FROM sales WHERE CustomerID IS NOT NULL GROUP BY CustomerID ORDER BY Orders DESC LIMIT 15')
            if product in cols and 'Quantity' in numeric_cols:
                add('Best-selling products', f'SELECT {quote(product)}, SUM(Quantity) AS Units FROM sales WHERE {quote(product)} IS NOT NULL GROUP BY {quote(product)} ORDER BY Units DESC LIMIT 15')
            if {product, 'IsCancelled'} <= cols and pd.api.types.is_bool_dtype(df.IsCancelled):
                add('Frequently cancelled products', f'SELECT {quote(product)}, COUNT(*) AS CancelledRows FROM sales WHERE IsCancelled = TRUE AND {quote(product)} IS NOT NULL GROUP BY {quote(product)} ORDER BY CancelledRows DESC LIMIT 15')
            if 'InvoiceNo' in cols:
                for col, title in [('DayOfWeek', 'Orders by weekday'), ('Hour', 'Orders by hour')]:
                    if col in cols:
                        add(title, f'SELECT {quote(col)}, COUNT(DISTINCT InvoiceNo) AS Orders FROM sales WHERE {quote(col)} IS NOT NULL GROUP BY 1 ORDER BY Orders DESC')
                        if 'Revenue' in numeric_cols:
                            add('Best ' + ('weekday' if col == 'DayOfWeek' else 'purchasing hour'), f'SELECT {quote(col)}, SUM(Revenue) AS Revenue FROM sales WHERE {quote(col)} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 1')
            if not analyses:
                numeric = list(df.select_dtypes(include='number').columns)
                for c in numeric[:6]:
                    add(f'{c} statistics', f'SELECT COUNT({quote(c)}) AS Valid, AVG({quote(c)}) AS Mean, MIN({quote(c)}) AS Minimum, MAX({quote(c)}) AS Maximum FROM sales')
                categorical = list(df.select_dtypes(include=['object', 'string', 'category']).columns)
                for c in categorical[:3]:
                    add(f'{c} distribution', f'SELECT {quote(c)}, COUNT(*) AS Records FROM sales GROUP BY 1 ORDER BY Records DESC LIMIT 12')
            return analyses
        finally:
            db.close()

    def summarize_dataset(self, df):
        return {'rows': len(df), 'columns': len(df.columns), 'null_values': int(df.isna().sum().sum()),
                'numeric_columns': df.select_dtypes(include='number').columns.tolist()}
