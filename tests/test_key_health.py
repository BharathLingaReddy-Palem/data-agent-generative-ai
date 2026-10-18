import json
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
from backend.services import llm_service as llm
from backend.services.quota_key_pool import QuotaAwareKeyPool


def pools(monkeypatch, groq_keys=('groq-secret-key-111111',), nvidia_keys=('nvidia-secret-key-222222',)):
    monkeypatch.setattr(llm, '_model_cooldowns', {})
    groq = QuotaAwareKeyPool(list(groq_keys), provider='groq')
    nvidia = QuotaAwareKeyPool(list(nvidia_keys), provider='nvidia')
    monkeypatch.setattr(llm, 'groq_key_pool', groq)
    monkeypatch.setattr(llm, 'nvidia_key_pool', nvidia)
    return groq, nvidia


def provider_responses(monkeypatch, responses):
    calls = []
    def post(url, headers, json, timeout):
        calls.append((url, headers['Authorization']))
        value = responses.pop(0)
        if isinstance(value, Exception): raise value
        response = requests.Response()
        response.status_code = value
        response.url = url
        response._content = b'{"choices":[{"message":{"content":"Provider answer"}}]}'
        return response
    monkeypatch.setattr(requests, 'post', post)
    return calls


def test_health_endpoint_observes_real_request_rotation_and_outcomes(client, accounts, monkeypatch):
    keys = ('groq-secret-key-111111','groq-secret-key-333333')
    groq, nvidia = pools(monkeypatch, keys)
    calls = provider_responses(monkeypatch, [429,200])
    assert llm.invoke_llm('Question', preferred_provider='groq') == 'Provider answer'
    response = client.get('/api/keys/health', headers=accounts[0])
    assert response.status_code == 200
    health = response.json()
    assert health['groq'] == groq.health_report()
    assert health['groq']['total_requests'] == 2
    assert health['groq']['total_successes'] == 1 and health['groq']['total_failures'] == 1
    assert health['groq']['available_keys'] == 1
    assert health['groq']['keys'][0]['rate_limit_hits'] == 1
    assert health['groq']['keys'][0]['cooldown_remaining_s'] > 0
    assert calls[0][1] != calls[1][1]
    assert health['nvidia']['total_requests'] == 0
    assert health['nvidia']['keys'][0]['success_rate'] is None
    assert all(key not in response.text for key in (*keys, 'nvidia-secret-key-222222'))
    assert client.get('/api/keys/health').status_code == 401
    assert len(calls) == 2  # Health reads do not contact providers.


@pytest.mark.parametrize('failure', [429, 401, 403, 500, 502, 599, requests.Timeout('Timed out')])
def test_cooldowns_fail_over_without_reusing_exhausted_keys(client, accounts, monkeypatch, failure):
    groq, nvidia = pools(monkeypatch)
    calls = provider_responses(monkeypatch, [failure,200])
    assert llm.invoke_llm('Question', preferred_provider='groq', max_retries=5) == 'Provider answer'
    assert len(calls) == 2
    assert 'groq' in calls[0][0] and 'nvidia' in calls[1][0]
    health = client.get('/api/keys/health', headers=accounts[0]).json()
    assert health['groq']['all_exhausted'] is True
    assert health['groq']['total_requests'] == health['groq']['total_failures'] == 1
    assert health['nvidia']['total_successes'] == 1


def test_all_cooling_or_unconfigured_pools_make_no_requests(monkeypatch):
    groq, nvidia = pools(monkeypatch, nvidia_keys=())
    calls = provider_responses(monkeypatch, [429])
    first = llm.invoke_llm('Question', preferred_provider='groq')
    assert 'Unable to contact LLM service' in first
    second = llm.invoke_llm('Question', preferred_provider='groq')
    assert 'Unable to contact LLM service' in second
    assert len(calls) == 1
    assert groq.health_report()['total_requests'] == 1
    assert nvidia.health_report()['total_keys'] == 0


def test_pool_normalizes_keys_and_recovers_only_after_cooldown(monkeypatch):
    import backend.services.quota_key_pool as module
    clock = [1000.]
    monkeypatch.setattr(module.time, 'time', lambda:clock[0])
    pool = QuotaAwareKeyPool([' key-one ', 'key-one', '', '  '], provider='groq')
    assert len(pool) == 1
    assert pool.get_key() == 'key-one'
    pool.report_failure('key-one', 429)
    assert pool.get_key() is None
    assert pool.health_report()['total_requests'] == 1
    clock[0] += 64.9
    assert pool.get_key() is None
    clock[0] += .2
    assert pool.get_key() == 'key-one'
    pool.report_success('key-one')
    report = pool.health_report()
    assert report['total_requests'] == 2 and report['total_successes'] == 1
    assert report['keys'][0]['consecutive_failures'] == 0


def test_pool_counts_concurrent_requests_without_losing_outcomes():
    pool = QuotaAwareKeyPool(['one','two','three'])
    def call(_):
        key = pool.get_key(); pool.report_success(key)
    with ThreadPoolExecutor(max_workers=8) as workers:
        list(workers.map(call, range(200)))
    report = pool.health_report()
    assert report['total_requests'] == report['total_successes'] == 200
    assert report['total_failures'] == 0
    assert all(key['in_flight_requests'] == 0 for key in report['keys'])


def test_late_concurrent_failure_cannot_shorten_an_auth_cooldown(monkeypatch):
    import backend.services.quota_key_pool as module
    monkeypatch.setattr(module.time, 'time', lambda:1000.)
    pool = QuotaAwareKeyPool(['key'])
    pool.get_key(); pool.get_key()  # Two requests were already in flight.
    pool.report_failure('key', 401)
    pool.report_failure('key', 429)
    report = pool.health_report()
    assert report['keys'][0]['cooldown_remaining_s'] == 3600
    assert report['total_failures'] == report['total_requests'] == 2
