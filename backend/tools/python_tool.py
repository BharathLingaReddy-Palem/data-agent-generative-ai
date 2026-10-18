"""Bounded analytical execution in a disposable process with no server credentials."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from backend.config import PYTHON_TIMEOUT_SECONDS, PYTHON_MEMORY_MB


_EXECUTION_SLOTS = threading.BoundedSemaphore(2)


def execute_python(code, df, *, timeout_seconds=None, memory_mb=None):
    if not _EXECUTION_SLOTS.acquire(blocking=False):
        return dict(success=False,stdout='',result=None,error='Analytical workers are busy. Please try again.')
    try:
        return _execute_python(code,df,timeout_seconds=timeout_seconds,memory_mb=memory_mb)
    finally:
        _EXECUTION_SLOTS.release()


def _execute_python(code, df, *, timeout_seconds=None, memory_mb=None):
    timeout = timeout_seconds if timeout_seconds is not None else PYTHON_TIMEOUT_SECONDS
    memory = memory_mb if memory_mb is not None else PYTHON_MEMORY_MB
    def failure(message):
        return dict(success=False,stdout='',result=None,error=message)
    if not 0 < timeout <= 60 or not 64 <= memory <= 2048:
        return failure('Invalid execution limits.')
    cleaned = code.strip()
    if cleaned.startswith('```'):
        cleaned = cleaned.split('\n',1)[-1].rsplit('```',1)[0].strip()
    if len(cleaned)>16384 or df.size>2_000_000:
        return failure('Code or dataset exceeds analytical execution limit.')
    try:
        data = df.to_json(orient='table',date_format='iso')
        payload = json.dumps(dict(code=cleaned,data=data))
        if len(payload.encode())>16*1024*1024:
            return failure('Dataset exceeds 16 MB execution limit.')
    except Exception as exc:
        return failure(f'Dataset serialization failed: {exc}')
    env = {key:os.environ[key] for key in ('SystemRoot','WINDIR','TEMP','TMP','LANG') if key in os.environ}
    env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONIOENCODING='utf-8')
    worker = Path(__file__).with_name('analytical_worker.py').resolve()
    close_job = None
    process = None
    with tempfile.TemporaryDirectory(prefix='ds-analytics-') as directory:
        try:
            process = subprocess.Popen([sys.executable,'-I',str(worker),str(memory),str(math.ceil(timeout))],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                text=True,encoding='utf-8',cwd=directory,env=env,
                creationflags=0x4 | 0x08000000 if os.name=='nt' else 0)
            if os.name=='nt':
                from backend.tools.process_limits import constrain_windows
                close_job = constrain_windows(process,memory,math.ceil(timeout))
            out, err = process.communicate(payload,timeout=timeout)
            if process.returncode != 0:
                return failure('Worker failed or exceeded its CPU/memory limit.')
            if len(out.encode())>1024*1024:
                return failure('Worker output exceeds 1 MB.')
            return json.loads(out)
        except subprocess.TimeoutExpired:
            return failure(f'Execution timed out after {timeout:g} seconds.')
        except Exception as exc:
            return failure(f'Isolated execution failed: {type(exc).__name__}: {exc}')
        finally:
            if close_job:
                close_job()
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.communicate()
