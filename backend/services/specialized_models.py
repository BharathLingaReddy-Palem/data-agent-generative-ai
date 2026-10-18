"""Dedicated text and time-series workflows with training-only model selection."""
import uuid
import numpy as np
import pandas as pd
import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import StratifiedGroupKFold, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, f1_score, mean_absolute_error, mean_squared_error
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from backend.config import ARTIFACTS_DIR
from backend.services.serializer import sanitize_for_json
from backend.services.evaluation import performance_warnings
from backend.services.model_tools import probability_diagnostics


def text_classification(df, settings, project_id, progress=lambda *a:None):
    text,label=settings.get('text_column'),settings.get('target_column')
    if text not in df or label not in df or text==label:
        raise ValueError('Select different text and label columns.')
    progress(5,'Validating text and classes')
    data=df.loc[df[text].notna() & df[label].notna(),[text,label]].copy()
    data[text]=data[text].astype(str).str.strip()
    data=data.loc[data[text].ne('')].reset_index(drop=True)
    y=data[label].astype(str).to_numpy(); X=data[text]
    if not 2<=len(set(y))<=30 or len(data)<30:
        raise ValueError('Text classification needs at least 30 labeled messages and 2–30 classes.')
    if X.str.len().max()>100000 or X.str.len().sum()>20000000:
        raise ValueError('Text is too large. Keep individual messages under 100,000 characters and total text under 20 million characters.')
    groups=X.str.lower().str.replace(r'\s+',' ',regex=True).to_numpy()
    if any(len(set(groups[y==c]))<10 for c in set(y)):
        raise ValueError('Provide at least ten distinct messages per class for separate training, validation and holdout groups.')
    train,test=next(StratifiedGroupKFold(5,shuffle=True,random_state=42).split(X,y,groups))
    folds=list(StratifiedGroupKFold(3,shuffle=True,random_state=43).split(X.iloc[train],y[train],groups[train]))
    if set(y[train])!=set(y) or any(set(y[train][a])!=set(y) for a,b in folds):
        raise ValueError('The grouped text split is missing a training class. Add more distinct messages per class.')
    candidates={ 'TF-IDF + Logistic Regression':LogisticRegression(max_iter=1000,class_weight='balanced',random_state=42),
        'TF-IDF + Naive Bayes':MultinomialNB() }
    leaderboard=[]; models={}
    for i,(name,model) in enumerate(candidates.items()):
        progress(20+i*25,'Cross-validating '+name)
        pipeline=Pipeline([('tfidf',TfidfVectorizer(max_features=20000,ngram_range=(1,2),sublinear_tf=True)),('model',model)])
        scores=cross_val_score(pipeline,X.iloc[train],y[train],cv=folds,scoring='f1_macro',error_score='raise')
        leaderboard.append(dict(model_name=name,cv_score_mean=float(scores.mean()),cv_score_std=float(scores.std())))
        models[name]=pipeline
    leaderboard.sort(key=lambda r:r['cv_score_mean'],reverse=True)
    winner=leaderboard[0]; pipeline=models[winner['model_name']]
    progress(75,'Fitting selected text model and evaluating holdout')
    pipeline.fit(X.iloc[train],y[train]); predicted=pipeline.predict(X.iloc[test]); labels=sorted(set(y))
    baseline=DummyClassifier(strategy='most_frequent').fit(np.zeros((len(train),1)),y[train])
    baseline_score=float(f1_score(y[test],baseline.predict(np.zeros((len(test),1))),average='macro',zero_division=0))
    score=float(f1_score(y[test],predicted,average='macro',zero_division=0))
    report=classification_report(y[test],predicted,labels=labels,output_dict=True,zero_division=0)
    mistakes=[dict(text=X.iloc[idx][:1500],actual=str(y[idx]),predicted=str(pred)) for idx,pred in zip(test,predicted) if y[idx]!=pred][:100]
    run_id=str(uuid.uuid4()); folder=ARTIFACTS_DIR/'models'/project_id/run_id;folder.mkdir(parents=True,exist_ok=True)
    probabilities=pipeline.predict_proba(X.iloc[test]); encoded=np.array([labels.index(c) for c in y[test]])
    probability_report=probability_diagnostics(encoded,probabilities,labels)
    path=folder/'text.joblib'; joblib.dump(dict(pipeline=pipeline,kind='text',text_column=text,
        evaluation_data=dict(actual=encoded.tolist(),probabilities=probabilities.tolist(),labels=labels)),path)
    progress(95,'Saving text model and evaluation')
    return sanitize_for_json(dict(run_id=run_id,kind='text',target_column=label,text_column=text,best_model=dict(winner,primary_metric=score,primary_metric_name='f1_macro'),
        baseline=dict(primary_metric=baseline_score,primary_metric_name='f1_macro'),leaderboard=leaderboard,
        per_class=[dict(label=c,**report[c]) for c in labels],misclassified=mistakes,probability_diagnostics=probability_report,
        diagnostic_chart=dict(type='confusion_matrix',matrix=confusion_matrix(y[test],predicted,labels=labels).tolist(),labels=labels),
        warnings=performance_warnings(score,baseline_score,winner['cv_score_mean'],'classification'),
        evaluation=dict(training_rows=len(train),holdout_rows=len(test),cv_folds=3,split_strategy='stratified groups of normalized text',group_overlap=0,
            dropped_rows=len(df)-len(data),preprocessing='TF-IDF fitted inside each training fold',test_used_for_selection=False),saved_model_path=str(path)))


def forecast(df, settings, project_id, progress=lambda *a:None):
    group=settings.get('series_column')
    if group:
        if group not in df or group in (settings.get('date_column'),settings.get('target_column')): raise ValueError('Choose a separate series column.')
        if df[group].isna().any() or not 1<=df[group].nunique()<=20: raise ValueError('Provide 1–20 named series with no missing series labels.')
        results=[]; failures=[]; groups=list(df.groupby(group,sort=False,observed=True))
        for i,(label,frame) in enumerate(groups):
            progress(5+int(i*85/len(groups)),'Forecasting series '+str(label))
            try:
                result=forecast(frame,dict(settings,series_column=None),project_id)
                results.append(dict(series=str(label),**result))
            except (ValueError,RuntimeError) as exc: failures.append(dict(series=str(label),error=str(exc)))
        if not results: raise ValueError('No series could be forecast: '+str(failures))
        total=sum(r['evaluation']['coverage_observations'] for r in results)
        covered=sum(r['evaluation']['covered_observations'] for r in results)
        return sanitize_for_json(dict(run_id=str(uuid.uuid4()),kind='forecast',target_column=settings['target_column'],series_column=group,
            series_results=results,failed_series=failures,
            best_model=dict(model_name='Independent models per series',primary_metric=float(np.mean([r['best_model']['primary_metric'] for r in results])),primary_metric_name='mean_series_mae'),
            baseline=dict(primary_metric=float(np.mean([r['baseline']['primary_metric'] for r in results])),primary_metric_name='mean_series_mae'),
            evaluation=dict(split_strategy='rolling chronological per series',series_count=len(results),failed_series_count=len(failures),holdout_coverage=covered/total,coverage_observations=total),
            warnings=['Series are forecast independently. Overall MAE is an equal-weight average across successful series; this is not a hierarchical reconciliation.']+
                ([f'{len(failures)} series failed validation. Review their errors; they are excluded from the aggregate.'] if failures else [])))
    date,target=settings.get('date_column'),settings.get('target_column')
    freq=settings.get('frequency','MS'); horizon=int(settings.get('horizon',12)); season=int(settings.get('season_length',12))
    if date not in df or target not in df or date==target: raise ValueError('Select different date and numeric outcome columns.')
    if freq not in ('D','W-MON','MS','QS','YS') or not 1<=horizon<=60 or not 1<=season<=52:
        raise ValueError('Choose a supported frequency, a horizon of 1–60 and a seasonal period of 1–52.')
    aggregation=settings.get('aggregation','mean'); missing=settings.get('missing_policy','reject')
    if aggregation not in ('mean','sum') or missing not in ('reject','forward_fill'):
        raise ValueError('Choose mean/sum aggregation and reject/forward-fill missing periods.')
    progress(5,'Building a regular calendar')
    dates=pd.to_datetime(df[date],format='mixed',errors='coerce')
    numbers=pd.to_numeric(df[target],errors='coerce').replace([np.inf,-np.inf],np.nan)
    if dates.isna().any() or (df[target].notna() & numbers.isna()).any():
        raise ValueError('Clean invalid dates or nonnumeric outcomes before forecasting.')
    raw=pd.Series(numbers.to_numpy(),index=pd.DatetimeIndex(dates)).sort_index()
    resampler=raw.resample(freq)
    series=resampler.sum(min_count=1) if aggregation=='sum' else resampler.mean()
    if len(series)>5000: raise ValueError('Use a coarser frequency; forecasting supports up to 5,000 periods.')
    gaps=int(series.isna().sum()); observed=series.notna()
    if gaps and missing=='reject': raise ValueError(f'{gaps} periods have no outcome. Choose forward-fill or clean the data.')
    # Causal filling: a future observed value is never used to fill an earlier period.
    series=series.ffill() if missing=='forward_fill' else series
    if series.isna().any(): raise ValueError('The first period has no outcome; provide its value before forward filling.')
    minimum=max(12,2*season)
    windows=int(settings.get('backtest_windows',2))
    if not 2<=windows<=10: raise ValueError('Choose 2–10 validation/backtest windows, plus one independent final holdout.')
    if len(series)<minimum+(windows+1)*horizon:
        raise ValueError(f'Need at least {minimum+(windows+1)*horizon} periods for {windows} backtest windows plus a final holdout. Reduce the horizon, windows or season length.')
    if float(series.std())==0: raise ValueError('A constant outcome cannot support meaningful model comparison.')
    def predict(name,values,n):
        if name=='Seasonal naive': return np.resize(np.asarray(values)[-season:],n)
        if name=='Last value': return np.repeat(values.iloc[-1],n)
        model=ExponentialSmoothing(values,trend='add',seasonal='add' if season>1 else None,
            seasonal_periods=season if season>1 else None,initialization_method='estimated').fit(optimized=True)
        return np.asarray(model.forecast(n))
    candidates=['Seasonal naive','Last value','Exponential smoothing']; scores=[]; all_errors={}; failures=[]
    origins=[len(series)-(windows+1)*horizon+i*horizon for i in range(windows+1)]
    selection_count=max(2,windows//2)
    selection_origins=origins[:selection_count];calibration_origins=origins[selection_count:-1]
    for j,name in enumerate(candidates):
        progress(15+j*20,'Rolling backtests: '+name)
        try:
            errors=[]; folds=[]
            for origin in selection_origins:
                pred=predict(name,series.iloc[:origin],horizon); truth=series.iloc[origin:origin+horizon].to_numpy()
                mask=observed.iloc[origin:origin+horizon].to_numpy()
                if not mask.any(): raise ValueError('A backtest contains no observed outcomes. Clean the missing periods or reduce the horizon.')
                errors.append(np.where(mask,truth-pred,np.nan))
                folds.append(dict(training_end=series.index[origin-1].isoformat(),start=series.index[origin].isoformat(),mae=float(np.mean(np.abs(truth[mask]-pred[mask])))))
            all_errors[name]=np.asarray(errors)
            scores.append(dict(model_name=name,validation_mae=float(np.nanmean(np.abs(errors))),backtests=folds))
        except (ValueError,RuntimeError) as exc: failures.append(dict(model_name=name,error=str(exc)))
    if not scores: raise ValueError('No forecasting model could be evaluated. '+str(failures))
    scores.sort(key=lambda r:r['validation_mae']); winner=scores[0]; name=winner['model_name']; origin=origins[-1]
    progress(80,'Evaluating the final chronological holdout')
    pred=predict(name,series.iloc[:origin],horizon); truth=series.iloc[origin:].to_numpy(); mask=observed.iloc[origin:].to_numpy()
    if not mask.any(): raise ValueError('The final holdout has no observed outcomes.')
    baseline=predict('Seasonal naive',series.iloc[:origin],horizon)
    mae=float(mean_absolute_error(truth[mask],pred[mask])); base_mae=float(mean_absolute_error(truth[mask],baseline[mask]))
    future=predict(name,series,horizon)
    # Freeze the model before later interval-calibration windows. Final holdout is not used to set widths.
    errors=all_errors[name]
    if calibration_origins:
        calibration_errors=[]
        for at in calibration_origins:
            forecasted=predict(name,series.iloc[:at],horizon);actual=series.iloc[at:at+horizon].to_numpy();valid=observed.iloc[at:at+horizon].to_numpy()
            calibration_errors.append(np.where(valid,actual-forecasted,np.nan))
        errors=np.asarray(calibration_errors)
        if not np.isfinite(errors).any(): raise ValueError('Interval calibration windows contain no observed outcomes.')
    widths=[]
    for i in range(horizon):
        pool=np.abs(errors[:,i]); pool=pool[np.isfinite(pool)]
        if not len(pool): pool=np.abs(errors[np.isfinite(errors)])
        level=min(1,np.ceil((len(pool)+1)*.95)/len(pool))
        widths.append(float(np.quantile(pool,level,method='higher')))
    dates_future=pd.date_range(series.index[-1],periods=horizon+1,freq=freq)[1:]
    covered=np.abs(truth-pred)<=np.asarray(widths)
    coverage=float(covered[mask].mean())
    warnings=[f'Intervals target 95% using {len(calibration_origins) or selection_count} rolling error windows. Measured final-holdout coverage is {coverage:.1%} over {int(mask.sum())} observed periods; future coverage is not guaranteed.']
    if not calibration_origins: warnings.append('With only two windows, interval estimation reuses model-selection windows. Increase backtest windows for separate calibration.')
    if coverage<.9: warnings.append('Interval coverage is below 90% on the final holdout. Treat uncertainty bands cautiously.')
    if gaps: warnings.append(f'{gaps} missing periods were forward-filled using past values. Imputed outcomes are excluded from evaluation.')
    if mae>=base_mae: warnings.append('Final holdout does not beat the seasonal naive baseline. Review this forecast before making decisions.')
    if mae>winner['validation_mae']*1.5: warnings.append('Holdout error is much higher than rolling validation error; the recent pattern may have changed.')
    progress(95,'Saving forecast and intervals')
    return sanitize_for_json(dict(run_id=str(uuid.uuid4()),kind='forecast',target_column=target,date_column=date,
        best_model=dict(model_name=name,primary_metric=mae,primary_metric_name='mae'),baseline=dict(primary_metric=base_mae,primary_metric_name='mae'),
        leaderboard=scores,failed_models=failures,warnings=warnings,
        horizon_errors=[dict(horizon=i+1,calibration_mae=float(np.nanmean(np.abs(errors[:,i]))) if np.isfinite(errors[:,i]).any() else None,
            calibration_observations=int(np.isfinite(errors[:,i]).sum()),holdout_absolute_error=float(abs(truth[i]-pred[i])) if mask[i] else None,
            covered=bool(covered[i]) if mask[i] else None,interval_width=2*widths[i]) for i in range(horizon)],
        evaluation=dict(split_strategy='rolling chronological',validation_origins=selection_count,calibration_origins=len(calibration_origins),backtest_windows=windows,
            holdout_coverage=coverage,coverage_observations=int(mask.sum()),covered_observations=int(covered[mask].sum()),mean_interval_width=float(2*np.mean(widths)),
            holdout_periods=horizon,missing_periods=gaps,aggregation=aggregation,frequency=freq,test_used_for_selection=False,
            holdout_mae=mae,holdout_rmse=float(np.sqrt(mean_squared_error(truth[mask],pred[mask])))),
        history=[dict(date=d.isoformat(),value=float(v),imputed=not bool(o)) for d,v,o in zip(series.index,series,observed)],
        holdout=[dict(date=d.isoformat(),actual=float(v) if o else None,predicted=float(p),lower=float(p-w),upper=float(p+w),covered=bool(c) if o else None) for d,v,p,o,w,c in zip(series.index[origin:],truth,pred,mask,widths,covered)],
        forecast=[dict(date=d.isoformat(),predicted=float(v),lower=float(v-w),upper=float(v+w)) for d,v,w in zip(dates_future,future,widths)],
        interval_method='Finite-sample corrected 95th percentile absolute error per horizon from rolling calibration windows; fallback pooled errors when a horizon is unobserved. Coverage is measured on the separate final holdout.'))
