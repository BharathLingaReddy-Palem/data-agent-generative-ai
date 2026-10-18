import importlib
from pathlib import Path
import pandas as pd
import pytest


@pytest.mark.parametrize('module',['sklearn','joblib','pptx','reportlab','xlrd','openpyxl','xgboost','lightgbm','catboost','optuna','shap','jwt','pwdlib'])
def test_required_imports(module):
    assert importlib.import_module(module)


@pytest.mark.parametrize('name,target,task',[
    ('saas_churn.csv','churned','classification'),
    ('retail_orders.csv','sales','regression'),
])
def test_real_training_and_saved_predictions(tmp_path,monkeypatch,name,target,task):
    import backend.services.automl_engine as engine
    monkeypatch.setattr(engine,'ARTIFACTS_DIR',tmp_path)
    df=pd.read_csv(Path(__file__).with_name('data')/name)
    result=engine.run_automl(df,target_column=target,project_id='fixture-'+task,run_tuning=False)
    assert result['task_type']==task
    assert result['leaderboard'] and result['best_model']['model_name']
    prediction=engine.predict_with_saved_model(result['saved_model_path'],df.drop(columns=target).head(3).to_dict(orient='records'))
    assert len(prediction['predictions'])==3
    assert result['xai']
