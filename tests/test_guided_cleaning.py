import numpy as np
import pandas as pd
import pytest
from backend.services.workspace_data import cleaning_options,transform


def test_observed_choices_preserve_values_and_only_suggest_placeholders():
    df=pd.DataFrame({'Amount':[-200.,10.,None,20.],'category':[' YES ','yes','unknown','éCOLE']})
    options=cleaning_options(df,'Amount')
    assert options['kind']=='number' and options['missing_count']==1
    assert options['sentinels']==[{'value':-200.,'count':1}]
    assert options['rename_suggestion']=='amount'
    text=cleaning_options(df,'category')
    assert any(v['value']==' YES ' and v['normalized']['lower']=='yes' for v in text['values'])
    assert any(v['value']=='éCOLE' and v['normalized']['title']=='École' for v in text['values'])
    assert df.Amount.iloc[0]==-200 and pd.isna(df.Amount.iloc[2])


def test_guided_endpoint_is_version_bound_bounded_and_owned(client,accounts):
    headers,other=accounts
    frame=pd.DataFrame({'Bad Name':['unknown']+['category '+str(i) for i in range(80)],'bad_name':[1]*81})
    pid=client.post('/api/profile',headers=headers,files={'file':('choices.csv',frame.to_csv(index=False),'text/csv')}).json()['project_id']
    path=f'/api/workspace/{pid}/clean/options'
    assert client.get(path,headers=other,params={'column':'Bad Name'}).status_code==404
    assert client.get(path,headers=headers,params={'column':'missing'}).status_code==400
    r=client.get(path,headers=headers,params={'column':'Bad Name'}).json()
    assert r['revision']==0 and len(r['values'])<=30 and r['values_truncated']
    assert r['rename_suggestion']=='bad_name_2'


@pytest.mark.parametrize('replacement',['nan','inf','-inf',np.nan])
def test_custom_numeric_fill_cannot_introduce_nonfinite_values(replacement):
    with pytest.raises(ValueError,match='finite'):
        transform(pd.DataFrame({'x':[1.,None]}),{'missing':{'x':{'strategy':'constant','value':replacement}}})


def test_protected_target_cannot_be_renamed():
    with pytest.raises(ValueError,match='protected target'):
        transform(pd.DataFrame({'target':[0,1],'feature':[2,3]}),{'protected_target':'target','rename':{'target':'outcome'}})


def test_guided_values_build_a_valid_recipe_with_real_cell_audit():
    df=pd.DataFrame({'amount':[-200.,None,10.],'group':[' YES ','yes','no'],'Date':['18/10/2026','19/10/2026','20/10/2026'],'label':[0,1,0]})
    changes=[]
    cleaned,steps=transform(df,dict(protected_target='label',sentinels=[dict(column='amount',values=['-200.0'])],
        missing={'amount':{'strategy':'constant','value':0}},categories={'group':{'case':'lower','mapping':{'yes':'no'}}},
        types={'Date':'date'},date_formats={'Date':'%d/%m/%Y'}),changes)
    assert cleaned.amount.tolist()==[0.,0.,10.] and cleaned.group.tolist()==['no']*3
    assert cleaned.Date.iloc[0].day==18 and cleaned.label.equals(df.label)
    assert sum(c['operation']=='fill_missing_constant' for c in changes)==2


def test_boolean_and_date_replacement_validation():
    frame=pd.DataFrame({'flag':pd.Series([True,None],dtype='boolean')})
    cleaned,_=transform(frame,{'missing':{'flag':{'strategy':'constant','value':False}}})
    assert cleaned.flag.tolist()==[True,False]
    with pytest.raises(ValueError,match='valid replacement date'):
        transform(pd.DataFrame({'day':pd.to_datetime(['2026-10-18',None])}),{'missing':{'day':{'strategy':'constant','value':'NaT'}}})
