import io
import time
import uuid
import zipfile
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import Ridge
from backend.services.workspace_data import transform, explore
from backend.services.workspace_store import WorkspaceStore
from backend.services.evaluation import partitions, performance_warnings
from backend.services.specialized_models import forecast, text_classification
import backend.services.specialized_models as specialized
import backend.services.automl_engine as engine


def test_preview_apply_undo_and_ownership(client,accounts):
    headers,other=accounts
    csv=b'group,amount,target\n A ,-200,0\n B ,20,1\n B ,20,1\n C ,30,0\n'
    pid=client.post('/api/profile',headers=headers,files={'file':('clean.csv',csv,'text/csv')}).json()['project_id']
    base='/api/workspace/'+pid
    original=client.get(base,headers=headers).json()
    assert len(original['versions'])==1
    assert client.get(base,headers=other).status_code==404
    plan=dict(sentinels=[dict(column='amount',values=['-200'])],rename={'group':'segment'},trim_text=True,remove_duplicates=True,protected_target='target')
    change=dict(plan=plan,revision=0,label='Sentinels and duplicates')
    assert client.post(base+'/clean/apply',headers=headers,json=change).status_code==409
    preview=client.post(base+'/clean/preview',headers=headers,json=change).json()
    assert preview['before']['rows']==4 and preview['after']['rows']==3
    assert preview['after']['missing_cells']==1
    unchanged=client.get(base,headers=headers).json()
    assert unchanged['summary']==original['summary']
    change['preview_token']=preview['preview_token']
    cleaned=client.post(base+'/clean/apply',headers=headers,json=change).json()
    assert cleaned['revision']==1 and len(cleaned['versions'])==2
    assert cleaned['summary']['rows']==3 and 'segment' in cleaned['columns']
    assert client.post(base+'/clean/apply',headers=headers,json=change).status_code==409
    restored=client.get(f'/api/projects/{pid}/session',headers=headers).json()
    assert restored['profile']['overview']['total_rows']==3
    undone=client.post(base+'/versions/activate',headers=headers,json={'revision':1}).json()
    assert undone['active_version_id']==original['active_version_id'] and undone['summary']['rows']==4
    assert len(undone['versions'])==2
    assert client.get(base+'/versions/'+cleaned['active_version_id']+'/download',headers=other).status_code==404
    assert b'segment,amount,target' in client.get(base+'/versions/'+cleaned['active_version_id']+'/download',headers=headers).content


def test_explicit_cleaning_protection_types_collision_and_filters():
    df=pd.DataFrame({'a':['2','bad',None], 'b':[1,2,3], 'target':[0,1,0]})
    with pytest.raises(ValueError,match='protected'):transform(df,dict(protected_target='target',types={'target':'string'}))
    with pytest.raises(ValueError,match='unique'):transform(df,dict(rename={'a':'b'}))
    with pytest.raises(ValueError,match='cannot convert'):transform(df,dict(types={'a':'number'}))
    cleaned,steps=transform(df,dict(types={'a':'number'},coerce_invalid=True))
    assert cleaned.a.isna().sum()==2 and steps[0]['invalid_to_missing']==1
    assert df.a.iloc[1]=='bad'
    out=explore(df,dict(filters=[dict(column='b',operator='gte',value=2),dict(column='b',operator='lt',value=3)],sort='b',descending=True))
    assert out['filtered_rows']==1 and out['rows'][0]['b']==2


@pytest.mark.parametrize('strategy',['grouped','chronological'])
def test_partitions_keep_entities_and_equal_dates_disjoint(strategy):
    data=pd.DataFrame({'entity':np.repeat(np.arange(20),5),'date':pd.date_range('2020-01-01',periods=50).repeat(2),'x':np.arange(100)})
    y=np.arange(100,dtype=float)
    train,test,cv,details=partitions(data,y,'regression',strategy,'entity','date')
    if strategy=='grouped':
        assert not set(data.entity.iloc[train])&set(data.entity.iloc[test])
        for a,b in cv.split():assert not set(data.entity.iloc[train[a]])&set(data.entity.iloc[train[b]])
    else:
        assert data.date.iloc[train].max()<data.date.iloc[test].min()
        for a,b in cv.split():assert data.date.iloc[train[a]].max()<data.date.iloc[train[b]].min()


def test_version_store_roundtrip_and_runs(tmp_path):
    store=WorkspaceStore(tmp_path/'versions.db');frame=pd.DataFrame({'x':[1,np.nan,3]})
    session=dict(project_id='p',owner_id='u',df=frame)
    first=store.ensure(session);second=store.add_version(session,frame.dropna(),'No blanks',[dict(operation='drop')],first)
    assert store.frame(session,first).equals(frame)
    session['active_version_id']=second
    store.save_run(session,dict(best_model={'primary_metric':.9}),'automl',{'split_strategy':'grouped'})
    assert store.runs(session)[0]['version_id']==second
    with pytest.raises(ValueError):store.frame(dict(project_id='p',owner_id='other'),first)
    store.save_template('u','Board report',{'title':'A'})
    assert not store.templates('other') and store.templates('u')[0]['name']=='Board report'


def test_grouped_automl_baseline_artifacts_and_cleaned_input(tmp_path,monkeypatch):
    monkeypatch.setattr(engine,'ARTIFACTS_DIR',tmp_path)
    monkeypatch.setattr(engine,'get_candidate_models',lambda _: {'Ridge':Ridge()})
    monkeypatch.setattr(engine,'compute_feature_importance',lambda *a,**k:{})
    df=pd.DataFrame({'entity':np.repeat(np.arange(20),5),'x':np.arange(100,dtype=float),'target':np.arange(100)*3.})
    a=engine.run_automl(df,'target','p',run_tuning=False,split_strategy='grouped',group_column='entity')
    b=engine.run_automl(df,'target','p',run_tuning=False,split_strategy='grouped',group_column='entity')
    assert a['evaluation']['group_overlap']==0 and 'entity' not in a['feature_columns']
    assert a['best_model']['primary_metric']>a['baseline']['primary_metric']
    assert a['saved_model_path']!=b['saved_model_path']
    assert a['diagnostic_chart']['type']=='residuals'
    assert performance_warnings(.1,0,.8,'regression')
    from backend.services.dataset_views import model_dataframe
    clean=df.iloc[:50].copy();out,target,clip=model_dataframe(dict(df=df,df_cleaned=clean,explicit_cleaning=True),'target')
    assert out.equals(clean)


def test_forecasting_backtests_gaps_and_future_intervals():
    dates=pd.date_range('2010-01-01',periods=96,freq='MS');values=100+np.arange(96)*2+15*np.sin(np.arange(96)*np.pi/6)
    df=pd.DataFrame({'date':dates,'value':values});settings=dict(date_column='date',target_column='value',horizon=6,season_length=12,frequency='MS')
    result=forecast(df,settings,'p')
    assert len(result['forecast'])==6 and result['forecast'][0]['date']>'2017-12'
    assert result['evaluation']['validation_origins']==2 and result['evaluation']['test_used_for_selection'] is False
    assert all(r['lower']<=r['predicted']<=r['upper'] for r in result['forecast'])
    gapped=df.drop(index=20)
    with pytest.raises(ValueError,match='no outcome'):forecast(gapped,settings,'p')
    result=forecast(gapped,dict(settings,missing_policy='forward_fill'),'p')
    assert result['evaluation']['missing_periods']==1
    assert result['history'][20]['value']==result['history'][19]['value']
    with pytest.raises(ValueError,match='Need at least'):forecast(df.iloc[:25],settings,'p')


def test_text_grouping_per_class_and_saved_predictions(tmp_path,monkeypatch):
    monkeypatch.setattr(specialized,'ARTIFACTS_DIR',tmp_path)
    data=pd.DataFrame({'message':[f'normal meeting agenda number {i}' for i in range(40)]+[f'win free prize cash now number {i}' for i in range(40)],'label':['ham']*40+['spam']*40})
    data=pd.concat([data,data.iloc[:20]],ignore_index=True)
    result=text_classification(data,dict(text_column='message',target_column='label'),'p')
    assert result['evaluation']['group_overlap']==0
    assert len(result['per_class'])==2 and sum(r['support'] for r in result['per_class'])==result['evaluation']['holdout_rows']
    assert result['best_model']['primary_metric']>.9
    import joblib
    pipeline=joblib.load(result['saved_model_path'])['pipeline']
    assert pipeline.predict(['win free cash prize now'])[0]=='spam'


def test_custom_reports_templates_and_downloads(client,accounts):
    a,b=accounts
    pid=client.post('/api/profile',headers=a,files={'file':('report.csv',b'category,value\na,2\nb,3\nc,4\n','text/csv')}).json()['project_id']
    base='/api/workspace/'+pid
    evidence=client.get(base+'/report-evidence',headers=a).json()
    settings=dict(title='Quarterly <report>',organization='Test brand',accent='#2255aa',context='Independent review',commentary='Data supports <only> descriptive conclusions.',chart_ids=['missing'])
    built=client.post(base+'/reports',headers=a,json=dict(settings=settings,version_id=evidence['version_id']))
    assert built.status_code==200,built.text
    rid=built.json()['report_id']
    for fmt in ('pdf','pptx'):
        url=base+f'/reports/{rid}/{fmt}/download'
        assert client.get(url,headers=b).status_code==404
        content=client.get(url,headers=a).content
        if fmt=='pdf':assert content.startswith(b'%PDF')
        else:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                assert any(n.startswith('ppt/media') for n in z.namelist())
                assert b'Test brand' in z.read('ppt/slides/slide1.xml')
    assert client.post('/api/report-templates',headers=a,json=dict(name='My report',settings=settings)).status_code==200
    assert any(t['name']=='My report' for t in client.get('/api/report-templates',headers=a).json())
    assert not client.get('/api/report-templates',headers=b).json()
    assert client.post(base+'/reports',headers=a,json=dict(settings=settings,version_id=str(uuid.uuid4()))).status_code==409
