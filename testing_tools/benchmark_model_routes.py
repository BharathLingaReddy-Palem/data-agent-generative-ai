"""Explicit live synthetic model/key audit; never prints or saves credentials.

Run from the project root. No application datasets or prompts are uploaded.
The five short cases test routing candidates directly, without hidden fallbacks.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CANDIDATES = [
    ('gemini', 'gemini-3.5-flash-lite'),
    ('gemini', 'gemini-3.8-flash'),
    ('groq', 'openai/gpt-oss-120b'),
    ('nvidia', 'z-ai/glm-5.3-flash'),
    ('nvidia', 'nvidia/nemotron-3.5-super-vl-120b-a12b'),
    ('nvidia', 'stepfun-ai/step-5-preview'),
    ('nvidia', 'google/diffusiongemma-26b-a4b-it'),
    ('nvidia', 'openai/gpt-oss-20b'),
]
URLS = {
    'gemini': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
    'groq': 'https://api.groq.com/openai/v1/chat/completions',
    'nvidia': 'https://integrate.api.nvidia.com/v1/chat/completions',
}
SMOKE_MODELS = dict(gemini='gemini-3.5-flash-lite', groq='openai/gpt-oss-120b', nvidia='openai/gpt-oss-20b')
CASES = {
    'plan': '''Return JSON only with keys target_metric, dimensions, agents_to_run.
Synthetic dataset columns: customer_id, date, region, revenue, churn_rate.
Goal: inspect revenue by region and changes over time. Set target_metric to revenue,
dimensions to [region]. Include schema, quality, kpi, eda, trend, visualization, report.
Order schema before quality and trend before visualization. Do not invent columns.''',
    'schema': '''Return JSON only mapping each of these exact columns to one semantic role.
customer_id is a unique integer assigned to customers; date contains ISO dates;
revenue contains monetary amounts with unknown currency; region contains East/West;
churn_rate is a numeric fraction. Allowed roles: Identifier, Temporal, Measure, Dimension.
Do not add other columns.''',
    'interpretation': '''Return JSON only, using the supplied computed evidence:
two revenue observations 100 and 200, currency unknown; churn fractions 0.10 and 0.20;
raw p=0.04 but multiple-test adjusted q=0.12, alpha=0.05. Cross-sectional snapshot,
no time series or randomized intervention. Required keys: revenue_total (number),
churn_mean (fraction number), adjusted_significant (boolean), causal (boolean),
trend_confirmed (boolean), p_is_probability_null_true (boolean), currency_known (boolean).
Compute/interpret correctly, without invented evidence.''',
    'chat_code': '''Return JSON only with one string field code containing analytical code.
df has four rows with columns region,revenue: (East,10),(West,20),(East,30),(East,10).
Assign a dict to result with keys rows, duplicates, by_region. Count all rows, fully
duplicated rows, and total revenue per region including duplicates. Do not import,
use loops, comprehensions, lambdas, attribute tricks, files, networking or eval/exec.
Allowed: len, int, df.duplicated().sum(), df.groupby('region')['revenue'].sum().to_dict().''',
    'synthesis': '''Return JSON only with numeric keys holdout_mae, baseline_mae,
coverage_percent and boolean keys beats_baseline, coverage_below_target, calibrated,
and string summary. Evidence: forecast holdout MAE 13.38, seasonal naive MAE 47.83,
observed interval coverage 83.3 percent on 12 holdout periods, target coverage 95 percent.
Classification probabilities have not been calibrated. Summary must state limited
sample/uncertainty and no guaranteed future coverage. Do not invent currency or causes.''',
}


def extract_json(content):
    text = content.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    return json.loads(text)


def grade(case, content):
    value = extract_json(content)
    if case == 'plan':
        agents = value['agents_to_run']
        assert value['target_metric'] == 'revenue' and value['dimensions'] == ['region']
        assert set(agents) == {'schema','quality','kpi','eda','trend','visualization','report'}
        assert agents.index('schema') < agents.index('quality') and agents.index('trend') < agents.index('visualization')
    elif case == 'schema':
        assert value == dict(customer_id='Identifier',date='Temporal',revenue='Measure',region='Dimension',churn_rate='Measure')
    elif case == 'interpretation':
        assert value['revenue_total'] == 300 and abs(value['churn_mean']-.15) < 1e-6
        for field in ('adjusted_significant','causal','trend_confirmed','p_is_probability_null_true','currency_known'):
            assert value[field] is False, field
    elif case == 'chat_code':
        import pandas as pd
        from backend.tools.python_tool import execute_python
        result = execute_python(value['code'], pd.DataFrame({'region':['East','West','East','East'],'revenue':[10,20,30,10]}))
        assert result['success'], result['error']
        assert result['result'] == dict(rows=4,duplicates=1,by_region={'East':50,'West':20})
    elif case == 'synthesis':
        assert value['holdout_mae'] == 13.38 and value['baseline_mae'] == 47.83 and value['coverage_percent'] == 83.3
        assert value['beats_baseline'] is True and value['coverage_below_target'] is True and value['calibrated'] is False
        assert isinstance(value['summary'], str) and len(value['summary']) > 30
    return True


def run(out, phase):
    env = dotenv_values(ROOT/'.env')
    pools = {p: [(f'{prefix}{i}', env.get(f'{prefix}{i}', '').strip()) for i in range(1,n+1) if env.get(f'{prefix}{i}', '').strip()]
             for p,prefix,n in [('gemini','Gemini_ApiKey_',6),('groq','GROQ_API_KEY_',11),('nvidia','NVIDIA_API_KEY_',7)]}
    secrets = [key for entries in pools.values() for _,key in entries]
    def redact(text):
        for secret in secrets:
            text = text.replace(secret, '[REDACTED]')
        return text
    results = []
    out.mkdir(parents=True, exist_ok=True)
    def persist():
        payload = dict(created_at=datetime.now(timezone.utc).isoformat(),synthetic_only=True,phase=phase,
                       key_counts={p:len(v) for p,v in pools.items()},results=results)
        (out/f'{phase}.json').write_text(redact(json.dumps(payload,indent=2,ensure_ascii=False)),encoding='utf-8')
    def call(provider, model, alias, key, case):
        prompt = 'Return exactly the JSON object {"ready":true} with no extra text.' if case == 'key_smoke' else CASES[case]
        payload = dict(model=model,messages=[{'role':'user','content':prompt}],temperature=.1,max_tokens=1536,stream=False)
        if provider == 'groq': payload['reasoning_effort'] = 'low'
        if provider == 'nvidia' and ('nemotron' in model or 'diffusiongemma' in model):
            payload['chat_template_kwargs'] = {'enable_thinking':False}
        record = dict(provider=provider,model=model,key_alias=alias,case=case)
        start = time.monotonic()
        try:
            response = requests.post(URLS[provider],headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},json=payload,timeout=(10,65))
            record['http_status'] = response.status_code
            record['retry_after'] = response.headers.get('Retry-After')
            if response.status_code != 200:
                record.update(status='http_error',error=redact(response.text[:1500]))
            else:
                data=response.json();choice=data.get('choices',[{}])[0];content=choice.get('message',{}).get('content') or ''
                record.update(usage=data.get('usage'),finish_reason=choice.get('finish_reason'),content=redact(content[:10000]))
                try:
                    if case=='key_smoke': assert extract_json(content)=={'ready':True}
                    else: grade(case,content)
                    record['status']='passed'
                except Exception as exc:
                    record.update(status='validation_failed',error=redact(type(exc).__name__+': '+str(exc)[:500]))
        except requests.RequestException as exc:
            # Exception text can include request details: save only its class.
            record.update(status='transport_error',error=type(exc).__name__)
        record['seconds']=round(time.monotonic()-start,3)
        return record

    if phase=='keys':
        work=[(p,SMOKE_MODELS[p],alias,key,'key_smoke') for p,entries in pools.items() for alias,key in entries]
    elif phase=='recheck':
        previous=json.loads((out/'keys.json').read_text(encoding='utf-8'))['results']
        failed={r['key_alias'] for r in previous if r['status']!='passed'}
        work=[(p,'gemini-3.8-flash' if p=='gemini' else SMOKE_MODELS[p],alias,key,'key_smoke')
              for p,entries in pools.items() for alias,key in entries if alias in failed]
    else:
        # Successful credential readiness alone is not a task benchmark.
        smoke=json.loads((out/'keys.json').read_text(encoding='utf-8'))['results']
        good={r['key_alias'] for r in smoke if r['status']=='passed'}
        work=[]
        for provider,model in CANDIDATES:
            entries=[entry for entry in pools[provider] if entry[0] in good]
            if not entries:
                results.append(dict(provider=provider,model=model,status='skipped_no_ready_key'))
                continue
            for i,case in enumerate(CASES):
                alias,key=entries[i%len(entries)]
                work.append((provider,model,alias,key,case))
    persist()
    # Independent accounts can make concurrent requests; this audit is bounded,
    # performs no 429 retries and sends <=5 task requests per model.
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures=[executor.submit(call,*args) for args in work]
        for future in as_completed(futures):
            record=future.result();results.append(record);persist()
            print(json.dumps({k:record[k] for k in ('provider','model','key_alias','case','status','seconds')}),flush=True)
    persist()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['keys','tasks','recheck'],required=True)
    parser.add_argument('--output',default='artifacts/model-audit')
    args=parser.parse_args()
    run(ROOT/args.output,args.phase)
