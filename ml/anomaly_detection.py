import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from services.profile_service import histogram


class AnomalyDetector:
    def detect(self, df, contamination=.02, features=None):
        if not 0 < float(contamination) <= .5:
            raise ValueError('Contamination must be greater than zero and at most 0.5.')
        features = features or [c for c in ['Quantity', 'UnitPrice', 'Revenue'] if c in df and pd.api.types.is_numeric_dtype(df[c])]
        if not features:
            features = list(df.select_dtypes(include='number').columns[:8])
        if not features or not set(features) <= set(df):
            raise ValueError('Anomaly detection requires available numeric columns.')
        x = df[features].apply(pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan)
        keep = x.notna().all(axis=1)
        x = x.loc[keep]
        if len(x) < 10:
            raise ValueError('Anomaly detection requires at least ten complete numeric rows.')
        model = IsolationForest(n_estimators=100, max_samples=min(2048, len(x)),
                                contamination=float(contamination), random_state=42, n_jobs=2)
        model.fit(x)
        # Preserve uploaded columns whose names overlap the generated outputs.
        renamed = {}
        used = set(df.columns)
        for column in ('SourceRow', 'AnomalyScore', 'IsAnomaly'):
            if column in used:
                name = column + ' (original)'
                while name in used:
                    name += '_'
                renamed[column] = name
                used.add(name)
        result = df.rename(columns=renamed).copy()
        result['AnomalyScore'] = np.nan
        result['IsAnomaly'] = pd.Series(pd.NA, index=df.index, dtype='boolean')
        result.loc[keep, 'AnomalyScore'] = -model.decision_function(x)
        result.loc[keep, 'IsAnomaly'] = model.predict(x) == -1
        unusual = result.loc[result.IsAnomaly.fillna(False)].copy()
        unusual.insert(0, 'SourceRow', np.flatnonzero(result.IsAnomaly.fillna(False).to_numpy()) + 1)
        return {'data': result, 'anomalies': unusual.sort_values('AnomalyScore', ascending=False),
                'count': int(result.IsAnomaly.sum()), 'rows_checked': len(x),
                'rate': float(result.IsAnomaly.sum() / len(x) * 100),
                'max_score': float(result.AnomalyScore.max()),
                'distribution': histogram(result.AnomalyScore),
                'excluded_rows': int((~keep).sum()), 'features': [renamed.get(c, c) for c in features]}

    @staticmethod
    def explain(analysis, source_row):
        df = analysis['data']
        position = int(source_row) - 1
        if not 0 <= position < len(df):
            raise ValueError('Select an available transaction.')
        row = df.iloc[position]
        comparisons = []
        scored = df.loc[df.AnomalyScore.notna()]
        for column in analysis['features']:
            population = pd.to_numeric(scored[column], errors='coerce')
            value = pd.to_numeric(row[column], errors='coerce')
            comparisons.append({'Feature': column, 'Transaction value': value,
                                'Population median': population.median(), 'Population mean': population.mean(),
                                'Percent of scored rows at or below value': float((population <= value).mean() * 100) if pd.notna(value) else None})
        return {'transaction': df.iloc[[position]], 'comparison': pd.DataFrame(comparisons),
                'note': 'Comparisons use all scored active rows. These describe unusual values; they are not causal explanations of the model score.'}
