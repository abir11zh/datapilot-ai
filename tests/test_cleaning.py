import pandas as pd
from services.data_cleaner import DataCleaner, CleaningOptions, prepare_data, analyze_data_quality
from services.data_loader import DataLoader, inspect_dataset

def test_features_and_original():
    raw=pd.DataFrame({'Invoice':['1','C2','3'], 'Price':['2','3','bad'], 'Quantity':['4','-2','0'],
                      'InvoiceDate':['2024-01-01','bad','2024-01-03'], 'Customer ID':[1,None,3]})
    old=raw.copy(deep=True)
    result=prepare_data(raw)
    pd.testing.assert_frame_equal(raw,old)
    assert result.Revenue.iloc[0]==8
    assert result.IsCancelled.tolist()==[False,True,False]
    assert pd.isna(result.InvoiceDate.iloc[1])
    assert set(['Year','Month','Day','Hour','DayOfWeek'])<=set(result)
    report=analyze_data_quality(raw)
    assert report['issues']['Malformed dates']==1
    assert report['issues']['Negative quantities']==1
    assert report['conversions']['Invalid values'].sum()>=2

def test_cleaning_policies():
    raw=pd.DataFrame({'InvoiceNo':['1','1','C2','3'], 'Quantity':[1,1,-1,0], 'UnitPrice':[2,2,2,0]})
    cleaned=DataCleaner().clean(raw)
    assert len(cleaned)==3
    assert cleaned.IsCancelled.sum()==1
    strict=DataCleaner().clean(raw,CleaningOptions(remove_cancelled=True,remove_nonpositive_quantity=True,remove_nonpositive_price=True))
    assert len(strict)==1 and strict.Revenue.sum()==2
    assert len(raw)==4

def test_generic_missing_preserved():
    raw=pd.DataFrame({'First Name':['Alice','Alice','Bob'],'Age':[25,25,None]})
    out=DataCleaner().clean(raw)
    assert len(out)==2 and out.Age.isna().sum()==1
    assert 'First Name' in out

def test_loading_csv_and_dates():
    raw=DataLoader().load_file(b'event_date,value\n2024-01-01,10\n2024-01-02,20\n','test.csv')
    out=prepare_data(raw)
    profile=inspect_dataset(out)
    assert profile['rows']==2 and profile['datetime_columns']==['event_date']

def test_manual_types():
    raw=pd.DataFrame({'amount':['1','bad'],'when':['2024-01-01','oops']})
    out=DataCleaner().clean(raw,numeric_columns=['amount'],date_columns=['when'])
    assert out.amount.isna().sum()==1 and out.when.isna().sum()==1
