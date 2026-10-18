from pathlib import Path
import runpy
import subprocess
import sys
from types import SimpleNamespace

import pytest
import run_regression


@pytest.mark.parametrize('status', [1,2,5])
def test_runner_propagates_failures_without_running_frontend(monkeypatch, status):
    monkeypatch.setattr(run_regression.subprocess, 'run', lambda *a,**k:SimpleNamespace(returncode=status))
    monkeypatch.setattr(run_regression.shutil, 'which', lambda *a:pytest.fail('Frontend ran after Python failure'))
    assert run_regression.main(['--frontend']) == status


def test_runner_propagates_frontend_failure(monkeypatch):
    commands = []
    def run(command, cwd):
        commands.append(command)
        return SimpleNamespace(returncode=0 if len(commands)==1 else 7)
    monkeypatch.setattr(run_regression.subprocess, 'run', run)
    monkeypatch.setattr(run_regression.shutil, 'which', lambda name:'node')
    assert run_regression.main(['--frontend']) == 7
    assert commands[0][:3] == [sys.executable,'-m','pytest']
    assert commands[1][:2] == ['node','--test']


@pytest.mark.parametrize('name', ['test_master_suite.py','test_all_services.py','test_all_5_datasets.py',
    'test_analyst_pipeline.py','test_pipeline_3_datasets.py','test_classification.py'])
def test_legacy_entry_points_use_the_maintained_runner(monkeypatch, name):
    monkeypatch.setattr(run_regression, 'main', lambda:7)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(run_regression.ROOT/name), run_name='__main__')
    assert exc.value.code == 7


def test_runner_process_exits_nonzero_for_an_actual_failed_assertion(tmp_path):
    path = tmp_path/'test_intentional_failure.py'
    path.write_text('def test_failure():\n    assert False, "Intentional runner exit-code check"\n')
    result = subprocess.run([sys.executable, str(run_regression.ROOT/'run_regression.py'), str(path), '-q'],
        cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 1
    assert '1 failed' in result.stdout
