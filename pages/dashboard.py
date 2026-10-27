import pandas as pd
from services.duckdb_service import DuckDBService


def show_dashboard(workspace):
    df = workspace.active()
    db = DuckDBService()
    db.register_dataframe(df)
    metrics = {'Rows': len(df), 'Columns': len(df.columns)}
    has_revenue = 'Revenue' in df and pd.api.types.is_numeric_dtype(df.Revenue)
    try:
        if has_revenue:
            metrics['Total Revenue'] = db.query('SELECT SUM(Revenue) AS value FROM sales').iloc[0, 0]
        if 'InvoiceNo' in df:
            metrics['Orders'] = int(df.InvoiceNo.nunique())
        for col, label in [('CustomerID', 'Customers'), ('StockCode', 'Products')]:
            if col in df:
                metrics[label] = int(df[col].nunique())
        if has_revenue and 'InvoiceNo' in df:
            metrics['Average Order Value'] = db.query('SELECT AVG(amount) AS value FROM (SELECT InvoiceNo, SUM(Revenue) AS amount FROM sales WHERE InvoiceNo IS NOT NULL GROUP BY InvoiceNo) AS orders').iloc[0, 0]
        return {'metrics': metrics, 'analyses': workspace.insights(),
                'note': 'All values use the active data view and filters. Revenue is signed; returns and cancellations remain unless removed in Data Quality. Orders include cancellation identifiers when retained. Currency is not inferred.'}
    finally:
        db.close()
