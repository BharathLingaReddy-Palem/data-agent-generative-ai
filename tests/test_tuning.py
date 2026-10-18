from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import Ridge
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, r2_score
import backend.services.automl_engine as engine


def test_real_optuna_search_refits_and_saves_selected_parameters(tmp_path,monkeypatch):
    monkeypatch.setattr(engine,'ARTIFACTS_DIR',tmp_path)
    monkeypatch.setattr(engine,'get_candidate_models',lambda task:{'Decision Tree':DecisionTreeClassifier(max_depth=1,random_state=42)})
    search=engine.tune_best_model_with_optuna
    def short_search(*args,**kwargs):
        kwargs.update(n_trials=2,timeout_sec=15)
        return search(*args,**kwargs)
    monkeypatch.setattr(engine,'tune_best_model_with_optuna',short_search)
    observed=[]
    def explain(model,*args,**kwargs):
        observed.append(model.get_params());return {'model_depth':model.max_depth}
    monkeypatch.setattr(engine,'compute_feature_importance',explain)
    df=pd.DataFrame({'feature':np.tile([0,1],150),'target':np.tile([0,1],150)})
    result=engine.run_automl(df,'target','tuned-classification',run_tuning=True)
    tuning=result['optuna_tuning']
    assert tuning['applied'] is True,tuning
    assert tuning['optimization_trials']==tuning['completed_trials']==2
    bundle=joblib.load(result['saved_model_path']);model=bundle['pipeline'].named_steps['model']
    assert model.max_depth>=2 and model.tree_.node_count>0
    for key,value in tuning['best_parameters'].items():
        assert model.get_params()[key]==value and observed[0][key]==value
    _, X_test, _, y_test=train_test_split(df.drop(columns='target'),df['target'],test_size=0.2,random_state=42,stratify=df['target'])
    predicted=bundle['pipeline'].predict(X_test)
    assert result['best_model']['f1_macro']==round(f1_score(y_test,predicted,average='macro'),4)
    assert result['leaderboard'][0]==result['best_model']
    assert bundle['optuna_tuning']['applied']
    assert Path(result['saved_model_path']).name=='champion.joblib'


def regression_setup(tmp_path,monkeypatch,baseline_alpha):
    monkeypatch.setattr(engine,'ARTIFACTS_DIR',tmp_path)
    monkeypatch.setattr(engine,'get_candidate_models',lambda task:{'Ridge Regression':Ridge(alpha=baseline_alpha)})
    monkeypatch.setattr(engine,'compute_feature_importance',lambda *a,**k:{'available':True})
    x=np.linspace(-10,10,180)
    return pd.DataFrame({'feature':x,'target':4*x+0.01*np.sin(x)})


def tuning_result(alpha):
    return dict(best_parameters={'alpha':alpha},optimization_trials=1,completed_trials=1,best_cv_score=0.99)


def test_regression_saved_predictions_and_metrics_use_refitted_model(tmp_path,monkeypatch):
    df=regression_setup(tmp_path,monkeypatch,100)
    monkeypatch.setattr(engine,'tune_best_model_with_optuna',lambda *a,**k:tuning_result(0.001))
    result=engine.run_automl(df,'target','tuned-regression',run_tuning=True)
    assert result['optuna_tuning']['applied']
    bundle=joblib.load(result['saved_model_path'])
    assert bundle['pipeline'].named_steps['model'].alpha==0.001
    _, X_test, _, y_test=train_test_split(df.drop(columns='target'),df['target'],test_size=0.2,random_state=42)
    predicted=bundle['pipeline'].predict(X_test)
    assert result['best_model']['r2_score']==round(r2_score(y_test,predicted),4)
    np.testing.assert_allclose(result['diagnostic_chart']['predicted'],predicted)
    assert result['optuna_tuning']['tuned_cv_score']>result['optuna_tuning']['baseline_cv_score']


@pytest.mark.parametrize('mode',['failure','worse','disabled'])
def test_failed_or_worse_tuning_keeps_working_baseline(tmp_path,monkeypatch,mode):
    df=regression_setup(tmp_path,monkeypatch,0.001)
    def search(*args,**kwargs):
        assert mode!='disabled','Disabled tuning must not run the search.'
        return tuning_result(-1 if mode=='failure' else 100000)
    monkeypatch.setattr(engine,'tune_best_model_with_optuna',search)
    result=engine.run_automl(df,'target','baseline-'+mode,run_tuning=mode!='disabled')
    if mode=='disabled':assert result['optuna_tuning'] is None
    else:
        assert result['optuna_tuning']['applied'] is False
        assert result['optuna_tuning']['reason']
    bundle=joblib.load(result['saved_model_path'])
    assert bundle['pipeline'].named_steps['model'].alpha==0.001
    assert len(engine.predict_with_saved_model(result['saved_model_path'],{'feature':5})['predictions'])==1
