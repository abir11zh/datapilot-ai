from io import BytesIO
import json
import pandas as pd
import pytest
from app import SESSIONS
from services.workspace_service import Workspace
from services.profile_service import column_profile
from services.data_cleaner import analyze_data_quality, prepare_data
from services.wsgi_service import create_application
from services.agent_service import AgentService
from ml.anomaly_detection import AnomalyDetector
from tests.test_agent import FakeLLM, plan
from pages.dashboard import show_dashboard


def test_cleaning_preview_is_non_destructive_and_stale_tokens_fail():
    w=Workspace();w.load(b'amount,kind\n1,a\n1,a\n,b\n','test.csv')
    p=w.preview_cleaning({'remove_duplicates':True})
    assert p['report']['after_rows']==2 and w.cleaned is None and len(w.active())==3
    w.filters={'country':'France'}
    w.apply_cleaning(p['token'])
    assert len(w.raw)==3 and len(w.cleaned)==2 and w.filters=={'country':'France'}
    with pytest.raises(ValueError,match='expired'):w.apply_cleaning(p['token'])
    p=w.preview_cleaning({});w.load(b'x\n1\n','new.csv')
    with pytest.raises(ValueError,match='expired'):w.apply_cleaning(p['token'])


def test_column_profiles_full_population():
    df=pd.DataFrame({'amount':range(5000),'group':['a']*4999+['b'],'date':pd.date_range('2024-01-01',periods=5000)})
    p=column_profile(df,'amount')
    assert p['metrics']['Mean']==2499.5 and p['distribution'].Count.sum()==5000
    assert column_profile(df,'group')['distribution'].Count.sum()==5000
    assert column_profile(df,'date')['metrics']['Latest']==df.date.max()


def test_generic_text_revenue_does_not_break_dashboard_or_insights():
    w=Workspace();w.load(b'Revenue,amount,category\nunknown,10,a\nwaiting,20,b\n','generic.csv')
    result=show_dashboard(w)
    assert result['metrics']=={'Rows':2,'Columns':3}
    assert any(a['title']=='amount statistics' for a in result['analyses'])
    assert w.raw.Revenue.tolist()==['unknown','waiting']


def test_quality_score_and_examples():
    raw=pd.DataFrame({'InvoiceNo':['1','1','C2','3'],'Quantity':['2','2','-1','bad'],'UnitPrice':[5,5,0,-2],'InvoiceDate':['2024-01-01','2024-01-01','bad',None]})
    d=analyze_data_quality(raw)
    assert d['issues']['Duplicate rows']==1 and d['issues']['Malformed dates']==1
    assert d['issues']['Negative prices']==1 and d['issues']['Cancelled invoices (rows)']==1
    expected=100*((1-1/16)+(1-1/4)+(1-2/16))/3
    assert d['score']==round(expected,1)
    assert len(d['samples']['Invalid types / dates'])==2


def test_anomaly_distribution_and_explanation(retail):
    df=prepare_data(retail)
    result=AnomalyDetector().detect(df)
    assert result['distribution'].Count.sum()==result['rows_checked']
    row=int(result['anomalies'].iloc[0].SourceRow)
    explanation=AnomalyDetector.explain(result,row)
    assert explanation['comparison'].iloc[0]['Population mean']==df.Quantity.mean()
    assert len(explanation['transaction'])==1


def test_trace_only_after_execution_and_limited_followup(retail):
    llm=FakeLLM([plan('SELECT Country, SUM(Revenue) AS Revenue FROM sales GROUP BY Country ORDER BY Revenue DESC LIMIT 5')])
    a=AgentService(prepare_data(retail),llm=llm)
    try:
        d=a.ask('top countries')
        assert d['verified'] and d['trace']['engine']=='DuckDB' and d['trace']['active_rows']==len(retail)
        limited=a.ask('Show only 3.')
        assert limited['sql'].endswith('LIMIT 3')
        chart=a.ask('Show that as a chart')
        assert chart['trace']['engine']=='DuckDB' and chart['source_sql']==limited['sql']
    finally:a.close()


def test_customer_ranking_excludes_missing_identity(retail):
    df=prepare_data(retail)
    row=df.iloc[[0]].copy();row['CustomerID']=None;row['Revenue']=1e9
    a=AgentService(pd.concat([df,row],ignore_index=True),llm=FakeLLM([]))
    try:
        ranked=a.ask('Who are the top customers by revenue?')
        assert len(ranked['table'])==10 and ranked['table'].CustomerID.notna().all()
        assert ranked['table'].Revenue.max()<1e9
        count=a.ask('How many cancelled transactions are there?')
        assert count['table'].iloc[0,0]==0
    finally:a.close()
    a=AgentService(retail,llm=FakeLLM(['bad']*3))
    try:assert not a.ask('an unknown question').get('verified')
    finally:a.close()


def test_deterministic_exclusion_preserves_prior_filters_and_limit(retail):
    sql='SELECT Country, SUM(Revenue) AS Revenue FROM sales WHERE Quantity > 2 GROUP BY Country ORDER BY Revenue DESC LIMIT 5'
    a=AgentService(prepare_data(retail),llm=FakeLLM([plan(sql)]))
    try:
        a.ask('top countries for orders with quantities over two')
        excluded=a.ask('Exclude the UK.')
        expected=prepare_data(retail).query("Country == 'France' and Quantity > 2").Revenue.sum()
        assert excluded['table'].Country.tolist()==['France'] and excluded['table'].Revenue.iloc[0]==expected
        assert 'Quantity > 2' in excluded['sql'] and excluded['sql'].endswith('LIMIT 5')
        a.ask('Show that as a chart')
        assert a.ask('Show only 3')['sql'].endswith('LIMIT 3')
        assert len(a.llm.calls)==1
    finally:a.close()


@pytest.mark.parametrize('product_column', ['Description', 'StockCode'])
def test_best_sellers_rank_net_units_instead_of_price(product_column):
    df=pd.DataFrame({product_column:['volume','premium','volume',None], 'Quantity':[30,1,-2,1000], 'UnitPrice':[1,100,1,1]})
    a=AgentService(prepare_data(df),llm=FakeLLM([]))
    try:
        ranked=a.ask('What are the 1 best-selling products?')
        assert ranked['table'].to_dict('records')==[{product_column:'volume','Units':28}]
        assert ranked['verified'] and ranked['visualization']=='bar' and not a.llm.calls
    finally:a.close()


def test_cloud_wsgi_no_reference_or_ai_credentials(monkeypatch,tmp_path):
    import app
    monkeypatch.setenv('APP_MODE','cloud');monkeypatch.setenv('PUBLIC_URL','https://demo.example')
    monkeypatch.setenv('LLM_PROVIDER','remote')
    for key in ['REMOTE_LLM_BASE_URL','REMOTE_LLM_MODEL','REMOTE_LLM_API_KEY']:
        monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(app,'REFERENCE',tmp_path/'absent.xlsx')
    SESSIONS.clear()
    application=create_application(8501)
    cookie=''
    def call(path,body=None,host='demo.example',origin='https://demo.example'):
        nonlocal cookie
        raw=body if isinstance(body,bytes) else json.dumps(body).encode() if body is not None else b''
        route,_,query=path.partition('?')
        env={'REQUEST_METHOD':'POST' if body is not None else 'GET','PATH_INFO':route,'QUERY_STRING':query,'HTTP_HOST':host,'HTTP_ORIGIN':origin,'HTTP_X_DATAPILOT':'1','HTTP_COOKIE':cookie,'CONTENT_LENGTH':str(len(raw)),'wsgi.input':BytesIO(raw)}
        meta={}
        def start(status,headers):
            nonlocal cookie
            meta.update(status=status,headers=dict(headers))
            if 'Set-Cookie' in meta['headers']:cookie=meta['headers']['Set-Cookie'].split(';')[0]
        result=b''.join(application(env,start))
        return meta,json.loads(result)
    _,public=call('/api/config')
    assert public['mode']=='cloud' and public['reference_available'] is False
    assert call('/api/provider')[1]['available'] is False
    meta,loaded=call('/api/upload?name=demo.csv',b'amount,category\n1,a\n2,b\n')
    assert loaded['rows']==2 and 'Secure' in meta['headers']['Set-Cookie']
    assert call('/api/explorer')[1]['rows']==2
    assert call('/api/sql',{'sql':'SELECT SUM(amount) AS Total FROM sales'})[1]['table']['rows'][0]['Total']==3
    assert call('/api/sql',{'sql':'DELETE FROM sales'})[0]['status'].startswith('400')
    assert call('/api/reference',{})[0]['status'].startswith('400')
    assert call('/api/status',host='evil.example')[0]['status'].startswith('400')
    assert call('/api/clear',{},origin='https://evil.example')[0]['status'].startswith('400')
    SESSIONS.clear()
