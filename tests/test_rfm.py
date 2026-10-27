import pandas as pd
import pytest
from ml.rfm import RFMAnalyzer
from ml.segmentation import SegmentationModel

def test_rfm_values():
    df=pd.DataFrame({'CustomerID':['1','1','1','2',None],'InvoiceNo':['A','A','C1','B','X'],
                     'InvoiceDate':['2024-01-01']*3+['2024-01-03']*2,'Revenue':[10,20,-10,40,500]})
    r=RFMAnalyzer().analyze(df).set_index('CustomerID')
    assert r.loc['1','Frequency']==1 and r.loc['1','Monetary']==30
    assert r.loc['1','Recency']==3 and r.loc['2','Recency']==1
    assert len(r)==2

def test_missing_columns():
    with pytest.raises(ValueError,match='RFM requires'):
        RFMAnalyzer().analyze(pd.DataFrame({'a':[1]}))

def test_deterministic_segments(retail):
    r=RFMAnalyzer().analyze(retail)
    a,s=SegmentationModel().segment(r)
    b,t=SegmentationModel().segment(r)
    pd.testing.assert_frame_equal(a,b)
    assert a.CustomerID.nunique()==20
    assert s.Customers.sum()==20 and s.Rationale.notna().all()

def test_identical_profiles():
    r=pd.DataFrame({'CustomerID':['a','b'],'Recency':[1,1],'Frequency':[1,1],'Monetary':[1,1]})
    with pytest.raises(ValueError,match='identical'):
        SegmentationModel().segment(r)
