from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd

ALIASES = {'Invoice': 'InvoiceNo', 'Price': 'UnitPrice', 'Customer ID': 'CustomerID'}


def prepare_data(raw, numeric_columns=(), date_columns=()):
    """Non-destructive feature copy. Coercions are recorded in the quality report."""
    df = raw.rename(columns={a: b for a, b in ALIASES.items() if b not in raw}).copy()
    unknown = (set(numeric_columns) | set(date_columns)) - set(df.columns)
    if unknown:
        raise ValueError('Conversion columns not found: ' + ', '.join(sorted(unknown)))
    for c in {'Quantity', 'UnitPrice', *numeric_columns} & set(df.columns):
        df[c] = pd.to_numeric(df[c], errors='coerce').replace([np.inf, -np.inf], np.nan)
    for c in {'InvoiceNo', 'StockCode', 'CustomerID'} & set(df.columns):
        df[c] = df[c].astype('string').str.replace(r'\.0$', '', regex=True).str.strip().replace('', pd.NA)
    inferred = {c for c in df if any(s in c.lower() for s in ('date', 'timestamp'))}
    for c in ({'InvoiceDate', *date_columns} | inferred) & set(df.columns):
        if pd.api.types.is_numeric_dtype(df[c]) and c in {'InvoiceDate', *date_columns}:
            df[c] = pd.NaT
        elif not pd.api.types.is_numeric_dtype(df[c]):
            parsed = pd.to_datetime(df[c], errors='coerce', format='mixed')
            if c in {'InvoiceDate', *date_columns} or parsed.notna().mean() >= .8:
                df[c] = parsed
    if 'InvoiceDate' in df and pd.api.types.is_datetime64_any_dtype(df.InvoiceDate):
        dt = df.InvoiceDate.dt
        for c, values in {'Year': dt.year, 'Month': dt.month, 'Day': dt.day,
                          'Hour': dt.hour, 'DayOfWeek': dt.day_name()}.items():
            df[c] = values
    if {'Quantity', 'UnitPrice'} <= set(df):
        df['Revenue'] = (df.Quantity * df.UnitPrice).replace([np.inf, -np.inf], np.nan)
    if 'InvoiceNo' in df:
        df['IsCancelled'] = df.InvoiceNo.str.upper().str.startswith('C').fillna(False)
    return df


def analyze_data_quality(raw, numeric_columns=(), date_columns=()):
    df = prepare_data(raw, numeric_columns, date_columns)
    original = raw.rename(columns={a: b for a, b in ALIASES.items() if b not in raw})
    issues = {'Duplicate rows': int(raw.duplicated().sum()), 'Missing cells': int(raw.isna().sum().sum())}
    conversions = []
    for c in original:
        lost = int((original[c].notna() & df[c].isna()).sum())
        if lost or str(original[c].dtype) != str(df[c].dtype):
            conversions.append({'Column': c, 'Before': str(original[c].dtype), 'After': str(df[c].dtype), 'Invalid values': lost})
    for c, label in [('Quantity', 'quantities'), ('UnitPrice', 'prices')]:
        if c in df:
            issues[f'Negative {label}'] = int((df[c] < 0).sum())
            issues[f'Zero {label}'] = int((df[c] == 0).sum())
    if 'InvoiceDate' in df:
        issues['Malformed dates'] = int((original.InvoiceDate.notna() & df.InvoiceDate.isna()).sum())
    if 'IsCancelled' in df:
        issues['Cancelled invoices (rows)'] = int(df.IsCancelled.sum())
    outliers = []
    for c in df.select_dtypes(include='number'):
        if c in {'Year', 'Month', 'Day', 'Hour'}:
            continue
        s = df[c].replace([np.inf, -np.inf], np.nan).dropna()
        if len(s):
            q1, q3 = s.quantile([.25, .75]); spread = q3 - q1
            outliers.append({'Column': c, 'IQR outliers': int(((s < q1-1.5*spread) | (s > q3+1.5*spread)).sum())})
    invalid = pd.Series(False, index=raw.index)
    invalid_cells = 0
    for c in original:
        lost = original[c].notna() & df[c].isna()
        invalid |= lost
        invalid_cells += int(lost.sum())
    masks = {'Missing values': raw.isna().any(axis=1), 'Duplicate rows': raw.duplicated(),
             'Invalid types / dates': invalid}
    for col, title in [('Quantity', 'Nonpositive quantities'), ('UnitPrice', 'Nonpositive prices')]:
        if col in df:
            masks[title] = df[col] <= 0
    if 'IsCancelled' in df:
        masks['Cancelled invoice rows'] = df.IsCancelled
    explanations = {'Missing values': 'Rows with at least one missing original value.',
                    'Duplicate rows': 'Exact repeated rows, excluding the first occurrence.',
                    'Invalid types / dates': 'Rows where preparation cannot convert an original nonmissing value.',
                    'Nonpositive quantities': 'Zero or negative quantities may represent returns or corrections.',
                    'Nonpositive prices': 'Zero or negative prices need business review.',
                    'Cancelled invoice rows': 'Invoice identifier begins with C; cancellations can be valid business records.'}
    dimensions = [{'Check': title, 'Affected rows': int(mask.sum()),
                   'Rate %': float(mask.mean() * 100) if len(raw) else 0,
                   'Status': 'Review' if mask.any() else 'Passed', 'Explanation': explanations[title]}
                  for title, mask in masks.items()]
    completeness = 1 - int(raw.isna().sum().sum()) / max(1, raw.size)
    uniqueness = 1 - int(raw.duplicated().sum()) / max(1, len(raw))
    validity = 1 - invalid_cells / max(1, raw.size)
    score = round(100 * (completeness + uniqueness + validity) / 3, 1)
    return {'issues': issues, 'dimensions': pd.DataFrame(dimensions), 'score': score,
            'score_formula': '100 × mean(completeness, row uniqueness, conversion validity). Completeness = 1 − missing original cells / cells; uniqueness = 1 − duplicate rows / rows; validity = 1 − failed conversion cells / cells. Returns, cancellations and IQR outliers are review signals, not score penalties.',
            'samples': {title: raw.loc[mask].head(25) for title, mask in masks.items() if mask.any()},
            'missing': raw.isna().sum().rename_axis('Column').reset_index(name='Missing'),
            'conversions': pd.DataFrame(conversions), 'outliers': pd.DataFrame(outliers),
            'aliases': {a: b for a, b in ALIASES.items() if a in raw and b not in raw}}


@dataclass
class CleaningOptions:
    remove_duplicates: bool = True
    remove_cancelled: bool = False
    remove_nonpositive_quantity: bool = False
    remove_nonpositive_price: bool = False
    drop_missing_customer: bool = False
    drop_invalid_dates: bool = False
    missing_numeric: str = 'keep'


class DataCleaner:
    def remove_duplicates(self, df):
        return df.drop_duplicates().reset_index(drop=True)

    def clean(self, raw, options=None, numeric_columns=(), date_columns=()):
        options = options or CleaningOptions()
        if options.missing_numeric not in {'keep', 'median', 'zero'}:
            raise ValueError('Missing numeric policy must be keep, median, or zero.')
        source = raw.drop_duplicates() if options.remove_duplicates else raw
        df = prepare_data(source, numeric_columns, date_columns)
        keep = pd.Series(True, index=df.index)
        for enabled, col, predicate in [
            (options.remove_cancelled, 'IsCancelled', lambda x: ~x),
            (options.remove_nonpositive_quantity, 'Quantity', lambda x: x > 0),
            (options.remove_nonpositive_price, 'UnitPrice', lambda x: x > 0),
            (options.drop_missing_customer, 'CustomerID', lambda x: x.notna()),
            (options.drop_invalid_dates, 'InvoiceDate', lambda x: x.notna()),
        ]:
            if enabled and col in df:
                keep &= predicate(df[col]).fillna(False)
        df = df.loc[keep].copy()
        if options.missing_numeric != 'keep':
            cols = df.select_dtypes(include='number').columns.difference(['Year', 'Month', 'Day', 'Hour', 'Revenue'])
            for c in cols:
                df[c] = df[c].fillna(0 if options.missing_numeric == 'zero' else df[c].median())
            df = prepare_data(df)
        return df.reset_index(drop=True)

    def clean_with_report(self, raw, options=None, **kwargs):
        options = options or CleaningOptions()
        cleaned = self.clean(raw, options, **kwargs)
        return cleaned, {'before_rows': len(raw), 'after_rows': len(cleaned),
                         'removed_rows': len(raw)-len(cleaned),
                         'before_missing': int(raw.isna().sum().sum()),
                         'after_missing': int(cleaned.isna().sum().sum()), 'options': asdict(options)}
