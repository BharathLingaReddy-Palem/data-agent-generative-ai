"""Authenticated versioned workspace endpoints, using the existing durable queue."""
import uuid
import threading
from pathlib import Path
from typing import Any, Literal
from fastapi import Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from backend.services.workspace_store import WorkspaceStore
from backend.services.workspace_data import workspace_frame, transform, frame_summary, preview_token, explore, cleaning_options
from backend.services.specialized_models import forecast, text_classification
from backend.services.custom_reports import export_reports, validate_settings
from backend.services.serializer import sanitize_for_json
from backend.config import ARTIFACTS_DIR, REPORTS_DIR

workspace_store=WorkspaceStore()
mutation_lock=threading.RLock()


class CleanPlan(BaseModel):
    model_config={'extra':'forbid'}
    protected_target: str | None=None
    sentinels: list[dict[str,Any]]=Field(default_factory=list,max_length=100)
    types: dict[str,str]=Field(default_factory=dict)
    rename: dict[str,str]=Field(default_factory=dict)
    drop_columns: list[str]=Field(default_factory=list)
    trim_text: bool=False
    coerce_invalid: bool=False
    remove_duplicates: bool=False
    missing: dict[str,dict[str,Any]]=Field(default_factory=dict)
    categories: dict[str,dict[str,Any]]=Field(default_factory=dict)
    date_formats: dict[str,str]=Field(default_factory=dict)


class CleanChange(BaseModel):
    plan: CleanPlan
    revision: int
    preview_token: str | None=None
    label: str=Field(default='Cleaned version',min_length=1,max_length=100)


class VersionChange(BaseModel):
    version_id: str | None=None
    revision: int


class ReportChange(BaseModel):
    settings: dict[str,Any]
    version_id: str


class TemplateChange(BaseModel):
    name: str
    settings: dict[str,Any]


class ModelChange(BaseModel):
    settings: dict[str,Any]

class RecipeChange(BaseModel):
    name: str=Field(min_length=1,max_length=100)
    plan: CleanPlan


def public_run(run):
    return {k:v for k,v in run.items() if k!='saved_model_path'}


def install(app, host):
    auth=host['current_user']; owned=host['owned_session']; persist=host['cache_session']; queue=host['job_queue']
    def session_for(pid,user):
        session=owned(pid,user)
        with mutation_lock:
            if not session.get('active_version_id'):
                workspace_store.ensure(session);persist(pid,session)
        return session
    def validate_change(session,revision):
        if queue.has_pending(session['project_id']): raise HTTPException(409,'Wait for current work before changing dataset versions.')
        if revision!=session.get('revision',0): raise HTTPException(409,'The dataset changed. Refresh and preview again.')
    def activate(session,frame,version_id):
        session.update(df_cleaned=frame,active_version_id=version_id,explicit_cleaning=True,
            revision=session.get('revision',0)+1,model_invalidated=True)
        for key in ('analysis','automl','cleaning_options','cleaning_target_source','forecast','text'):
            session.pop(key,None)
        persist(session['project_id'],session)
    def workspace_payload(session):
        return sanitize_for_json(dict(project_id=session['project_id'],revision=session.get('revision',0),
            active_version_id=session['active_version_id'],versions=workspace_store.versions(session),
            columns=list(workspace_frame(session)),summary=frame_summary(workspace_frame(session)),
            preview=explore(workspace_frame(session),{'limit':8})['rows'],
            runs=[public_run(r) for r in workspace_store.runs(session)],jobs=queue.latest_for_project(session['project_id'])))
    def run_bundle(pid,user,rid):
        session=session_for(pid,user)
        run=next((r for r in workspace_store.runs(session) if r['run_id']==rid),None)
        if not run or not run.get('saved_model_path'): raise HTTPException(404,'Model run not found.')
        path=Path(run['saved_model_path']).resolve();root=(ARTIFACTS_DIR/'models'/pid).resolve()
        if not path.is_relative_to(root) or not path.is_file(): raise HTTPException(404,'Model artifact unavailable.')
        import joblib
        return session,run,joblib.load(path)
    def invalid(exc):
        return HTTPException(400,str(exc))

    @app.get('/api/workspace/{project_id}')
    def workspace(project_id:str,user=Depends(auth)):
        return workspace_payload(session_for(project_id,user))

    @app.get('/api/workspace/{project_id}/workflow')
    def workflow(project_id:str,user=Depends(auth)):
        session=session_for(project_id,user);versions=workspace_store.versions(session);runs=workspace_store.runs(session)
        active=session['active_version_id'];current=next(v for v in versions if v['id']==active)
        return dict(active_version_id=active,version_number=next(i+1 for i,v in enumerate(versions) if v['id']==active),version_label=current['label'],revision=session.get('revision',0),
            current_runs=sum(r['version_id']==active for r in runs),outdated_runs=sum(r['version_id']!=active for r in runs),analysis_available=bool(session.get('analysis')))

    @app.get('/api/cleaning-recipes')
    def recipes(user=Depends(auth)): return workspace_store.recipes(user['id'])

    @app.post('/api/cleaning-recipes')
    def save_recipe(request:RecipeChange,user=Depends(auth)):
        try: return dict(id=workspace_store.save_recipe(user['id'],request.name,request.plan.model_dump()))
        except ValueError as exc: raise invalid(exc)

    @app.post('/api/workspace/{project_id}/clean/preview')
    def preview(project_id:str,request:CleanChange,user=Depends(auth)):
        with mutation_lock:
            session=session_for(project_id,user);validate_change(session,request.revision)
            plan=request.plan.model_dump()
            try:
                before=workspace_frame(session);changes=[];after,steps=transform(before,plan,changes)
                token=preview_token(session['active_version_id'],request.revision,plan)
                # A token is only valid if the server has actually produced this preview.
                session['clean_preview_token']=token;persist(project_id,session)
                return sanitize_for_json(dict(before=frame_summary(before),after=frame_summary(after),steps=steps,
                    before_rows=explore(before,{'limit':8})['rows'],after_rows=explore(after,{'limit':8})['rows'],preview_token=token,
                    changes=changes[:100],change_count=len(changes),audit_note='Rows are 1-based source data rows, excluding the header. Preview shows the first 100 changes. Download the full audit before applying.'))
            except (ValueError,TypeError,KeyError) as exc: raise invalid(exc)

    @app.get('/api/workspace/{project_id}/clean/options')
    def guided_cleaning_options(project_id:str,column:str,user=Depends(auth)):
        session=session_for(project_id,user)
        try: return dict(**cleaning_options(workspace_frame(session),column),revision=session.get('revision',0))
        except (ValueError,TypeError,KeyError) as exc: raise invalid(exc)

    @app.post('/api/workspace/{project_id}/clean/preview-audit')
    def preview_audit(project_id:str,request:CleanChange,user=Depends(auth)):
        import pandas as pd
        with mutation_lock:
            session=session_for(project_id,user);validate_change(session,request.revision)
            plan=request.plan.model_dump();token=preview_token(session['active_version_id'],request.revision,plan)
            if request.preview_token!=token or session.get('clean_preview_token')!=token:
                raise HTTPException(409,'Preview these exact changes before downloading their audit.')
            try:
                changes=[];transform(workspace_frame(session),plan,changes)
                return Response(pd.DataFrame(changes,columns=['row','column','operation','before','after']).to_csv(index=False),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="preview_changes.csv"'})
            except (ValueError,TypeError,KeyError) as exc: raise invalid(exc)

    @app.post('/api/workspace/{project_id}/clean/apply')
    def apply(project_id:str,request:CleanChange,user=Depends(auth)):
        with mutation_lock:
            session=dict(session_for(project_id,user));validate_change(session,request.revision)
            plan=request.plan.model_dump(); token=preview_token(session['active_version_id'],request.revision,plan)
            if not request.preview_token or request.preview_token!=token or session.get('clean_preview_token')!=token:
                raise HTTPException(409,'Preview these exact changes before applying them.')
            try:
                changes=[];frame,steps=transform(workspace_frame(session),plan,changes)
                vid=workspace_store.add_version(session,frame,request.label,steps,session['active_version_id'])
                workspace_store.save_audit(session,vid,changes)
                activate(session,frame,vid);session.pop('clean_preview_token',None)
                return workspace_payload(session)
            except (ValueError,TypeError,KeyError) as exc: raise invalid(exc)

    @app.post('/api/workspace/{project_id}/versions/activate')
    def change_version(project_id:str,request:VersionChange,user=Depends(auth)):
        with mutation_lock:
            session=dict(session_for(project_id,user));validate_change(session,request.revision)
            vid=request.version_id
            if not vid:
                current=next(v for v in workspace_store.versions(session) if v['id']==session['active_version_id'])
                vid=current['parent_version_id']
                if not vid: raise HTTPException(400,'The original version has no earlier transformation to undo.')
            try:
                activate(session,workspace_store.frame(session,vid),vid)
                return workspace_payload(session)
            except ValueError as exc: raise invalid(exc)

    @app.get('/api/workspace/{project_id}/versions/{version_id}/download')
    def version_download(project_id:str,version_id:str,user=Depends(auth)):
        try: frame=workspace_store.frame(session_for(project_id,user),version_id)
        except ValueError as exc: raise HTTPException(404,str(exc))
        return Response(frame.to_csv(index=False),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="version_{version_id}.csv"'})

    @app.get('/api/workspace/{project_id}/versions/{version_id}/audit')
    def audit_download(project_id:str,version_id:str,user=Depends(auth)):
        import pandas as pd
        try: changes=workspace_store.audit(session_for(project_id,user),version_id)
        except ValueError as exc: raise HTTPException(404,str(exc))
        return Response(pd.DataFrame(changes,columns=['row','column','operation','before','after']).to_csv(index=False),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="cleaning_changes.csv"'})

    @app.post('/api/workspace/{project_id}/features')
    def feature_assessment(project_id:str,settings:dict[str,Any],user=Depends(auth)):
        import numpy as np
        import pandas as pd
        from backend.services.automl_engine import validate_automl_input,build_preprocessor,is_identifier_column,_normalize_features
        from backend.services.evaluation import partitions
        try:
            target,task,data=validate_automl_input(workspace_frame(session_for(project_id,user)),settings.get('target_column'),settings.get('task_type'))
            y=data[target].astype(str).to_numpy() if task=='classification' else data[target].to_numpy(dtype=float)
            train,_,_,details=partitions(data,y,task,settings.get('split_strategy','random'),settings.get('group_column'),settings.get('date_column'),settings.get('holdout_fraction',.2))
            frame=data.iloc[train];_,nums,cats=build_preprocessor(_normalize_features(frame.drop(columns=[target])))
            split=settings.get('group_column') if settings.get('split_strategy')=='grouped' else settings.get('date_column') if settings.get('split_strategy')=='chronological' else None
            rows=[]
            for c in frame:
                if c==target: continue
                flags=[];unique=int(frame[c].nunique()); numeric=pd.api.types.is_numeric_dtype(frame[c])
                if is_identifier_column(c): flags.append('Identifier-like name: automatically excluded')
                if numeric and unique/max(len(frame),1)>.95 and frame[c].dropna().mod(1).eq(0).all(): flags.append('Possible numeric ID: review before including')
                if frame[c].astype('string').equals(frame[target].astype('string')): flags.append('Exact target copy: possible leakage')
                if numeric and pd.api.types.is_numeric_dtype(frame[target]):
                    corr=frame[c].corr(frame[target])
                    if pd.notna(corr) and abs(corr)>.995: flags.append('Near-perfect target correlation: inspect availability at prediction time')
                eligible=c in nums+cats and c!=split
                if not eligible: flags.append('Excluded: identifier, split column, constant, date, free text or unsuitable cardinality')
                rows.append(dict(column=c,role='numeric' if numeric else 'categorical/text',unique=unique,missing=int(frame[c].isna().sum()),eligible=eligible,recommended=eligible and not flags,flags=flags))
            return sanitize_for_json(dict(target_column=target,task_type=task,training_rows=len(frame),features=rows,note='Diagnostics use the training partition only. Flags require domain review; correlation does not establish leakage. Automatic selection refits inside every training fold.'))
        except (ValueError,TypeError,KeyError) as exc: raise invalid(exc)

    @app.get('/api/workspace/{project_id}/runs/{run_id}/schema')
    def model_schema(project_id:str,run_id:str,user=Depends(auth)):
        session,run,bundle=run_bundle(project_id,user,run_id)
        text=bundle.get('kind')=='text';prep=bundle['pipeline'].named_steps.get('preprocessor')
        return dict(run_id=run_id,version_id=run['version_id'],outdated=run['version_id']!=session['active_version_id'],
            required_columns=[bundle['text_column']] if text else bundle['feature_names'],numeric_columns=[] if text else prep.numeric_columns_,
            task_type='classification' if text else bundle['task_type'],labels=bundle['pipeline'].classes_.tolist() if text else bundle['label_encoder'].classes_.tolist() if bundle.get('label_encoder') is not None else [])

    @app.post('/api/workspace/{project_id}/runs/{run_id}/threshold')
    def threshold(project_id:str,run_id:str,request:dict[str,Any],user=Depends(auth)):
        from backend.services.model_tools import threshold_metrics
        _,_,bundle=run_bundle(project_id,user,run_id);data=bundle.get('evaluation_data')
        if not data: raise HTTPException(400,'Retrain this model to save probability diagnostics.')
        try: return threshold_metrics(data['actual'],data['probabilities'],data['labels'],request.get('threshold',.5),request.get('positive_index',1))
        except (ValueError,TypeError) as exc: raise invalid(exc)

    @app.post('/api/workspace/{project_id}/runs/{run_id}/explain')
    def explain(project_id:str,run_id:str,request:dict[str,Any],user=Depends(auth)):
        from backend.services.model_tools import explain_prediction
        _,_,bundle=run_bundle(project_id,user,run_id)
        if not isinstance(request.get('record'),dict) or len(str(request))>50000: raise HTTPException(400,'Provide one bounded input record.')
        try: return explain_prediction(bundle,request['record'],request.get('positive_label'))
        except (ValueError,TypeError,KeyError) as exc: raise invalid(exc)

    @app.post('/api/workspace/{project_id}/runs/{run_id}/batch')
    async def batch_predict(project_id:str,run_id:str,file:UploadFile=File(...),threshold:float|None=Form(None),positive_label:str|None=Form(None),user=Depends(auth)):
        from backend.services.upload_limits import read_upload,parse_upload
        from backend.services.model_tools import strict_inference
        session,run,bundle=run_bundle(project_id,user,run_id)
        frame=parse_upload(await read_upload(file),file.filename)
        try:
            predictions,probabilities,labels,warnings=strict_inference(bundle,frame,threshold,positive_label)
            if run['version_id']!=session['active_version_id']: warnings.insert(0,'This saved model belongs to a different dataset version. Prediction uses its original saved schema and preprocessing.')
            prefix='model_'
            while any(c.startswith(prefix) for c in frame): prefix='_'+prefix
            output=frame.copy();output[prefix+'prediction']=predictions
            if probabilities is not None:
                for i,label in enumerate(labels): output[prefix+'probability_'+str(label)]=probabilities[:,i]
                warnings.append('Probabilities are uncalibrated model estimates, not guaranteed confidence.')
            metadata=dict(run_id=run_id,version_id=run['version_id'],count=len(frame),warnings=warnings,threshold=threshold,positive_label=positive_label,prediction_column=prefix+'prediction')
            bid=workspace_store.save_batch(session,metadata,output)
            return sanitize_for_json(dict(batch_id=bid,preview=output.head(100).to_dict('records'),input_preview=frame.head(100).to_dict('records'),**metadata))
        except (ValueError,TypeError,KeyError) as exc: raise invalid(exc)

    @app.get('/api/workspace/{project_id}/batches/{batch_id}/download')
    def batch_download(project_id:str,batch_id:str,user=Depends(auth)):
        try: _,frame=workspace_store.batch(session_for(project_id,user),batch_id)
        except ValueError as exc: raise HTTPException(404,str(exc))
        return Response(frame.to_csv(index=False),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="predictions.csv"'})

    @app.post('/api/workspace/{project_id}/explore')
    def explorer(project_id:str,query:dict[str,Any],user=Depends(auth)):
        try: return explore(workspace_frame(session_for(project_id,user)),query)
        except (ValueError,TypeError,KeyError) as exc: raise invalid(exc)

    def run_special(project_id,owner_id,payload,progress):
        session=host['job_session'](project_id,owner_id,payload)
        settings=payload['settings'];kind=payload['kind']
        result=(forecast if kind=='forecast' else text_classification)(workspace_frame(session).copy(),settings,project_id,progress)
        result=workspace_store.save_run(session,result,kind,settings)
        session[kind]=result;persist(project_id,session)
        return public_run(result)
    def resume_forecast(pid,owner,payload,progress): return run_special(pid,owner,payload,progress)
    host['resume_forecast_job']=resume_forecast;host['resume_text_job']=resume_forecast

    @app.post('/api/workspace/{project_id}/models/{kind}/start')
    def start_model(project_id:str,kind:Literal['forecast','text'],request:ModelChange,user=Depends(auth)):
        with mutation_lock:
            session=session_for(project_id,user)
            if len(str(request.settings))>5000: raise HTTPException(400,'Model settings are too large.')
            payload=dict(settings=request.settings,kind=kind,revision=session.get('revision',0))
            job_id=host['submit_job'](project_id=project_id,owner_id=user['id'],kind=kind,payload=payload,
                fn=lambda **kw:run_special(project_id,user['id'],payload,kw['_progress_callback']),on_progress=True)
            return dict(job_id=job_id,project_id=project_id,status='queued')

    @app.get('/api/workspace/{project_id}/runs/{run_id}/download')
    def run_download(project_id:str,run_id:str,user=Depends(auth)):
        run=next((r for r in workspace_store.runs(session_for(project_id,user)) if r['run_id']==run_id),None)
        if not run or not run.get('saved_model_path'): raise HTTPException(404,'This run has no model artifact.')
        path=Path(run['saved_model_path']).resolve(); root=(ARTIFACTS_DIR/'models'/project_id).resolve()
        if not path.is_relative_to(root) or not path.is_file(): raise HTTPException(404,'Model artifact unavailable.')
        return FileResponse(path,filename=path.name,media_type='application/octet-stream')

    @app.post('/api/workspace/{project_id}/runs/{run_id}/predict-text')
    def predict_text(project_id:str,run_id:str,request:dict[str,str],user=Depends(auth)):
        run=next((r for r in workspace_store.runs(session_for(project_id,user)) if r['run_id']==run_id and r['kind']=='text'),None)
        if not run: raise HTTPException(404,'Text run not found.')
        text=request.get('text','').strip()
        if not text or len(text)>100000: raise HTTPException(400,'Enter 1–100,000 characters.')
        import joblib
        bundle=joblib.load(run['saved_model_path']);pipeline=bundle['pipeline']
        return dict(prediction=str(pipeline.predict([text])[0]),probabilities=sanitize_for_json(pipeline.predict_proba([text])[0]),labels=pipeline.classes_.tolist())

    def evidence(session):
        frame=workspace_frame(session); charts=[]
        for i,c in enumerate(session.get('analysis',{}).get('charts',[])):
            charts.append(dict(id='analysis-'+str(i),title=c['title'],figure=dict(data=c.get('data',[]),layout=c.get('layout',{}))))
        # Instant report evidence also works before any LLM analysis.
        from backend.services.profiler import numeric_analysis_columns
        for c in numeric_analysis_columns(frame)[:8]:
            charts.append(dict(id='distribution-'+str(frame.columns.get_loc(c)),title='Distribution · '+c,
                figure=dict(data=[dict(type='histogram',x=frame[c].dropna().tolist())],layout={})))
        missing=frame.isna().sum()
        charts.append(dict(id='missing',title='Missing values by column',figure=dict(data=[dict(type='bar',x=list(frame),y=missing.tolist())],layout={})))
        return sanitize_for_json(charts)

    @app.get('/api/workspace/{project_id}/report-evidence')
    def report_evidence(project_id:str,user=Depends(auth)):
        session=session_for(project_id,user)
        return dict(version_id=session['active_version_id'],charts=evidence(session))

    @app.post('/api/workspace/{project_id}/reports')
    def build_report(project_id:str,request:ReportChange,user=Depends(auth)):
        session=session_for(project_id,user)
        if request.version_id!=session['active_version_id']: raise HTTPException(409,'The dataset changed. Refresh report evidence.')
        try: return export_reports(project_id,session['active_version_id'],request.settings,evidence(session))
        except (ValueError,TypeError) as exc: raise invalid(exc)

    @app.get('/api/workspace/{project_id}/reports/{report_id}/{format}/download')
    def custom_download(project_id:str,report_id:str,format:Literal['pdf','pptx'],user=Depends(auth)):
        owned(project_id,user)
        try:
            if str(uuid.UUID(report_id))!=report_id: raise ValueError()
        except ValueError: raise HTTPException(404,'Report unavailable.')
        path=REPORTS_DIR/project_id/'custom'/report_id/('report.'+format)
        if not path.is_file(): raise HTTPException(404,'Report unavailable.')
        return FileResponse(path,filename=path.name,media_type='application/pdf' if format=='pdf' else 'application/vnd.openxmlformats-officedocument.presentationml.presentation')

    @app.get('/api/report-templates')
    def templates(user=Depends(auth)): return workspace_store.templates(user['id'])

    @app.post('/api/report-templates')
    def save_template(request:TemplateChange,user=Depends(auth)):
        try:
            validate_settings(request.settings)
            return dict(id=workspace_store.save_template(user['id'],request.name,request.settings))
        except ValueError as exc: raise invalid(exc)
