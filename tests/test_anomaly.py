import pandas as pd
import pytest
from ml.anomaly_detection import AnomalyDetector

def test_extreme_and_missing():
    df=pd.DataFrame({'Quantity':[1]*99+[100000,None],'UnitPrice':[2]*99+[100000,2]})
    a=AnomalyDetector().detect(df)
    b=AnomalyDetector().detect(df)
    assert a['excluded_rows']==1
    assert bool(a['data'].iloc[99].IsAnomaly)
    pd.testing.assert_frame_equal(a['data'],b['data'])
    assert 'AnomalyScore' not in df

def test_generic_numeric():
    d=AnomalyDetector().detect(pd.DataFrame({'score':list(range(30))}))
    assert d['rows_checked']==30 and d['features']==['score']


def test_uploaded_output_names_are_preserved():
    df=pd.DataFrame({'Revenue':['unknown']*30,'SourceRow':range(30),'AnomalyScore':list(range(29))+[1000],'IsAnomaly':['source']*30})
    result=AnomalyDetector().detect(df,features=['AnomalyScore'])
    assert result['data']['AnomalyScore (original)'].tolist()==df.AnomalyScore.tolist()
    assert result['data']['SourceRow (original)'].tolist()==df.SourceRow.tolist()
    assert result['data']['IsAnomaly (original)'].eq('source').all()
    row=int(result['anomalies'].iloc[0].SourceRow)
    explanation=AnomalyDetector.explain(result,row)
    assert explanation['comparison'].iloc[0]['Feature']=='AnomalyScore (original)'
    assert explanation['comparison'].iloc[0]['Population mean']==df.AnomalyScore.mean()
    assert list(df.columns)==['Revenue','SourceRow','AnomalyScore','IsAnomaly']


def test_insufficient():
    with pytest.raises(ValueError):
        AnomalyDetector().detect(pd.DataFrame({'x':[1,2]}))
