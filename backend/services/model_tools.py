"""Training-fold feature selection, honest probability diagnostics and strict inference."""
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve, average_precision_score, confusion_matrix, precision_score, recall_score, f1_score
from backend.services.serializer import sanitize_for_json


def probability_diagnostics(y, probabilities, labels):
    y=np.asarray(y); p=np.asarray(probabilities,dtype=float)
    if p.ndim!=2 or len(p)!=len(y) or not np.isfinite(p).all(): return None
    curves=[]; calibration=[]; metrics=[]
    for i,label in enumerate(labels):
        truth=(y==i).astype(int); scores=p[:,i]
        if truth.any() and not truth.all():
            precision,recall,thresholds=precision_recall_curve(truth,scores)
            indices=np.unique(np.linspace(0,len(precision)-1,min(200,len(precision)),dtype=int))
            curves.append(dict(label=str(label),precision=precision[indices].tolist(),recall=recall[indices].tolist(),average_precision=float(average_precision_score(truth,scores))))
        bins=[]; ece=0.
        # Assign each row once, including exact decimal boundaries and probability 1.
        assignments=np.minimum((scores*10).astype(int),9)
        for index in range(10):
            mask=assignments==index
            if mask.any():
                predicted=float(scores[mask].mean()); observed=float(truth[mask].mean()); count=int(mask.sum())
                bins.append(dict(predicted=predicted,observed=observed,count=count));ece+=count/len(y)*abs(predicted-observed)
        calibration.append(dict(label=str(label),bins=bins))
        metrics.append(dict(label=str(label),brier_score=float(np.mean((scores-truth)**2)),ece=ece))
    return sanitize_for_json(dict(labels=list(labels),precision_recall=curves,calibration=calibration,metrics=metrics,
        probability_status='Uncalibrated model probabilities; reliability measured on final holdout. Do not interpret as guaranteed confidence.',
        warning='Small holdouts give noisy calibration estimates. Threshold exploration reuses holdout data and is not an independent evaluation.'))


def threshold_metrics(y, probabilities, labels, threshold=.5, positive_index=1):
    if len(labels)!=2: raise ValueError('Threshold adjustment currently supports binary classification only.')
    threshold=float(threshold)
    if not 0<=threshold<=1 or not np.isfinite(threshold): raise ValueError('Threshold must be between zero and one.')
    if positive_index not in (0,1): raise ValueError('Choose a valid positive class.')
    actual=(np.asarray(y)==positive_index).astype(int)
    pred=(np.asarray(probabilities)[:,positive_index]>=threshold).astype(int)
    return dict(threshold=threshold,positive_label=str(labels[positive_index]),precision=float(precision_score(actual,pred,zero_division=0)),
        recall=float(recall_score(actual,pred,zero_division=0)),f1=float(f1_score(actual,pred,zero_division=0)),
        matrix=confusion_matrix(actual,pred,labels=[0,1]).tolist(),labels=[str(labels[1-positive_index]),str(labels[positive_index])],
        warning='Exploratory holdout threshold analysis. Choose the production threshold using validation data and evaluate on new untouched data.')


def strict_inference(bundle, frame, threshold=None, positive_label=None):
    if not len(frame) or len(frame)>10000: raise ValueError('Batch prediction requires 1–10,000 rows.')
    pipeline=bundle['pipeline']; is_text=bundle.get('kind')=='text'
    expected=[bundle['text_column']] if is_text else bundle.get('feature_names',[])
    missing=[c for c in expected if c not in frame]
    if missing: raise ValueError('Missing required columns: '+', '.join(missing)+'. Use the saved model schema; columns are not silently inserted.')
    warnings=[]
    extra=[c for c in frame if c not in expected]
    if extra: warnings.append('Extra columns are retained in output and ignored by the model: '+', '.join(extra))
    if is_text:
        if frame[expected[0]].isna().any() or frame[expected[0]].astype(str).str.strip().eq('').any(): raise ValueError('Text input contains empty messages.')
        X=frame[expected[0]].astype(str)
        if X.str.len().max()>100000 or X.str.len().sum()>20000000: raise ValueError('Text input exceeds the model text limits.')
        task='classification';encoder=None; labels=[str(c) for c in pipeline.classes_]
    else:
        X=frame[expected].copy();task=bundle['task_type'];encoder=bundle.get('label_encoder')
        prep=pipeline.named_steps['preprocessor']
        for c in prep.numeric_columns_:
            converted=pd.to_numeric(X[c].replace('',np.nan),errors='coerce')
            invalid=X[c].notna() & (converted.isna() | ~np.isfinite(converted))
            if invalid.any(): raise ValueError(f'{c}: {int(invalid.sum())} invalid numeric values. Clean these values before prediction.')
            X[c]=converted
        for c in prep.categorical_columns_:
            X[c]=X[c].map(lambda v:str(v).strip() if pd.notna(v) else np.nan).replace('',np.nan)
        if X.isna().any().any(): warnings.append('Missing feature values use the saved training-fold imputation; prediction does not refit preprocessing.')
        if prep.categorical_columns_:
            cats=prep.transformer_.named_transformers_['cat'].named_steps['encoder'].categories_
            for c,known in zip(prep.categorical_columns_,cats):
                count=int((X[c].notna() & ~X[c].isin(known)).sum())
                if count: warnings.append(f'{c}: {count} unseen category values use the saved unknown-category handling.')
        labels=encoder.classes_.tolist() if encoder is not None else []
    predicted=pipeline.predict(X); probabilities=pipeline.predict_proba(X) if task=='classification' and hasattr(pipeline,'predict_proba') else None
    if encoder is not None: predicted=encoder.inverse_transform(predicted.astype(int))
    if threshold is not None:
        if probabilities is None or len(labels)!=2: raise ValueError('A custom threshold requires a binary model with probabilities.')
        if positive_label is not None and positive_label not in labels: raise ValueError('Choose a positive class from the saved model labels.')
        index=labels.index(positive_label) if positive_label in labels else 1
        threshold=float(threshold)
        if not 0<=threshold<=1 or not np.isfinite(threshold): raise ValueError('Threshold must be between zero and one.')
        predicted=np.where(probabilities[:,index]>=threshold,labels[index],labels[1-index])
    return predicted,probabilities,labels,warnings


def explain_prediction(bundle, record, positive_label=None):
    if bundle.get('kind')=='text': raise ValueError('Individual feature sensitivity currently supports tabular models.')
    refs=bundle.get('reference_values')
    if not refs: raise ValueError('Retrain this older model to save training reference values for explanations.')
    frame=pd.DataFrame([record]); predictions,probabilities,labels,warnings=strict_inference(bundle,frame)
    label=positive_label if positive_label in labels else str(predictions[0])
    index=labels.index(label) if labels else None
    base=float(probabilities[0,index]) if index is not None else float(predictions[0])
    rows=[]
    for c,value in list(refs.items())[:30]:
        changed=frame.copy();changed[c]=value
        pred,probs,_,_=strict_inference(bundle,changed)
        score=float(probs[0,index]) if index is not None else float(pred[0])
        rows.append(dict(feature=c,value=record.get(c),training_reference=value,score_with_reference=score,difference=base-score))
    rows.sort(key=lambda r:abs(r['difference']),reverse=True)
    return sanitize_for_json(dict(prediction=predictions[0],score=base,class_label=label if labels else None,features=rows,
        method='One feature at a time replaced by its training median or mode. Differences are sensitivity measures, not additive SHAP values or causal effects.',warnings=warnings))
