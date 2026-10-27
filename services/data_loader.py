"""File ingestion and calculated dataset profiles."""
from io import BytesIO, StringIO
from pathlib import Path
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype

class DataLoader:
    def load_csv(self, source):
        return pd.read_csv(source, low_memory=False)

    def load_excel(self, source, sheet_name=0):
        return pd.read_excel(source, sheet_name=sheet_name)

    def load_file(self, source, filename=None, sheet_name=0):
        suffix = Path(filename or str(source)).suffix.lower()
        if isinstance(source, bytes):
            source = BytesIO(source)
        if suffix == '.csv':
            df = self.load_csv(source)
        elif suffix in {'.xlsx', '.xls'}:
            df = self.load_excel(source, sheet_name)
        else:
            raise ValueError('Upload a CSV, XLSX, or XLS file.')
        if df.empty or not len(df.columns):
            raise ValueError('The file contains no data rows.')
        names = [str(c).strip() for c in df.columns]
        if len(set(n.casefold() for n in names)) != len(names):
            raise ValueError('Column names must be unique, including case.')
        df.columns = names
        return df


def inspect_dataset(df):
    info = StringIO()
    df.info(buf=info)
    numeric = [c for c in df if is_numeric_dtype(df[c])]
    dates = [c for c in df if is_datetime64_any_dtype(df[c])]
    categorical = [c for c in df if c not in numeric + dates]
    columns = pd.DataFrame([{
        'Column': c, 'Type': str(df[c].dtype), 'Missing': int(df[c].isna().sum()),
        'Missing %': float(df[c].isna().mean() * 100) if len(df) else 0,
        'Unique': int(df[c].nunique()),
        'Examples': ', '.join(df[c].dropna().astype(str).drop_duplicates().head(5)),
    } for c in df])
    return {
        'rows': len(df), 'columns': len(df.columns),
        'missing': int(df.isna().sum().sum()), 'duplicates': int(df.duplicated().sum()),
        'memory_mb': float(df.memory_usage(deep=True).sum() / 1024**2),
        'numeric_columns': numeric, 'categorical_columns': categorical, 'datetime_columns': dates,
        'schema': columns, 'info': info.getvalue(), 'preview': df.head(100),
        'statistics': df[numeric].describe().reset_index() if numeric else pd.DataFrame(),
        'categorical': df[categorical].astype('string').describe().reset_index() if categorical else pd.DataFrame(),
        'countries': int(df.Country.nunique()) if 'Country' in df else None,
        'customers': int(df.CustomerID.nunique()) if 'CustomerID' in df else None,
        'products': int(df.StockCode.nunique()) if 'StockCode' in df else None,
    }
