"""Explicit reversible transformations and server-side filtered exploration."""
import json
import hashlib
import re
import numpy as np
import pandas as pd
from backend.services.profiler import profile_dataset, numeric_analysis_columns
from backend.services.serializer import sanitize_for_json


def workspace_frame(session):
    return session['df_cleaned'] if session.get('df_cleaned') is not None else session['df']


def cleaning_options(frame, column):
    """Bounded observed choices for guided cleaning; never infer a safe deletion."""
    if column not in frame: raise ValueError('Choose an existing column.')
    series=frame[column]
    kind='boolean' if pd.api.types.is_bool_dtype(series) else 'number' if pd.api.types.is_numeric_dtype(series) else 'date' if pd.api.types.is_datetime64_any_dtype(series) else 'text'
    counts=series.dropna().value_counts().head(30)
    values=[dict(value=value,count=int(count),normalized={case:getattr(str(value).strip(),case)() if case!='preserve' else str(value).strip()
            for case in ('preserve','lower','upper','title')}) for value,count in counts.items() if len(str(value))<=200]
    suspicious_numbers={-99999,-9999,-999,-200,-99,9999,99999}
    suspicious_text={'?','-','n/a','na','null','none','unknown','not available','missing',''}
    candidates=[]
    for value,count in series.dropna().value_counts().items():
        suspicious=value in suspicious_numbers if kind=='number' else str(value).strip().lower() in suspicious_text if kind=='text' else False
        if suspicious and len(str(value))<=200: candidates.append(dict(value=value,count=int(count)))
        if len(candidates)>=20:break
    suggested=re.sub(r'[^\w]+','_',column.strip().lower()).strip('_') or 'column'
    base=suggested;suffix=2
    while suggested in frame.columns and suggested!=column:
        suggested=f'{base}_{suffix}';suffix+=1
    return sanitize_for_json(dict(column=column,kind=kind,missing_count=int(series.isna().sum()),
        unique_count=int(series.nunique()),values=values,sentinels=candidates,rename_suggestion=suggested,
        values_truncated=series.nunique()>len(values),examples=series.dropna().astype(str).head(3).str.slice(0,100).tolist()))


def transform(frame, plan, audit=None):
    out=frame.copy(deep=True).reset_index(drop=True); steps=[]
    def log(column, old, new, operation):
        if audit is None: return
        same=old.eq(new).fillna(False) | (old.isna() & new.isna())
        for i in old.index[~same]:
            audit.append(dict(row=int(i)+1,column=column,operation=operation,before=old.loc[i],after=new.loc[i]))
        if len(audit)>400000: raise ValueError('This recipe exceeds 400,000 audit changes. Apply smaller recipes.')
    def remove(mask, operation):
        nonlocal out
        if audit is not None:
            for i in out.index[mask]: audit.append(dict(row=int(i)+1,column='(row)',operation=operation,before=out.loc[i].to_json(date_format='iso'),after=None))
        out=out.loc[~mask].copy()
    target=plan.get('protected_target')
    if target and target not in out: raise ValueError('Protected target does not exist.')
    def check(column):
        if column not in out: raise ValueError(f"Column '{column}' does not exist.")
        if column==target: raise ValueError(f"'{column}' is the protected target; select a different operation.")
    for item in plan.get('sentinels',[]):
        column=item['column']; check(column)
        values=item.get('values',[])
        if not values or len(values)>100: raise ValueError('Provide between 1 and 100 sentinel values.')
        # Numeric equivalents may be supplied from a text input; text columns keep exact matching.
        if pd.api.types.is_numeric_dtype(out[column]): values=pd.to_numeric(pd.Series(values),errors='raise').tolist()
        mask=out[column].isin(values); count=int(mask.sum())
        old=out[column].copy(); out.loc[mask,column]=np.nan; log(column,old,out[column],'replace_sentinels')
        steps.append(dict(operation='replace_sentinels',column=column,values=values,affected_cells=count))
    for column, dtype in plan.get('types',{}).items():
        check(column); old=out[column]
        if dtype=='number': converted=pd.to_numeric(old,errors='coerce')
        elif dtype=='date': converted=pd.to_datetime(old,format=plan.get('date_formats',{}).get(column) or 'mixed',errors='coerce')
        elif dtype=='string': converted=old.astype('string')
        elif dtype=='boolean': converted=old.astype('string').str.lower().str.strip().map(
            {'true':True,'false':False,'1':True,'0':False,'yes':True,'no':False})
        else: raise ValueError('Choose number, date, string or boolean.')
        invalid=int((old.notna() & converted.isna()).sum())
        if invalid and not plan.get('coerce_invalid',False):
            raise ValueError(f'{column}: {invalid} values cannot convert to {dtype}. Enable explicit conversion of invalid values to missing, or fix them first.')
        out[column]=converted; log(column,old.astype(object),converted.astype(object),'convert_type')
        steps.append(dict(operation='convert_type',column=column,dtype=dtype,invalid_to_missing=invalid))
    if plan.get('trim_text'):
        for column in out.select_dtypes(include=['object','string']):
            if column==target: continue
            old=out[column].copy(); out[column]=old.map(lambda v:v.strip() if isinstance(v,str) else v); log(column,old,out[column],'trim_text')
        steps.append(dict(operation='trim_text'))
    for column,rule in plan.get('categories',{}).items():
        check(column); old=out[column].copy()
        if not isinstance(rule,dict): raise ValueError('Category rules must be objects.')
        case=rule.get('case','preserve'); mapping=rule.get('mapping',{})
        if case not in ('preserve','lower','upper','title') or not isinstance(mapping,dict) or len(mapping)>100:
            raise ValueError('Choose a supported category case and up to 100 explicit mappings.')
        converted=old.astype('string').str.strip()
        if case!='preserve': converted=getattr(converted.str,case)()
        converted=converted.replace(mapping)
        out[column]=converted; log(column,old,converted,'standardize_categories')
        steps.append(dict(operation='standardize_categories',column=column,case=case,mapping=mapping))
    for column,rule in plan.get('missing',{}).items():
        check(column); strategy=rule.get('strategy')
        if strategy=='drop_rows':
            mask=out[column].isna(); count=int(mask.sum());remove(mask,'drop_missing:'+column)
        elif strategy=='constant':
            value=rule.get('value')
            if value is None or isinstance(value,(dict,list)): raise ValueError('Provide a non-missing scalar replacement.')
            if pd.api.types.is_bool_dtype(out[column]):
                normalized=str(value).strip().lower()
                if normalized not in ('true','false','1','0','yes','no'): raise ValueError('Choose true or false for boolean replacement.')
                value=normalized in ('true','1','yes')
            elif pd.api.types.is_numeric_dtype(out[column]):
                value=float(value)
                if not np.isfinite(value): raise ValueError('Numeric replacement must be finite.')
            if pd.api.types.is_datetime64_any_dtype(out[column]):
                value=pd.to_datetime(value,errors='raise')
                if pd.isna(value): raise ValueError('Choose a valid replacement date.')
            old=out[column].copy(); count=int(old.isna().sum()); out[column]=old.fillna(value); log(column,old,out[column],'fill_missing_constant')
        else: raise ValueError('Missing strategy must be constant or drop_rows. Learned imputation belongs inside model training folds.')
        steps.append(dict(operation='handle_missing',column=column,strategy=strategy,affected=count,value=rule.get('value')))
    for column in plan.get('drop_columns',[]):
        check(column)
        if audit is not None:
            for i,value in out[column].items(): audit.append(dict(row=int(i)+1,column=column,operation='drop_column',before=value,after=None))
    if plan.get('drop_columns'):
        out=out.drop(columns=plan['drop_columns']); steps.append(dict(operation='drop_columns',columns=plan['drop_columns']))
    if not len(out.columns): raise ValueError('Keep at least one column.')
    renames=plan.get('rename',{})
    if any(c not in out for c in renames): raise ValueError('A renamed column does not exist.')
    for column in renames: check(column)
    names=[renames.get(c,c).strip() for c in out]
    if any(not n or len(n)>150 for n in names) or len(set(names))!=len(names):
        raise ValueError('Column names must be nonempty, unique, and at most 150 characters.')
    if renames:
        out.columns=names; steps.append(dict(operation='rename',mapping=renames))
        if audit is not None:
            for c,n in renames.items(): audit.append(dict(row=None,column=c,operation='rename_column',before=c,after=n.strip()))
    if plan.get('remove_duplicates'):
        removed=int(out.duplicated().sum()); remove(out.duplicated(),'remove_duplicate')
        steps.append(dict(operation='remove_duplicates',removed_rows=removed))
    if not steps: raise ValueError('Choose at least one transformation before previewing.')
    if audit is not None and len(audit)>400000: raise ValueError('This recipe exceeds 400,000 audit changes. Apply smaller recipes.')
    return out.reset_index(drop=True),steps


def frame_summary(frame):
    return dict(rows=len(frame),columns=len(frame.columns),missing_cells=int(frame.isna().sum().sum()),
                duplicates=int(frame.duplicated().sum()),quality=profile_dataset(frame)['health']['score'])


def preview_token(version_id,revision,plan):
    return hashlib.sha256(json.dumps([version_id,revision,plan],sort_keys=True).encode()).hexdigest()


def explore(frame, query):
    view=frame
    search=query.get('search','').strip()
    if len(search)>200: raise ValueError('Search is limited to 200 characters.')
    if search:
        mask=pd.Series(False,index=view.index)
        for c in view: mask |= view[c].astype('string').str.contains(search,case=False,regex=False,na=False)
        view=view.loc[mask]
    filters=query.get('filters',[])
    if len(filters)>20: raise ValueError('Use at most 20 filters.')
    for f in filters:
        col=f.get('column'); op=f.get('operator','eq'); value=f.get('value')
        if col not in view: raise ValueError('Filter column does not exist.')
        s=view[col]
        if op=='missing': mask=s.isna()
        elif op=='contains': mask=s.astype('string').str.contains(str(value),case=False,regex=False,na=False)
        elif op in ('gte','lte','lt'):
            numeric=pd.to_numeric(s,errors='coerce'); mask=numeric.ge(float(value)) if op=='gte' else numeric.lt(float(value)) if op=='lt' else numeric.le(float(value))
        elif op=='eq': mask=s.astype('string').eq(str(value)).fillna(False)
        else: raise ValueError('Unsupported filter operation.')
        view=view.loc[mask]
    sort=query.get('sort')
    if sort:
        if sort not in view: raise ValueError('Sort column does not exist.')
        view=view.sort_values(sort,ascending=not query.get('descending',False),kind='stable',na_position='last')
    offset=max(0,int(query.get('offset',0))); limit=min(100,max(1,int(query.get('limit',25))))
    category=query.get('category'); metric=query.get('metric')
    cats={}
    if category in view:
        counts=view[category].astype('string').fillna('(missing)').value_counts().head(15)
        cats=dict(labels=counts.index.tolist(),counts=counts.tolist(),column=category)
    histogram={}
    if metric in numeric_analysis_columns(frame):
        arr=pd.to_numeric(view[metric],errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
        if len(arr):
            counts,edges=np.histogram(arr,bins=min(20,max(5,int(np.sqrt(len(arr))))))
            histogram=dict(column=metric,edges=edges.tolist(),centers=((edges[:-1]+edges[1:])/2).tolist(),counts=counts.tolist(),
                mean=float(arr.mean()),median=float(arr.median()))
    return sanitize_for_json(dict(total_rows=len(frame),filtered_rows=len(view),columns=list(view.columns),
        rows=view.iloc[offset:offset+limit].astype(object).where(view.iloc[offset:offset+limit].notna(),None).to_dict('records'),
        offset=offset,limit=limit,missing_cells=int(view.isna().sum().sum()),duplicates=int(view.duplicated().sum()),
        categories=cats,histogram=histogram))
