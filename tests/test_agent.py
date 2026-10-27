import json
import pandas as pd
from services.agent_service import AgentService
from services.llm_service import LLMService, LLMError
from services.memory_service import MemoryService
from services.data_cleaner import prepare_data

class FakeLLM:
    parse_structured=staticmethod(LLMService.parse_structured)
    def __init__(self,responses): self.responses=iter(responses);self.calls=[]
    def chat(self,messages,schema=None):
        self.calls.append(messages)
        value=next(self.responses)
        if isinstance(value,Exception): raise value
        return value
    def check_connection(self): return {'available':False}

def plan(sql,**extra): return json.dumps(dict(action='sql_query',sql=sql,**extra))

def test_real_results_and_context(retail):
    llm=FakeLLM([plan('SELECT Country, SUM(Revenue) AS Revenue FROM sales GROUP BY Country ORDER BY Revenue DESC LIMIT 5',visualization='bar',x='Country',y='Revenue'),
                 plan("SELECT Country, SUM(Revenue) AS Revenue FROM sales WHERE Country <> 'United Kingdom' GROUP BY Country ORDER BY Revenue DESC LIMIT 5",visualization='bar',x='Country',y='Revenue')])
    a=AgentService(prepare_data(retail),llm=llm)
    try:
        first=a.ask('top five countries by revenue')
        assert first['table'].Revenue.sum()==prepare_data(retail).Revenue.sum()
        second=a.ask('Now exclude the UK from those results')
        assert second['table'].Country.tolist()==['France']
        assert 'generated_sql' in llm.calls[1][1]['content']
        chart=a.ask('Show that as a chart')
        pd.testing.assert_frame_equal(second['table'],chart['table'])
        assert len(llm.calls)==2
    finally:a.close()

def test_retry_bound(retail):
    llm=FakeLLM(['bad json']*3)
    a=AgentService(retail,llm=llm)
    try:
        r=a.ask('a question')
        assert 'two corrections' in r['answer'] and len(llm.calls)==3
    finally:a.close()

def test_sql_error_correction(retail):
    llm=FakeLLM([plan('SELECT Missing FROM sales'),plan('SELECT COUNT(*) AS n FROM sales')])
    a=AgentService(retail,llm=llm)
    try:
        r=a.ask('count rows')
        assert r['table'].iloc[0,0]==len(retail) and len(llm.calls)==2
    finally:a.close()

def test_no_ollama(retail):
    a=AgentService(retail,llm=FakeLLM([LLMError('Offline')]))
    try:
        assert 'Offline' in a.ask('what are sales')['answer']
        assert not a.ask('show statistics')['table'].empty
    finally:a.close()

def test_missing_information(retail):
    a=AgentService(retail,llm=FakeLLM([json.dumps({'action':'clarification','message':'Age is 99'})]))
    try:
        result=a.ask('customer age')
        assert '99' not in result['answer'] and 'may not contain' in result['answer']
    finally:a.close()


def test_month_alias_collision_and_segment_tools(retail):
    a=AgentService(prepare_data(retail),llm=FakeLLM([]))
    try:
        monthly=a.ask('What was total revenue by month?')
        assert monthly['table'].Revenue.sum()==prepare_data(retail).Revenue.sum()
        comparison=a.ask('Compare France and Germany.')
        assert comparison['table'].Country.tolist()==['France']
        risk=a.ask('Which customers are at risk?')
        assert 'segments' in risk['sql']
        assert all(risk['table'].Segment=='At Risk')
        groups=a.ask('Compare VIP and regular customers')
        assert groups['table'].Customers.sum()==20
    finally:a.close()


def test_agent_respects_selected_cluster_count(retail):
    a=AgentService(prepare_data(retail),llm=FakeLLM([]),n_clusters=3)
    try:
        customers, stats=a.analyze_customers()
        assert stats.shape[0]==3 and customers.Cluster.nunique()==3
    finally:a.close()
