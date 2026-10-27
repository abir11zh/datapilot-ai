import pandas as pd
from services.data_cleaner import prepare_data


class RFMAnalyzer:
    def analyze(self, df, reference_date=None):
        df = prepare_data(df)
        required = {'CustomerID', 'InvoiceNo', 'InvoiceDate', 'Revenue'}
        missing = required - set(df)
        if missing:
            raise ValueError('RFM requires: ' + ', '.join(sorted(missing)) + '. Upload customer transaction data.')
        mask = df.CustomerID.notna() & df.InvoiceNo.notna() & df.InvoiceDate.notna() & (df.Revenue > 0)
        if 'IsCancelled' in df:
            mask &= ~df.IsCancelled
        if 'Quantity' in df:
            mask &= df.Quantity > 0
        valid = df.loc[mask].copy()
        if valid.empty:
            raise ValueError('No valid positive customer purchases are available for RFM.')
        reference = pd.Timestamp(reference_date) if reference_date else valid.InvoiceDate.max().normalize() + pd.Timedelta(days=1)
        if reference < valid.InvoiceDate.max():
            raise ValueError('Reference date must follow the last purchase.')
        rfm = valid.groupby('CustomerID').agg(LastPurchase=('InvoiceDate', 'max'),
                                              Frequency=('InvoiceNo', 'nunique'), Monetary=('Revenue', 'sum'))
        rfm['Recency'] = (reference - rfm.LastPurchase).dt.days
        result = rfm.reset_index()[['CustomerID', 'Recency', 'Frequency', 'Monetary']]
        result.attrs['reference_date'] = reference.isoformat()
        result.attrs['eligible_rows'] = len(valid)
        result.attrs['excluded_rows'] = len(df) - len(valid)
        return result
