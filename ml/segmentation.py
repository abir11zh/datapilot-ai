import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


class SegmentationModel:
    def segment(self, rfm, n_clusters=4):
        features = ['Recency', 'Frequency', 'Monetary']
        if not set(features) <= set(rfm):
            raise ValueError('Calculate RFM before clustering customers.')
        if len(rfm) < 2:
            raise ValueError('Segmentation needs at least two customers.')
        x = rfm[features].astype(float)
        if not np.isfinite(x).all().all() or (x < 0).any().any():
            raise ValueError('RFM features must be finite and nonnegative.')
        k = min(max(2, int(n_clusters)), len(x), len(x.drop_duplicates()))
        if k < 2:
            raise ValueError('Customer profiles are identical; meaningful clustering is not possible.')
        scaled = StandardScaler().fit_transform(np.log1p(x))
        result = rfm.copy()
        result['Cluster'] = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(scaled)
        stats = result.groupby('Cluster')[features].mean()
        med = x.median()
        labels = {}
        reasons = {}
        for cluster, row in stats.iterrows():
            recent = row.Recency <= med.Recency
            frequent = row.Frequency > med.Frequency
            valuable = row.Monetary > med.Monetary
            if recent and frequent and valuable:
                label = 'VIP Customers'
            elif recent and frequent:
                label = 'Loyal Customers'
            elif not recent and (frequent or valuable):
                label = 'At Risk'
            elif not recent:
                label = 'Inactive Customers'
            else:
                label = 'Potential Customers'
            labels[cluster] = label
            reasons[cluster] = f"Recency {'<=' if recent else '>'} median; frequency {'>' if frequent else '<='} median; monetary {'>' if valuable else '<='} median."
        result['Segment'] = result.Cluster.map(labels)
        stats['Customers'] = result.groupby('Cluster').size()
        stats['Revenue'] = result.groupby('Cluster').Monetary.sum()
        stats['Segment'] = stats.index.map(labels)
        stats['Rationale'] = stats.index.map(reasons)
        return result, stats.reset_index()
