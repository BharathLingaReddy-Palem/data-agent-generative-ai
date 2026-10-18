"""Task-aware provider routing with bounded retries and shared key health."""
import json
import logging
import threading
import time
from pathlib import Path
from typing import Optional
import requests
from backend.services.quota_key_pool import QuotaAwareKeyPool
from backend.config import (BASE_DIR,GROQ_API_KEYS,GROQ_BASE_URL,GROQ_REASONING_MODEL,
    NVIDIA_API_KEYS,NVIDIA_BASE_URL,NVIDIA_GPT_20B_MODEL,GEMINI_API_KEYS,
    GEMINI_BASE_URL,GEMINI_FAST_MODEL,DEFAULT_PROVIDER,NVIDIA_RPM,GROQ_RPM,
    GROQ_TPM,GEMINI_FAST_RPM,GEMINI_REASONING_RPM)
logger=logging.getLogger(__name__)
groq_key_pool=QuotaAwareKeyPool(GROQ_API_KEYS,provider='groq')
nvidia_key_pool=QuotaAwareKeyPool(NVIDIA_API_KEYS,provider='nvidia')
gemini_key_pool=QuotaAwareKeyPool(GEMINI_API_KEYS,provider='gemini')
_model_cooldowns={}
_model_lock=threading.Lock()
ROUTES_PATH=BASE_DIR/'backend'/'model_routes.json'


def load_task_routes(path=ROUTES_PATH):
    if not Path(path).is_file(): return {}
    routes=json.loads(Path(path).read_text(encoding='utf-8'))['tasks']
    for task,targets in routes.items():
        if not targets or len(targets)>5: raise ValueError('Each LLM task requires 1-5 targets.')
        for target in targets:
            if target['provider'] not in ('gemini','groq','nvidia') or not isinstance(target['model'],str) or not target['model'].strip():
                raise ValueError('Invalid provider/model in LLM route configuration.')
    return routes


TASK_ROUTES=load_task_routes()


def routing_summary():
    return {task:[dict(provider=t['provider'],model=t['model']) for t in targets] for task,targets in TASK_ROUTES.items()}


def key_pool_health():
    """Observed local health, not remaining provider billing quota."""
    return {p:pool.health_report() for p,pool in [('groq',groq_key_pool),('nvidia',nvidia_key_pool),('gemini',gemini_key_pool)]}


class LLMOutputError(ValueError): pass


def _call_openai_compatible_endpoint(url,api_key,model,prompt,system_prompt=None,temperature=.2,max_tokens=4096,timeout=25):
    messages=[]
    if system_prompt: messages.append({'role':'system','content':system_prompt})
    messages.append({'role':'user','content':prompt})
    payload=dict(model=model,messages=messages,temperature=temperature,max_tokens=max_tokens,stream=False)
    if url.startswith(GROQ_BASE_URL) or url.startswith(GEMINI_BASE_URL): payload['reasoning_effort']='low'
    elif 'nemotron-3.5-super-vl' in model or 'diffusiongemma' in model:
        payload['chat_template_kwargs']={'enable_thinking':False}
    response=requests.post(url,headers={'Authorization':'Bearer '+api_key,'Content-Type':'application/json','Accept':'application/json'},json=payload,timeout=(min(10,timeout),timeout))
    response.raise_for_status()
    data=response.json();choices=data.get('choices') or []
    if not choices: raise LLMOutputError('No completion choices.')
    choice=choices[0];content=choice.get('message',{}).get('content')
    if not isinstance(content,str) or not content.strip(): raise LLMOutputError('No final answer.')
    if choice.get('finish_reason') in ('length','content_filter'): raise LLMOutputError('Incomplete or filtered answer.')
    return content


def _targets(tier,task,preferred_provider):
    pools={'groq':groq_key_pool,'nvidia':nvidia_key_pool,'gemini':gemini_key_pool}
    bases={'groq':GROQ_BASE_URL,'nvidia':NVIDIA_BASE_URL,'gemini':GEMINI_BASE_URL}
    if task:
        if task not in TASK_ROUTES: raise ValueError('Unknown LLM task: '+task)
        candidates=[(v['provider'],v['model']) for v in TASK_ROUTES[task]]
        preferred=preferred_provider
    else:
        # Legacy tier-only callers retain their provider preference. Production
        # agents pass an explicit task. Groq candidates are restricted to 120B.
        candidates=[('groq',GROQ_REASONING_MODEL),('nvidia',NVIDIA_GPT_20B_MODEL)]
        preferred=preferred_provider or DEFAULT_PROVIDER
    if preferred: candidates.sort(key=lambda item:item[0]!=preferred)
    return [(p,m,bases[p]+'/chat/completions',pools[p]) for p,m in candidates]


def invoke_llm(prompt:str,system_prompt:Optional[str]=None,tier='reasoning',preferred_provider=None,
               temperature=.2,max_tokens=4096,max_retries=5,task=None):
    """Try measured task models, one request per key, with no credential leakage."""
    last_error='No configured key has capacity.'
    for provider,model,url,pool in _targets(tier,task,preferred_provider):
        with _model_lock:
            if _model_cooldowns.get((provider,model),0)>time.time(): continue
        if not len(pool): continue
        tokens=max(64,min(int(max_tokens),8192))
        # Conservative reservation, not an exact tokenizer or billing counter.
        input_estimate=(len(prompt)+len(system_prompt or '')+2)//3+64
        if provider=='groq':
            tokens=min(tokens,GROQ_TPM-input_estimate)
            if tokens<64:
                last_error='Prompt exceeds configured Groq token budget.'
                continue
        rpm=GROQ_RPM if provider=='groq' else NVIDIA_RPM if provider=='nvidia' else (GEMINI_FAST_RPM if model==GEMINI_FAST_MODEL else GEMINI_REASONING_RPM)
        for _ in range(max(1,min(max_retries,2))):
            key=pool.get_key(rpm_limit=rpm,token_budget=GROQ_TPM if provider=='groq' else None,
                             request_tokens=input_estimate+tokens,max_in_flight=1)
            if not key: break
            try:
                answer=_call_openai_compatible_endpoint(url,key,model,prompt,system_prompt=system_prompt,temperature=temperature,max_tokens=tokens)
                if task in ('schema','supervisor'):
                    clean=answer.strip()
                    if clean.startswith('```'): clean=clean.split('\n',1)[-1].rsplit('```',1)[0].strip()
                    if not isinstance(json.loads(clean),dict): raise LLMOutputError('Structured task requires a JSON object.')
                pool.report_success(key)
                return answer
            except requests.HTTPError as exc:
                status=exc.response.status_code if exc.response is not None else 0
                retry_after=0
                try: retry_after=float(exc.response.headers.get('Retry-After','0'))
                except (ValueError,TypeError,AttributeError): pass
                pool.report_failure(key,status,'HTTP '+str(status),retry_after_seconds=retry_after)
                last_error=provider+' HTTP '+str(status)
                if status in (400,404,410) or 500<=status<600:
                    with _model_lock: _model_cooldowns[provider,model]=time.time()+(300 if status<500 else max(20,retry_after))
                    break
                if status not in (401,403,429): break
            except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
                pool.report_failure(key,0,type(exc).__name__)
                last_error=provider+' '+type(exc).__name__
                break
    # Raw response bodies and key fragments never become a chat answer.
    logger.warning('LLM routes unavailable for task %s: %s',task or tier,last_error)
    return '[Analysis completed. Notice: Unable to contact LLM service: '+last_error+']'
