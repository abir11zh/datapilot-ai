from io import BytesIO
import threading
import pandas as pd
import pytest
import requests
from http.server import ThreadingHTTPServer
from app import Handler

@pytest.fixture
def server():
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{http.server_port}'
    http.shutdown();http.server_close();thread.join()

@pytest.fixture
def client():
    s=requests.Session();s.headers['X-DataPilot']='1'
    yield s
    s.close()

def test_upload_clean_query_and_isolation(server,client):
    r=client.post(server+'/api/upload?name=generic.csv',data=b'amount,category\n1,a\n1,a\n3,b\n')
    assert r.status_code==200 and r.json()['rows']==3
    assert requests.get(server+'/api/status').json()['loaded'] is False
    assert client.get(server+'/api/explorer').json()['duplicates']==1
    r=client.post(server+'/api/sql',json={'sql':'SELECT SUM(amount) AS total FROM sales'})
    assert r.json()['table']['rows'][0]['total']==5
    assert client.post(server+'/api/sql',json={'sql':'DROP TABLE sales'}).status_code==400
    r=client.post(server+'/api/clean',json={'remove_duplicates':True})
    assert r.json()['after_rows']==2
    assert client.get(server+'/api/status').json()['mode']=='cleaned'
    assert client.post(server+'/api/mode',json={'mode':'raw'}).json()['rows']==3
    assert client.get(server+'/api/download').text.count('1,a')==2
    r=client.post(server+'/api/segments',json={})
    assert r.status_code==400 and 'RFM requires' in r.json()['error']

def test_excel_sheets(server,client):
    data=BytesIO()
    with pd.ExcelWriter(data,engine='openpyxl') as writer:
        pd.DataFrame({'x':[1,2]}).to_excel(writer,sheet_name='First',index=False)
        pd.DataFrame({'y':[3,4,5]}).to_excel(writer,sheet_name='Second',index=False)
    r=client.post(server+'/api/upload?name=test.xlsx',data=data.getvalue())
    assert r.status_code==200 and r.json()['sheets']==['First','Second']
    r=client.post(server+'/api/sheet',json={'sheet':'Second'})
    assert r.json()['rows']==3

def test_origin_and_header_rejected(server):
    assert requests.post(server+'/api/clear',json={}).status_code==400
    assert requests.post(server+'/api/clear',json={},headers={'X-DataPilot':'1','Origin':'https://untrusted.example'}).status_code==400
    assert requests.get(server+'/api/status',headers={'Host':'untrusted.example'}).status_code==400

def test_frontend_assets(server):
    r=requests.get(server+'/')
    assert r.status_code==200 and 'DataPilot' in r.text
    assert requests.get(server+'/api/health').json()['status']=='ok'
    assert requests.get(server+'/../requirements.txt').status_code==404
