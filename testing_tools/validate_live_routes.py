"""Validate actual configured routes using only synthetic benchmark fixtures."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import threading
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from testing_tools.benchmark_model_routes import CASES,grade
from backend.services import llm_service as llm


def main():
    original=llm._call_openai_compatible_endpoint
    context=threading.local()
    def observed(url,key,model,prompt,**kwargs):
        started=time.monotonic()
        provider=next(p for p,base in [('gemini',llm.GEMINI_BASE_URL),('groq',llm.GROQ_BASE_URL),('nvidia',llm.NVIDIA_BASE_URL)] if url.startswith(base))
        event=dict(provider=provider,model=model)
        try:
            result=original(url,key,model,prompt,**kwargs);event['status']='returned';return result
        except Exception as exc:
            event['status']=type(exc).__name__;raise
        finally:
            event['seconds']=round(time.monotonic()-started,3);context.attempts.append(event)
    llm._call_openai_compatible_endpoint=observed
    work=[('supervisor','plan'),('schema','schema'),('eda','interpretation'),('hypothesis','interpretation'),
          ('trend','synthesis'),('chat_code','chat_code'),('chat_answer','synthesis'),('comparison','synthesis')]
    def check(task,case):
        context.attempts=[];start=time.monotonic()
        answer=llm.invoke_llm(CASES[case],task=task,temperature=.1,max_tokens=1536)
        error=None
        try:grade(case,answer);passed=True
        except Exception as exc:passed=False;error=type(exc).__name__+': '+str(exc)[:150]
        return dict(task=task,case=case,passed=passed,error=error,seconds=round(time.monotonic()-start,3),attempts=context.attempts,answer=answer)
    results=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(check,*args) for args in work]):
            result=future.result();results.append(result)
            print(json.dumps({k:result[k] for k in ('task','passed','seconds','attempts')}),flush=True)
    health={p:{k:h[k] for k in ('total_keys','total_requests','total_successes','total_failures')} for p,h in llm.key_pool_health().items()}
    path=ROOT/'artifacts/model-audit/live-routes.json'
    path.write_text(json.dumps(dict(checked_at=datetime.now(timezone.utc).isoformat(),results=results,health=health),indent=2),encoding='utf-8')
    if not all(r['passed'] for r in results):raise SystemExit(1)


if __name__=='__main__':main()
