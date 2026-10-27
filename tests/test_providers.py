"""Provider contracts run without credentials, external services, or model downloads."""
import json
import requests
import pytest
from services.config import Settings, load_env_file
from services.llm_service import LLMService, LLMError, OllamaProvider, RemoteProvider
from services.sql_generator import QueryPlan


class Response:
    def __init__(self, data): self.data = data
    def raise_for_status(self): pass
    def json(self): return self.data


def test_local_defaults_and_cloud_has_no_localhost_dependency(monkeypatch):
    for key in ['APP_MODE','LLM_PROVIDER','PUBLIC_URL','HOST','PORT']:
        monkeypatch.delenv(key, raising=False)
    local = Settings.from_env()
    assert local.provider == 'ollama' and local.ollama_model == 'qwen3:4b'
    monkeypatch.setenv('APP_MODE','cloud')
    cloud = Settings.from_env()
    assert cloud.provider == 'remote' and cloud.host == '0.0.0.0'
    assert cloud.provider_problem and cloud.public_settings()['mode'] == 'cloud'
    assert 'local' not in cloud.public_settings()['privacy_title'].lower()


@pytest.mark.parametrize('key,value', [('PORT','bad'),('PORT','70000'),('APP_MODE','invalid'),('PUBLIC_URL','https://user:password@example.com'),('PUBLIC_URL','https://example.com/path')])
def test_invalid_config_is_actionable(monkeypatch,key,value):
    monkeypatch.setenv(key,value)
    with pytest.raises(ValueError,match=key): Settings.from_env()


def test_explicit_env_file_does_not_execute_or_override(tmp_path,monkeypatch):
    path=tmp_path/'env'
    path.write_text('# example\nTEST_DP="$(do-not-execute)"\nPORT=9999\n',encoding='utf-8')
    monkeypatch.setenv('PORT','8501');monkeypatch.delenv('TEST_DP',raising=False)
    load_env_file(str(path))
    import os
    assert os.environ['PORT']=='8501' and os.environ['TEST_DP']=='$(do-not-execute)'
    monkeypatch.delenv('TEST_DP')


def test_remote_contract_and_local_validation(monkeypatch):
    settings=Settings(provider='remote',remote_url='https://provider.example/v1',remote_model='model',remote_key='private-test-secret')
    calls=[]
    monkeypatch.setattr(requests,'get',lambda *a,**kw: Response({'data':[{'id':'model'}]}))
    def post(url,**kwargs):
        calls.append((url,kwargs))
        return Response({'choices':[{'message':{'content':json.dumps({'action':'sql_query','sql':'SELECT COUNT(*) FROM sales'})}}]})
    monkeypatch.setattr(requests,'post',post)
    llm=LLMService(settings=settings)
    assert isinstance(llm.provider,RemoteProvider) and llm.health_check()['available']
    result=llm.structured_chat([{'role':'user','content':'count rows'}],QueryPlan)
    assert result.action=='sql_query'
    url,payload=calls[0]
    assert url.endswith('/v1/chat/completions') and payload['json']['response_format']['type']=='json_object'
    assert payload['headers']['Authorization']=='Bearer private-test-secret'
    assert payload['allow_redirects'] is False
    assert 'private-test-secret' not in repr(settings)+json.dumps(settings.public_settings())+json.dumps(llm.metadata())


def test_missing_config_and_failure_never_fallback(monkeypatch,caplog):
    calls=[]
    def fail(*args,**kwargs):
        calls.append(args[0]);raise requests.ConnectionError('secret-key-in-upstream-error')
    monkeypatch.setattr(requests,'post',fail);monkeypatch.setattr(requests,'get',fail)
    missing=LLMService(settings=Settings(provider='remote'))
    assert missing.health_check()['available'] is False and calls==[]
    with pytest.raises(LLMError):missing.chat([])
    remote=LLMService(settings=Settings(provider='remote',remote_url='https://provider.example/v1',remote_model='m',remote_key='secret'))
    assert remote.health_check()['available'] is False
    with pytest.raises(LLMError) as exc:remote.chat([])
    assert all(url.startswith('https://provider.example/') for url in calls)
    assert 'secret-key' not in str(exc.value)+caplog.text


def test_ollama_contract_and_missing_model(monkeypatch):
    monkeypatch.setattr(requests,'get',lambda *a,**kw:Response({'models':[{'name':'another-model'}]}))
    captured=[]
    def post(*args,**kw):captured.append(kw);return Response({'message':{'content':'{"action":"statistics"}'}})
    monkeypatch.setattr(requests,'post',post)
    llm=LLMService(settings=Settings())
    assert isinstance(llm.provider,OllamaProvider)
    assert llm.health_check()['connected'] and not llm.health_check()['available']
    assert llm.structured_chat([],QueryPlan).action=='statistics'
    assert captured[0]['json']['stream'] is False and isinstance(captured[0]['json']['format'],dict)


def test_remote_insecure_url_and_unknown_provider_stay_offline():
    for settings in [Settings(provider='unknown'),Settings(provider='disabled'),Settings(provider='remote',remote_url='http://example.com/v1',remote_model='x',remote_key='key')]:
        llm=LLMService(settings=settings)
        assert llm.health_check()['available'] is False
        with pytest.raises(LLMError):llm.chat([])
