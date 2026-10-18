import json
from concurrent.futures import ThreadPoolExecutor
import pytest
import requests
from backend.services import llm_service as llm
from backend.services.quota_key_pool import QuotaAwareKeyPool


@pytest.fixture
def routed(monkeypatch):
    pools={p:QuotaAwareKeyPool([p+'-one',p+'-two'],provider=p) for p in ('gemini','groq','nvidia')}
    for p,pool in pools.items():monkeypatch.setattr(llm,p+'_key_pool',pool)
    monkeypatch.setattr(llm,'_model_cooldowns',{})
    return pools


def responses(monkeypatch,values):
    calls=[]
    def post(url,headers,json,timeout):
        calls.append(dict(url=url,model=json['model'],key=headers['Authorization']))
        value=values.pop(0)
        if isinstance(value,Exception):raise value
        status,content,finish=value
        r=requests.Response();r.status_code=status;r.url=url
        r._content=__import__('json').dumps({'choices':[{'message':{'content':content},'finish_reason':finish}]}).encode()
        return r
    monkeypatch.setattr(requests,'post',post)
    return calls


def test_task_order_is_not_overridden_by_legacy_default_and_gemini_is_monitored(monkeypatch,routed):
    calls=responses(monkeypatch,[(200,'Grounded explanation.','stop')])
    assert llm.invoke_llm('Computed evidence',task='trend')=='Grounded explanation.'
    assert calls[0]['model']=='gemini-3.5-flash-lite'
    assert 'generativelanguage.googleapis.com' in calls[0]['url']
    assert llm.key_pool_health()['gemini']['total_successes']==1
    assert llm.key_pool_health()['groq']['total_requests']==0


@pytest.mark.parametrize('failure',[(503,'Busy','stop'),(404,'Model missing','stop'),(200,'','stop'),(200,'Partial answer','length')])
def test_model_errors_switch_model_instead_of_exhausting_accounts(monkeypatch,routed,failure):
    calls=responses(monkeypatch,[failure,(200,'Fallback explanation','stop')])
    assert llm.invoke_llm('Explain evidence',task='trend')=='Fallback explanation'
    assert len(calls)==2 and calls[0]['model']!=calls[1]['model']
    assert routed['gemini'].health_report()['total_requests']==1


def test_schema_rejects_non_json_before_using_a_fallback(monkeypatch,routed):
    calls=responses(monkeypatch,[(200,'Not structured','stop'),(200,'{"columns":{}}','stop')])
    assert json.loads(llm.invoke_llm('Schema evidence',task='schema'))=={'columns':{}}
    assert [c['model'] for c in calls]==['nvidia/nemotron-3.5-super-vl-120b-a12b','gemini-3.5-flash-lite']


def test_per_account_capacity_allows_parallel_keys_without_reusing_busy_key():
    pool=QuotaAwareKeyPool(['a','b'])
    with ThreadPoolExecutor(2) as workers:
        keys=list(workers.map(lambda _:pool.get_key(max_in_flight=1),range(2)))
    assert set(keys)=={'a','b'} and pool.get_key(max_in_flight=1) is None
    pool.report_success('a')
    assert pool.get_key(max_in_flight=1)=='a'


def test_request_and_token_reservations_and_retry_after(monkeypatch):
    import backend.services.quota_key_pool as module
    now=[1000.];monkeypatch.setattr(module.time,'time',lambda:now[0])
    pool=QuotaAwareKeyPool(['a'])
    assert pool.get_key(rpm_limit=2,token_budget=100,request_tokens=60)=='a'
    pool.report_success('a')
    assert pool.get_key(token_budget=100,request_tokens=60) is None
    assert pool.get_key(rpm_limit=1) is None
    now[0]+=61
    assert pool.get_key(rpm_limit=1,token_budget=100,request_tokens=60)=='a'
    pool.report_failure('a',429,retry_after_seconds=120)
    now[0]+=66
    assert pool.get_key() is None
    now[0]+=55
    assert pool.get_key()=='a'


def test_routes_only_use_requested_groq_model_and_exclude_failed_candidates():
    models={t['model'] for targets in llm.TASK_ROUTES.values() for t in targets}
    assert 'z-ai/glm-5.3-flash' not in models and 'google/diffusiongemma-26b-a4b-it' not in models
    assert {t['model'] for targets in llm.TASK_ROUTES.values() for t in targets if t['provider']=='groq'}=={'openai/gpt-oss-120b'}


def test_unknown_task_fails_before_contacting_a_provider(monkeypatch,routed):
    calls=responses(monkeypatch,[])
    with pytest.raises(ValueError,match='Unknown LLM task'):llm.invoke_llm('Question',task='invented')
    assert not calls
