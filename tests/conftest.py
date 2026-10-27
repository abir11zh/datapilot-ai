import pandas as pd
import pytest

@pytest.fixture
def retail():
    rows=[]
    for customer in range(1,21):
        for order in range(1,customer%5+2):
            rows.append({'InvoiceNo':f'{customer}-{order}', 'StockCode':f'P{order}', 'Description':f'Product {order}',
                         'Quantity':order+1, 'UnitPrice':customer*2., 'CustomerID':str(customer),
                         'InvoiceDate':f'2024-01-{customer:02d}', 'Country':'France' if customer%2 else 'United Kingdom'})
    return pd.DataFrame(rows)
