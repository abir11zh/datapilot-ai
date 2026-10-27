import pandas as pd
from services.workspace_service import Workspace
from services.chart_service import ChartService
from services.insight_service import InsightService
from app import serial

def test_cache_and_reset():
    w=Workspace();w.load(b'a,b\n1,x\n2,y\n','a.csv')
    w.memory.add('user','hi')
    assert w.profile() is w.profile()
    w.clean({})
    assert not w.memory.memory and len(w.raw)==2 and w.mode=='cleaned'

def test_charts_fail_soft():
    d=pd.DataFrame({'a':['x','y'],'b':[1,-2]})
    c=ChartService()
    assert c.create_chart(d,'pie','a','b') is None
    assert c.create_chart(d,'bar','missing','b') is None
    for kind in ['bar','line','scatter','histogram']:
        assert c.create_chart(d,kind,'a','b') is not None

def test_generic_insights():
    d=pd.DataFrame({'amount':[1,2,3],'category':['a','a','b']})
    a=InsightService().generate(d)
    assert a and a[0]['table'].Mean.iloc[0]==2

def test_serial_nonfinite():
    assert serial(float('nan')) is None


def test_selected_segments_and_upload_origin(retail):
    w=Workspace()
    w.load(retail.to_csv(index=False).encode(), 'online_retail_II.xlsx.csv')
    assert w.status()['source']=='upload'
    w.memory.add('user','prior context')
    selected=w.segments(3)
    assert selected['statistics'].shape[0]==3 and w.segment_k==3
    assert w.segments() is selected and w.memory.get_all()==[]
    assert w.status()['cluster_count']==3
