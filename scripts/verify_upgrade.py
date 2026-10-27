"""Full-workbook acceptance checks for the upgraded product. Requires local AI."""
import json
import os
from pathlib import Path
import time
import requests

ROOT=Path(__file__).resolve().parents[1]
s=requests.Session();s.headers['X-DataPilot']='1'
base=os.getenv('DATAPILOT_URL','http://127.0.0.1:8501')+'/api/'
evidence=[]
def call(path,payload=None):
    started=time.perf_counter()
    response=s.get(base+path,timeout=600) if payload is None else s.post(base+path,json=payload,timeout=600)
    response.raise_for_status()
    result=response.json()
    print(path,round(time.perf_counter()-started,2),'seconds',flush=True)
    return result

def ask(question,expected_sql=None):
    result=call('chat',{'question':question})
    item={'question':question,'answer':result['answer'],'sql':result.get('sql'),'verified':result.get('verified',False),'has_chart':bool(result.get('figure')), 'status':'checking', 'result_rows':result['table']['rows']}
    evidence.append(item)
    (ROOT/'docs/upgrade_chat_verification.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    if expected_sql:
        expected=call('sql',{'sql':expected_sql})['table']['rows']
        actual=result['table']['rows']
        assert len(actual)==len(expected),(question,'row count',len(actual),len(expected),result['answer'])
        # Compare ordered cells rather than model-selected output aliases.
        for a,b in zip(actual,expected):
            av,bv=list(a.values()),list(b.values())
            assert len(av)==len(bv),(question,av,bv)
            for x,y in zip(av,bv):
                if isinstance(x,(int,float)) and isinstance(y,(int,float)):
                    assert abs(x-y)<=max(.01,abs(y)*1e-9),(question,x,y)
                else: assert str(x)==str(y),(question,x,y)
        assert result.get('verified') and result['trace']['engine']=='DuckDB'
    if question.endswith('age?'):
        assert not result.get('verified') and not result['table']['rows'] and result.get('sql') is None
        # The planner can name a missing field or request clarification against
        # the available schema. Both must abstain from calculating an age.
        assert ('does not contain' in result['answer'] or 'Available sales columns:' in result['answer'])
    if 'bar chart' in question or question=='Show that as a chart.':
        assert result.get('figure')
    item['status']='passed'
    (ROOT/'docs/upgrade_chat_verification.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print('PASS:',question,flush=True)
    return result

status=call('reference',{'sheet':'Year 2010-2011'})
assert status['rows']==541910
call('dashboard');call('quality');call('profile?column=Revenue')
segments=call('segments',{'clusters':4})
call('customer?id='+str(segments['customers']['rows'][0]['CustomerID']))
anomalies=call('anomalies',{'contamination':.02})
call('anomaly-detail?row='+str(anomalies['anomalies']['rows'][0]['SourceRow']))
call('insights',{})
call('clear',{})
ask('What are the top 5 countries by revenue?','SELECT Country, SUM(Revenue) AS Revenue FROM sales GROUP BY Country ORDER BY Revenue DESC LIMIT 5')
ask('Exclude the United Kingdom.',"SELECT Country, SUM(Revenue) AS Revenue FROM sales WHERE Country <> 'United Kingdom' GROUP BY Country ORDER BY Revenue DESC LIMIT 5")
ask('Show only 3.',"SELECT Country, SUM(Revenue) AS Revenue FROM sales WHERE Country <> 'United Kingdom' GROUP BY Country ORDER BY Revenue DESC LIMIT 3")
assert ask('Show that as a chart.')['figure']
for question,sql in [
    ('Show revenue by month.',"SELECT DATE_TRUNC('month', InvoiceDate) AS Month, SUM(Revenue) AS Revenue FROM sales WHERE InvoiceDate IS NOT NULL GROUP BY 1 ORDER BY 1"),
    ('What are the 10 best-selling products?', 'SELECT Description, SUM(Quantity) AS Units FROM sales WHERE Description IS NOT NULL GROUP BY Description ORDER BY Units DESC LIMIT 10'),
    ('Who are the top customers by revenue?', 'SELECT CustomerID, SUM(Revenue) AS Revenue FROM sales WHERE CustomerID IS NOT NULL GROUP BY CustomerID ORDER BY Revenue DESC LIMIT 10'),
    ('Compare France and Germany.',"SELECT Country, SUM(Revenue) AS Revenue FROM sales WHERE Country IN ('France','Germany') GROUP BY Country ORDER BY Revenue DESC"),
    ('How many cancelled transactions are there?', 'SELECT COUNT(*) AS CancelledRows FROM sales WHERE IsCancelled = TRUE'),
    ('Show revenue by country as a bar chart.',None),
    ("What is the customer's age?",None),
]:
    call('clear',{})
    result=ask(question,sql)
call('filters',{'country':'France'})
p=call('clean-preview',{'remove_duplicates':True})
assert call('status')['mode']=='prepared'
call('clean-apply',{'token':p['token']})
assert call('status')['filters']=={'country':'France'}
assert call('status')['has_cleaned']
r=s.get(base+'download',timeout=600);r.raise_for_status();assert 'Revenue' in r.text.splitlines()[0]
print('All upgrade acceptance checks passed.',flush=True)
