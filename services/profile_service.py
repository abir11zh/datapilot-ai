"""Bounded, full-column summaries for the interactive profiler."""
import numpy as np
import pandas as pd


def histogram(series, bins=30):
    values = pd.to_numeric(series, errors='coerce').replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return pd.DataFrame(columns=['Range', 'Count'])
    counts, edges = np.histogram(values, bins=min(bins, max(1, values.nunique())))
    return pd.DataFrame({'Range': [f'{a:,.4g} – {b:,.4g}' for a, b in zip(edges[:-1], edges[1:])], 'Count': counts})


def column_profile(df, column):
    if column not in df:
        raise ValueError('Select an available column.')
    series = df[column]
    result = {'column': column, 'dtype': str(series.dtype), 'rows': len(series),
              'missing': int(series.isna().sum()), 'unique': int(series.nunique()),
              'missing_percent': float(series.isna().mean() * 100) if len(series) else 0}
    if pd.api.types.is_datetime64_any_dtype(series):
        counts = series.dropna().dt.to_period('M').astype(str).value_counts().sort_index()
        result.update(kind='date', metrics={'Earliest': series.min(), 'Latest': series.max()},
                      distribution=counts.rename_axis('Month').reset_index(name='Count'))
    elif pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        values = series.replace([np.inf, -np.inf], np.nan)
        result.update(kind='numeric', metrics={'Minimum': values.min(), 'Maximum': values.max(),
                                              'Mean': values.mean(), 'Median': values.median()},
                      distribution=histogram(values))
    else:
        counts = series.astype('string').fillna('(missing)').value_counts().head(20)
        result.update(kind='categorical', metrics={'Unique values': result['unique']},
                      distribution=counts.rename_axis('Value').reset_index(name='Count'))
    return result
