"""Repeatable HTTP acceptance check against a running local DataPilot server."""
import json
import os
import time
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
s=requests.Session()
s.headers['X-DataPilot']='1'
base=os.getenv('DATAPILOT_URL','http://127.0.0.1:8501')+'/api/'
checks={}
def call(path,payload=None):
    start=time.perf_counter()
    r=s.get(base+path,timeout=420) if payload is None else s.post(base+path,json=payload,timeout=420)
    r.raise_for_status()
    d=r.json()
    checks[path]={'seconds':round(time.perf_counter()-start,2),'ok':True}
    print(path,checks[path],flush=True)
    return d

status=call('reference',{'sheet':'Year 2010-2011'})
call('mode',{'mode':'raw'})
raw=call('explorer')
quality=call('quality')
call('mode',{'mode':'prepared'})
dashboard=call('dashboard')
insights=call('insights',{})
segments=call('segments',{'clusters':4})
anomalies=call('anomalies',{'contamination':.02})
assert raw['rows']==status['rows']
assert sum(r['Customers'] for r in segments['statistics']['rows'])==segments['customers']['total_rows']
assert anomalies['rows_checked']+anomalies['excluded_rows']==status['rows']
questions=['What are the top 5 countries by revenue?','Exclude the UK.','Show that as a chart.',"What is the customer's age?",'Which customers are at risk?','Compare France and Germany.','What was total revenue by month?']
chat=[]
for q in questions:
    result=call('chat',{'question':q})
    chat.append({'question':q,'answer':result['answer'],'sql':result.get('sql'),'table':result['table'],'has_chart':bool(result.get('figure'))})
(ROOT/'docs/chat_verification.json').write_text(json.dumps(chat,indent=2),encoding='utf-8')
assert chat[0]['table']['rows'],chat[0]['answer']
assert all(r.get('Country')!='United Kingdom' for r in chat[1]['table']['rows']),chat[1]
assert chat[2]['has_chart'],chat[2]
assert not chat[3]['table']['rows'] and 'does not contain' in chat[3]['answer'],chat[3]
assert chat[4]['sql'] and 'segments' in chat[4]['sql'],chat[4]
assert set(row['Country'] for row in chat[5]['table']['rows'])=={'France','Germany'},chat[5]
assert abs(sum(row['Revenue'] for row in chat[6]['table']['rows'])-dashboard['metrics']['Total Revenue']) < .01,chat[6]
cleaning=call('clean',{'remove_duplicates':True})
export=s.get(base+'download',timeout=420);export.raise_for_status()
(ROOT/'data/processed/online_retail_2010_2011_cleaned.csv').write_bytes(export.content)
report={'dataset':status,'raw_profile':raw,'quality':quality,'dashboard_metrics':dashboard['metrics'],
        'insight_count':len(insights['analyses']),'segmentation':{k:v for k,v in segments.items() if k!='customers'},
        'anomalies':{k:v for k,v in anomalies.items() if k!='anomalies'},'cleaning':cleaning,'chat':chat,'checks':checks}
(ROOT/'docs/reference_verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print('Verification report and cleaned dataset saved.',flush=True)
