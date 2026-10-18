import numpy as np
import pandas as pd
import pytest
import joblib
from sklearn.linear_model import Ridge,LogisticRegression
from backend.services.automl_engine import run_automl,FoldPreprocessor
import backend.services.automl_engine as engine
from backend.services.model_tools import strict_inference,explain_prediction,probability_diagnostics,threshold_metrics
from backend.services.specialized_models import forecast


def test_recipe_reuse_audit_and_owner_boundaries(client,accounts):
    headers,other=accounts
    csv=b'date,amount,category,target\n31/12/2025,-200, YES ,0\n01/01/2026,,no,1\n01/01/2026,,no,1\n'
    pid=client.post('/api/profile',headers=headers,files={'file':('recipe.csv',csv,'text/csv')}).json()['project_id']
    base='/api/workspace/'+pid
    plan=dict(protected_target='target',sentinels=[dict(column='amount',values=['-200'])],types={'date':'date'},date_formats={'date':'%d/%m/%Y'},
        categories={'category':{'case':'lower','mapping':{'yes':'Y','no':'N'}}},missing={'amount':{'strategy':'constant','value':0}},remove_duplicates=True)
    rid=client.post('/api/cleaning-recipes',headers=headers,json=dict(name='Year-end cleanup',plan=plan)).json()['id']
    assert not client.get('/api/cleaning-recipes',headers=other).json()
    recipe=client.get('/api/cleaning-recipes',headers=headers).json()[0]
    assert recipe['id']==rid
    change=dict(plan=recipe['plan'],revision=0,label='Recipe applied')
    preview=client.post(base+'/clean/preview',headers=headers,json=change).json()
    assert preview['change_count']>=7 and preview['after']['rows']==2
    assert any(r['row']==1 and r['operation']=='replace_sentinels' for r in preview['changes'])
    change['preview_token']=preview['preview_token']
    full_preview=client.post(base+'/clean/preview-audit',headers=headers,json=change)
    assert full_preview.status_code==200 and b'remove_duplicate' in full_preview.content
    assert client.get(base,headers=headers).json()['revision']==0
    cleaned=client.post(base+'/clean/apply',headers=headers,json=change).json();vid=cleaned['active_version_id']
    assert cleaned['versions'][-1]['audit_available'] and not cleaned['versions'][0]['audit_available']
    audit=client.get(base+f'/versions/{vid}/audit',headers=headers)
    assert audit.status_code==200 and b'remove_duplicate' in audit.content and b'fill_missing_constant' in audit.content
    assert client.get(base+f'/versions/{vid}/audit',headers=other).status_code==404
    assert client.get(base+'/workflow',headers=headers).json()['version_number']==2
    another=client.post('/api/profile',headers=headers,files={'file':('another.csv',csv,'text/csv')}).json()['project_id']
    assert client.post('/api/workspace/'+another+'/clean/preview',headers=headers,json=dict(change,revision=0)).json()['after']['rows']==2


def test_selection_fits_training_folds_and_strict_inference(tmp_path,monkeypatch):
    monkeypatch.setattr(engine,'ARTIFACTS_DIR',tmp_path)
    monkeypatch.setattr(engine,'get_candidate_models',lambda task:{'Ridge':Ridge()})
    rng=np.random.default_rng(12);n=120
    df=pd.DataFrame({'signal':rng.normal(size=n),'noise':rng.normal(size=n),'other':rng.normal(size=n)})
    df['target']=df.signal*5+rng.normal(0,.1,n)
    calls=[];old=FoldPreprocessor.fit
    def spy(self,X,y=None):calls.append(set(X.index));return old(self,X,y)
    monkeypatch.setattr(FoldPreprocessor,'fit',spy)
    result=run_automl(df,'target','features',run_tuning=False,selection_percentile=50,include_columns=['signal','noise'],compare_features=True)
    from backend.services.evaluation import partitions
    train,test,_,_=partitions(df,df.target.to_numpy(),'regression')
    assert all(not rows.intersection(test) for rows in calls)
    assert any(len(rows)<len(train) for rows in calls)
    assert len(result['selected_encoded_features'])==1 and 'signal' in result['selected_encoded_features'][0]
    assert result['feature_comparison']['after_cv_mean']>.9
    bundle=joblib.load(result['saved_model_path'])
    with pytest.raises(ValueError,match='Missing required'):strict_inference(bundle,pd.DataFrame({'signal':[1]}))
    with pytest.raises(ValueError,match='invalid numeric'):strict_inference(bundle,pd.DataFrame({'signal':['bad'],'noise':[1]}))
    values=pd.DataFrame({'signal':[1.,2.],'noise':[0.,None],'extra':['A','B']})
    predictions,_,_,warnings=strict_inference(bundle,values)
    assert len(predictions)==2 and any('Missing feature' in w for w in warnings)
    explanation=explain_prediction(bundle,dict(signal=1.,noise=0.))
    assert explanation['features'][0]['feature']=='signal' and explanation['features'][0]['difference']>3


def test_probability_reliability_and_thresholds():
    y=np.array([0,1,0,1]);p=np.array([[.9,.1],[.1,.9],[.9,.1],[.1,.9]])
    result=probability_diagnostics(y,p,['no','yes'])
    assert result['metrics'][1]['brier_score']==pytest.approx(.01)
    assert result['metrics'][1]['ece']==pytest.approx(.1)
    assert len(result['precision_recall'])==2
    assert threshold_metrics(y,p,['no','yes'],.5)['f1']==1
    assert threshold_metrics(y,p,['no','yes'],.95)['recall']==0
    assert threshold_metrics(y,p,['no','yes'],.05)['precision']==.5
    with pytest.raises(ValueError):threshold_metrics(y,p,['no','yes'],2)


def test_calibration_bins_count_decimal_boundaries_once():
    scores=np.array([0.,.1,.2,.3,.4,.5,.6,.7,.8,.9,1.])
    actual=np.array([0,1,0,1,0,1,0,1,0,1,1])
    result=probability_diagnostics(actual,np.column_stack([1-scores,scores]),['no','yes'])
    for calibration in result['calibration']:
        assert sum(b['count'] for b in calibration['bins'])==len(scores)


def test_perfect_categorical_feature_retains_features_with_infinite_scores():
    frame=pd.DataFrame({'category':['A','B']*40,'numeric':np.arange(80)})
    prep=FoldPreprocessor(selection_percentile=50,task_type='classification').fit(frame,np.array([0,1]*40))
    assert prep.transform(frame).shape==(80,2)
    assert len(prep.get_feature_names_out())==2


def test_feature_assessment_flags_identifiers_and_target_copies(client,accounts):
    headers,other=accounts
    df=pd.DataFrame({'customer_id':range(100),'sequence':range(100),'signal':np.sin(np.arange(100)), 'proxy':['no','yes']*50,'label':['no','yes']*50})
    pid=client.post('/api/profile',headers=headers,files={'file':('flags.csv',df.to_csv(index=False),'text/csv')}).json()['project_id']
    path=f'/api/workspace/{pid}/features'
    assert client.post(path,headers=other,json={'target_column':'label'}).status_code==404
    response=client.post(path,headers=headers,json={'target_column':'label'})
    assert response.status_code==200,response.text
    rows={r['column']:r for r in response.json()['features']}
    assert not rows['customer_id']['eligible']
    assert not rows['sequence']['recommended'] and 'numeric ID' in str(rows['sequence']['flags'])
    assert not rows['proxy']['recommended'] and 'target copy' in str(rows['proxy']['flags'])


def test_batch_api_validates_schema_ownership_threshold_and_download(client,accounts,tmp_path,monkeypatch):
    import backend.workspace_api as api
    monkeypatch.setattr(engine,'ARTIFACTS_DIR',tmp_path);monkeypatch.setattr(api,'ARTIFACTS_DIR',tmp_path)
    monkeypatch.setattr(engine,'get_candidate_models',lambda task:{'Logistic':LogisticRegression()})
    headers,other=accounts
    rng=np.random.default_rng(3);x=rng.normal(size=100);df=pd.DataFrame({'signal':x,'noise':rng.normal(size=100),'label':np.where(x>0,'yes','no')})
    pid=client.post('/api/profile',headers=headers,files={'file':('binary.csv',df.to_csv(index=False),'text/csv')}).json()['project_id']
    import backend.main as main
    session=main.active_sessions[pid]
    api.workspace_store.ensure(session)
    result=run_automl(df,'label',pid,run_tuning=False)
    run=api.workspace_store.save_run(session,result,'automl',{})
    base=f'/api/workspace/{pid}/runs/{run["run_id"]}'
    assert client.get(base+'/schema',headers=other).status_code==404
    assert client.get(base+'/schema',headers=headers).json()['required_columns']==['signal','noise']
    bad=client.post(base+'/batch',headers=headers,files={'file':('missing.csv',b'signal\n1\n','text/csv')})
    assert bad.status_code==400 and 'Missing required' in bad.json()['detail']
    response=client.post(base+'/batch',headers=headers,data={'threshold':'.9','positive_label':'yes'},files={'file':('new.csv',b'signal,noise,record\n1,0,A\n-1,0,B\n','text/csv')})
    assert response.status_code==200,response.text
    batch=response.json();assert batch['count']==2 and batch['preview'][0]['record']=='A'
    download=f'/api/workspace/{pid}/batches/{batch["batch_id"]}/download'
    assert client.get(download,headers=other).status_code==404
    assert b'model_prediction' in client.get(download,headers=headers).content
    assert client.post(base+'/threshold',headers=headers,json={'threshold':.9}).json()['positive_label']=='yes'
    assert client.post(base+'/explain',headers=headers,json={'record':{'signal':1,'noise':0}}).status_code==200


def test_forecast_calibration_is_separate_from_holdout_and_multiple_series():
    dates=pd.date_range('2010-01-01',periods=120,freq='MS');values=100+np.arange(120)*.3+10*np.sin(np.arange(120)*2*np.pi/12)
    df=pd.DataFrame({'date':dates,'outcome':values})
    settings=dict(date_column='date',target_column='outcome',horizon=6,season_length=12,backtest_windows=6)
    a=forecast(df,settings,'forecast');changed=df.copy();changed.loc[114:,'outcome']+=2000;b=forecast(changed,settings,'forecast')
    assert a['evaluation']['validation_origins']==3 and a['evaluation']['calibration_origins']==3
    assert a['best_model']['model_name']==b['best_model']['model_name']
    assert [r['interval_width'] for r in a['horizon_errors']]==pytest.approx([r['interval_width'] for r in b['horizon_errors']])
    assert b['evaluation']['holdout_coverage']==0
    assert len(a['horizon_errors'])==6 and a['evaluation']['coverage_observations']==6
    grouped=pd.concat([df.assign(store='A'),df.assign(store='B',outcome=values*2),df.head(10).assign(store='short')])
    result=forecast(grouped,dict(settings,series_column='store'),'grouped')
    assert result['evaluation']['series_count']==2 and result['evaluation']['failed_series_count']==1
    assert result['failed_series'][0]['series']=='short'
