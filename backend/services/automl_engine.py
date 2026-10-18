"""
automl_engine.py — Comprehensive Multi-Algorithm AutoML Engine
===============================================================
Autonomously detects task type, preprocesses features, benchmarks
multiple competitive algorithms, tunes hyperparameters with Optuna,
evaluates test performance, builds a leaderboard, and saves artifacts.

Supported Models:
- Classification:
  * Logistic Regression
  * Decision Tree Classifier
  * Random Forest Classifier
  * XGBoost Classifier
  * LightGBM Classifier
  * CatBoost Classifier (or GradientBoosting fallback)
- Regression:
  * Linear Regression
  * Ridge & Lasso
  * Random Forest Regressor
  * XGBoost Regressor
  * LightGBM Regressor
"""

import os
import time
import tempfile
import logging
import re
import uuid
from sklearn.dummy import DummyClassifier, DummyRegressor
from backend.services.evaluation import partitions, performance_warnings
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
import joblib
from backend.services.serializer import sanitize_for_json
from backend.config import ARTIFACTS_DIR

from sklearn.model_selection import train_test_split, cross_val_score, KFold, StratifiedKFold
from sklearn.preprocessing import StandardScaler, OneHotEncoder, LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.base import clone, BaseEstimator, TransformerMixin
from sklearn.feature_selection import SelectKBest, f_classif, f_regression
from backend.services.model_tools import probability_diagnostics
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    r2_score,
    mean_squared_error,
    mean_absolute_error,
)

# Linear & Tree Models
from sklearn.linear_model import LogisticRegression, LinearRegression, Ridge, Lasso
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, GradientBoostingClassifier, GradientBoostingRegressor

# Extended Gradient Boosters
try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False

try:
    import catboost as cb
    HAS_CATBOOST = True
except ImportError:
    HAS_CATBOOST = False

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    HAS_OPTUNA = True
except ImportError:
    HAS_OPTUNA = False

from backend.services.xai_service import compute_feature_importance

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. TARGET & TASK DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def is_identifier_column(name):
    """Match identifier tokens without excluding measures such as 'paid' or 'width'."""
    if str(name).strip() == '#':
        return True
    text = re.sub(r"([a-z])([A-Z])", r"\1_\2", str(name)).lower()
    tokens = set(re.split(r"[^a-z0-9]+", text))
    if tokens & {'postal', 'postcode', 'zip', 'zipcode'}:
        return True
    return bool(tokens & {"id", "identifier", "index", "key", "uuid", "serial", "email", "phone", "url", "website", "address"}) or text in {"row", "record", "customerid", "orderid", "userid", "employeeid"} or text.startswith("unnamed") or text.endswith("_number")


def detect_target_and_task(df, requested_target=None, requested_task=None):
    if not isinstance(df, pd.DataFrame) or df.empty or len(df.columns) < 2:
        raise ValueError("AutoML requires a non-empty dataset with a target and at least one feature.")
    if not df.columns.is_unique or not all(isinstance(c, str) for c in df.columns):
        raise ValueError("AutoML requires unique string column names. Clean the column names first.")
    if requested_target is not None and requested_target not in df.columns:
        raise ValueError(f"Target column '{requested_target}' does not exist. Select an existing column.")
    target = requested_target
    if target is None:
        priorities = ["target", "label", "class", "churn", "churned", "status", "outcome", "y", "survived", "profit", "sales", "revenue", "price", "target_salary", "category", "rating", "score", "type"]
        target = next((c for key in priorities for c in df.columns if c.lower() == key), None)
        if target is None:
            raise ValueError("No unambiguous target found. Select a target column explicitly.")
    if is_identifier_column(target):
        raise ValueError("An identifier cannot be used as the prediction target. Select an outcome column.")
    series = df[target].dropna()
    if pd.api.types.is_datetime64_any_dtype(series):
        raise ValueError("A date/time target is unsupported. Select a numeric or categorical outcome.")
    if requested_task not in (None, "classification", "regression"):
        raise ValueError("Task type must be classification or regression.")
    numeric = pd.api.types.is_numeric_dtype(series)
    non_integer = numeric and not np.all(np.equal(np.mod(series.astype(float), 1), 0))
    task = requested_task or ("regression" if numeric and (series.nunique() > 15 or (non_integer and series.nunique() > 2)) else "classification")
    return target, task


def validate_automl_input(df, target_column=None, task_type=None):
    target, task = detect_target_and_task(df, target_column, task_type)
    valid = df[target].notna()
    if df[target].dtype == object:
        valid &= df[target].map(lambda v: not isinstance(v, str) or bool(v.strip()))
    data = df.loc[valid].copy()
    if len(data) < 20:
        raise ValueError("AutoML requires at least 20 rows with non-missing target values.")
    if data[target].nunique() < 2:
        raise ValueError("Target must contain at least two distinct values.")
    if task == "classification":
        counts = data[target].astype(str).value_counts()
        if len(counts) > 20:
            raise ValueError("Classification supports at most 20 classes. Select regression for a continuous numeric target.")
        if counts.min() < 5:
            raise ValueError("Each class needs at least 5 rows for stratified holdout and cross-validation; labels are never merged.")
        if int(np.ceil(len(data) * 0.2)) < len(counts):
            raise ValueError("Too many classes for the holdout size. Add more labeled rows.")
    else:
        numeric = pd.to_numeric(data[target], errors="coerce")
        if not np.isfinite(numeric.to_numpy(dtype=float)).all():
            raise ValueError("Regression targets must be finite numeric values; invalid labels are never imputed.")
    X = data.drop(columns=[target])
    _, nums, cats = build_preprocessor(_normalize_features(X))
    if not nums and not cats:
        raise ValueError("No usable features remain after excluding identifiers, constants, dates and free text.")
    return target, task, data


def _normalize_features(X):
    X = X.copy().replace([np.inf, -np.inf], np.nan)
    for c in X.select_dtypes(include=["object", "string", "category"]).columns:
        X[c] = X[c].astype(object).map(lambda v: str(v).strip() if pd.notna(v) else np.nan).replace("", np.nan)
    return X


# ─────────────────────────────────────────────────────────────────────────────
# 2. DATA PREPROCESSING PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def build_preprocessor(X: pd.DataFrame) -> Tuple[ColumnTransformer, List[str], List[str]]:
    """Builds a scikit-learn ColumnTransformer for numeric and categorical columns."""
    num_cols = [c for c in X.select_dtypes(include=[np.number, "bool"]).columns
                if not is_identifier_column(c) and X[c].notna().any() and X[c].nunique() > 1]
    cat_cols = [c for c in X.select_dtypes(include=["object", "string", "category"]).columns
                if not is_identifier_column(c) and 1 < X[c].nunique() <= 40
                and X[c].nunique() / max(len(X), 1) < 0.35]

    num_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    cat_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", max_categories=25, sparse_output=False)),
    ])

    transformers = []
    if num_cols:
        transformers.append(("num", num_transformer, num_cols))
    if cat_cols:
        transformers.append(("cat", cat_transformer, cat_cols))

    preprocessor = ColumnTransformer(transformers=transformers, remainder="drop")
    return preprocessor, num_cols, cat_cols


class FoldPreprocessor(TransformerMixin, BaseEstimator):
    """Learn selection, clipping, imputation, encoding and scaling within each fold."""
    def __init__(self, clip_outliers=False, include_columns=None, selection_percentile=100, task_type='regression'):
        self.clip_outliers = clip_outliers
        self.include_columns=include_columns
        self.selection_percentile=selection_percentile
        self.task_type=task_type

    def fit(self, X, y=None):
        if self.include_columns is not None: X=X[list(self.include_columns)]
        frame = _normalize_features(X)
        self.transformer_, self.numeric_columns_, self.categorical_columns_ = build_preprocessor(frame)
        if not self.numeric_columns_ and not self.categorical_columns_:
            raise ValueError("No usable features in this training fold. Add informative non-ID features.")
        self.bounds_ = {}
        if self.clip_outliers:
            for c in self.numeric_columns_:
                q1, q3 = frame[c].quantile([0.25, 0.75])
                if q3 > q1:
                    self.bounds_[c] = (q1 - 1.5 * (q3-q1), q3 + 1.5 * (q3-q1))
        self.transformer_.fit(self._clip(frame))
        self.selector_=None
        if self.selection_percentile<100:
            encoded=self.transformer_.transform(self._clip(frame))
            keep=max(1,int(np.ceil(encoded.shape[1]*self.selection_percentile/100)))
            self.selector_=SelectKBest(f_classif if self.task_type=='classification' else f_regression,k=keep)
            self.selector_.fit(encoded,y)
            if not self.selector_.get_support().any(): raise ValueError('Selection retained no encoded features. Increase the selection percentage.')
        self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        return self

    def _clip(self, frame):
        for c, (low, high) in self.bounds_.items():
            frame[c] = frame[c].clip(low, high)
        return frame

    def transform(self, X):
        frame = _normalize_features(X)
        for c in self.numeric_columns_:
            frame[c] = pd.to_numeric(frame[c], errors="coerce")
        for c in self.categorical_columns_:
            frame[c] = frame[c].map(lambda value: str(value).strip() if pd.notna(value) else np.nan).replace("", np.nan)
        values=self.transformer_.transform(self._clip(frame))
        return self.selector_.transform(values) if getattr(self,'selector_',None) is not None else values

    def get_feature_names_out(self, input_features=None):
        names=self.transformer_.get_feature_names_out()
        return names[self.selector_.get_support()] if getattr(self,'selector_',None) is not None else names


# ─────────────────────────────────────────────────────────────────────────────
# 3. MODEL CATALOG
# ─────────────────────────────────────────────────────────────────────────────

def get_candidate_models(task_type: str) -> Dict[str, Any]:
    """Instantiates the benchmark suite of models."""
    if task_type == "classification":
        models = {
            "Logistic Regression": LogisticRegression(max_iter=1000, random_state=42),
            "Decision Tree": DecisionTreeClassifier(max_depth=6, random_state=42),
            "Random Forest": RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42),
        }
        if HAS_XGB:
            models["XGBoost"] = xgb.XGBClassifier(n_estimators=100, max_depth=5, eval_metric="logloss", random_state=42)
        if HAS_LGB:
            models["LightGBM"] = lgb.LGBMClassifier(n_estimators=100, max_depth=5, verbosity=-1, random_state=42)
        if HAS_CATBOOST:
            models["CatBoost"] = cb.CatBoostClassifier(iterations=100, depth=5, verbose=0, random_seed=42)
        else:
            models["Gradient Boosting"] = GradientBoostingClassifier(n_estimators=100, random_state=42)
    else:
        models = {
            "Linear Regression": LinearRegression(),
            "Ridge Regression": Ridge(alpha=1.0),
            "Lasso Regression": Lasso(alpha=0.1),
            "Random Forest Regressor": RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42),
        }
        if HAS_XGB:
            models["XGBoost Regressor"] = xgb.XGBRegressor(n_estimators=100, max_depth=5, random_state=42)
        if HAS_LGB:
            models["LightGBM Regressor"] = lgb.LGBMRegressor(n_estimators=100, max_depth=5, verbosity=-1, random_state=42)

    return models


# ─────────────────────────────────────────────────────────────────────────────
# 4. OPTUNA HYPERPARAMETER TUNER
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# 5. FULL AUTOML PIPELINE EXECUTION
# ─────────────────────────────────────────────────────────────────────────────

def tune_best_model_with_optuna(model_name, X_train, y_train, task_type,
                                n_trials=12, timeout_sec=35, *, base_model=None,
                                cv=3, return_details=False):
    """Search only training folds and preserve the candidate's fixed parameters."""
    supported = ('Random Forest','XGBoost','LightGBM','CatBoost','Logistic Regression',
                 'Decision Tree','Ridge','Lasso')
    if not HAS_OPTUNA or not any(name in model_name for name in supported):
        return None
    try:
        estimator = base_model if base_model is not None else get_candidate_models(task_type)[model_name]
        # Keep searches bounded on large datasets; the selected model is refit on
        # the complete training partition and evaluated with the original folds.
        if len(X_train) > 2000 and isinstance(cv, int):
            indices = np.random.default_rng(42).choice(len(X_train),2000,replace=False)
            X_train = X_train.iloc[indices] if isinstance(X_train, pd.DataFrame) else X_train[indices]
            y_train = np.asarray(y_train)[indices]
        def objective(trial):
            if 'Random Forest' in model_name:
                params = dict(n_estimators=trial.suggest_int('n_estimators',50,200,step=50),
                              max_depth=trial.suggest_int('max_depth',4,15))
            elif 'XGBoost' in model_name:
                params = dict(learning_rate=trial.suggest_float('learning_rate',0.01,0.3,log=True),
                              max_depth=trial.suggest_int('max_depth',3,8),
                              n_estimators=trial.suggest_int('n_estimators',50,150))
            elif 'LightGBM' in model_name:
                params = dict(learning_rate=trial.suggest_float('learning_rate',0.01,0.3,log=True),
                              num_leaves=trial.suggest_int('num_leaves',15,63))
            elif 'CatBoost' in model_name:
                params = dict(iterations=trial.suggest_int('iterations',50,150),
                              depth=trial.suggest_int('depth',3,8),
                              learning_rate=trial.suggest_float('learning_rate',0.01,0.3,log=True))
            elif 'Logistic' in model_name:
                params = dict(C=trial.suggest_float('C',0.001,100,log=True))
            elif 'Decision Tree' in model_name:
                params = dict(max_depth=trial.suggest_int('max_depth',2,15),
                              min_samples_leaf=trial.suggest_int('min_samples_leaf',1,10))
            else:
                params = dict(alpha=trial.suggest_float('alpha',0.0001,100,log=True))
            prefix = "model__" if isinstance(estimator, Pipeline) else ""
            candidate = clone(estimator).set_params(**{prefix+k: v for k,v in params.items()})
            scores = cross_val_score(candidate,X_train,y_train,cv=cv,
                scoring='f1_macro' if task_type=='classification' else 'r2',error_score='raise')
            score = float(scores.mean())
            if not np.isfinite(score):
                raise ValueError('Tuning produced a non-finite validation score.')
            return score
        study = optuna.create_study(direction='maximize',sampler=optuna.samplers.TPESampler(seed=42))
        study.optimize(objective,n_trials=n_trials,timeout=timeout_sec)
        details = dict(best_parameters=study.best_params, optimization_trials=len(study.trials),
            completed_trials=sum(t.state==optuna.trial.TrialState.COMPLETE for t in study.trials),
            best_cv_score=study.best_value)
        return details if return_details else details['best_parameters']
    except Exception as exc:
        logger.warning('Optuna tuning failed: %s',exc)
        return None


def _validate_model(name, model, X_train, y_train, task_type, cv):
    start = time.time()
    scoring = "f1_macro" if task_type == "classification" else "r2"
    scores = cross_val_score(model, X_train, y_train, cv=cv, scoring=scoring, error_score="raise")
    if not np.isfinite(scores).all():
        raise ValueError("Model produced non-finite validation scores.")
    model.fit(X_train, y_train)
    return dict(model_name=name, cv_score_mean=float(scores.mean()), cv_score_std=float(scores.std()),
                cv_metric=scoring, cv_folds=cv.n_splits, training_time_sec=round(time.time()-start, 2))


def _holdout_metrics(model, X_test, y_test, task):
    predicted = model.predict(X_test)
    if task == "classification":
        macro = round(float(f1_score(y_test, predicted, average="macro", zero_division=0)), 4)
        metrics = dict(accuracy=round(float(accuracy_score(y_test, predicted)), 4),
            precision=round(float(precision_score(y_test, predicted, average="macro", zero_division=0)), 4),
            recall=round(float(recall_score(y_test, predicted, average="macro", zero_division=0)), 4),
            f1_macro=macro, f1_score=macro,
            f1_weighted=round(float(f1_score(y_test, predicted, average="weighted", zero_division=0)), 4),
            primary_metric=macro, primary_metric_name="f1_macro", roc_auc=None)
        if hasattr(model, "predict_proba"):
            try:
                prob = model.predict_proba(X_test)
                metrics["roc_auc"] = round(float(roc_auc_score(y_test, prob[:, 1]) if prob.shape[1] == 2 else roc_auc_score(y_test, prob, multi_class="ovr")), 4)
            except ValueError:
                pass
    else:
        nonzero = np.abs(y_test) > 1e-8
        metrics = dict(r2_score=round(float(r2_score(y_test, predicted)), 4),
            rmse=round(float(np.sqrt(mean_squared_error(y_test, predicted))), 4),
            mae=round(float(mean_absolute_error(y_test, predicted)), 4),
            mape=round(float(np.mean(np.abs((y_test[nonzero]-predicted[nonzero])/y_test[nonzero]))*100), 2) if nonzero.any() else None,
            primary_metric_name="r2_score")
        metrics["primary_metric"] = metrics["r2_score"]
    return metrics, predicted


def run_automl(df, target_column=None, project_id="default_project", run_tuning=True,
               task_type=None, clip_outliers=False, progress_callback=None, split_strategy="random",
               group_column=None, date_column=None, holdout_fraction=.2, run_id=None,
               include_columns=None, selection_percentile=100, compare_features=False):
    start_time = time.time()
    def report(pct, step):
        if progress_callback:
            progress_callback(pct, step)
    report(5, 'Validating target and features')
    target, task_type, data = validate_automl_input(df, target_column, task_type)
    excluded_ids = [c for c in data.columns if c != target and is_identifier_column(c)]
    X = data.drop(columns=[target] + excluded_ids)
    label_encoder = None
    if task_type == "classification":
        label_encoder = LabelEncoder()
        y = label_encoder.fit_transform(data[target].astype(str))
    else:
        y = pd.to_numeric(data[target]).to_numpy(dtype=float)
    if (split_strategy=='grouped' and group_column==target) or (split_strategy=='chronological' and date_column==target):
        raise ValueError('The split column must differ from the target.')
    train, test, cv, split_details = partitions(data, y, task_type, split_strategy, group_column, date_column, holdout_fraction)
    split_columns = [c for c in (group_column if split_strategy=='grouped' else None,
        date_column if split_strategy=='chronological' else None) if c and c!=target]
    X = X.drop(columns=split_columns, errors='ignore')
    if not 1<=selection_percentile<=100: raise ValueError('Feature selection percentage must be between 1 and 100.')
    if include_columns is not None:
        if not include_columns or len(set(include_columns))!=len(include_columns) or any(c not in X for c in include_columns):
            raise ValueError('Select unique existing feature columns; targets, identifiers and split columns cannot be included.')
    if not len(X.columns): raise ValueError('No features remain after excluding the target and split columns.')
    X_train, X_test, y_train, y_test = X.iloc[train], X.iloc[test], y[train], y[test]
    leaderboard, fitted_models, failures = [], {}, []
    candidates = get_candidate_models(task_type)
    for index, (name, estimator) in enumerate(candidates.items()):
        report(10 + int(50 * index / max(len(candidates), 1)), 'Cross-validating ' + name)
        pipeline = Pipeline([("preprocessor", FoldPreprocessor(clip_outliers,include_columns,selection_percentile,task_type)), ("model", estimator)])
        try:
            leaderboard.append(_validate_model(name, pipeline, X_train, y_train, task_type, cv))
            fitted_models[name] = pipeline
        except Exception as exc:
            failures.append(dict(model_name=name, error=str(exc)))
            logger.warning("Model %s training failed: %s", name, exc)
        report(10 + int(50 * (index+1) / max(len(candidates), 1)), 'Finished ' + name)
    leaderboard.sort(key=lambda entry: entry["cv_score_mean"], reverse=True)
    if not leaderboard:
        raise ValueError("No model trained successfully: " + "; ".join(f"{f['model_name']}: {f['error']}" for f in failures))
    best_entry = leaderboard[0]
    best_name = best_entry["model_name"]
    best_pipeline = fitted_models[best_name]
    tuning_report = None
    if run_tuning and HAS_OPTUNA:
        report(65, 'Tuning ' + best_name)
        search = tune_best_model_with_optuna(best_name, X_train, y_train, task_type,
            n_trials=10, timeout_sec=25, base_model=best_pipeline, cv=cv, return_details=True)
        if search:
            tuning_report = dict(search, tuned_model=best_name, applied=False, baseline_cv_score=best_entry["cv_score_mean"])
            try:
                tuned = clone(best_pipeline).set_params(**{"model__"+k: v for k,v in search["best_parameters"].items()})
                entry = _validate_model(best_name, tuned, X_train, y_train, task_type, cv)
                tuning_report["tuned_cv_score"] = entry["cv_score_mean"]
                if entry["cv_score_mean"] >= best_entry["cv_score_mean"] - 1e-12:
                    leaderboard[0] = best_entry = entry
                    best_pipeline = tuned
                    tuning_report["applied"] = True
                else:
                    tuning_report["reason"] = "Tuned validation score was lower; retained baseline model."
            except Exception as exc:
                tuning_report["reason"] = f"Tuned model refit failed: {exc}"
        else:
            tuning_report = dict(tuned_model=best_name, applied=False, optimization_trials=0,
                reason="No completed tuning result; baseline model retained.")
    feature_comparison=None
    if compare_features:
        report(81,'Comparing feature settings using training folds only')
        before=Pipeline([('preprocessor',FoldPreprocessor(clip_outliers)),('model',clone(best_pipeline.named_steps['model']))])
        before_scores=cross_val_score(before,X_train,y_train,cv=cv,scoring='f1_macro' if task_type=='classification' else 'r2',error_score='raise')
        feature_comparison=dict(before_cv_mean=float(before_scores.mean()),before_cv_std=float(before_scores.std()),after_cv_mean=best_entry['cv_score_mean'],after_cv_std=best_entry['cv_score_std'],
            metric='f1_macro' if task_type=='classification' else 'r2',model_name=best_name,note='Same estimator and training folds. Before uses all eligible features; after uses the selected settings. Holdout does not select features.')
    report(85, 'Evaluating selected model on holdout')
    # Selection and tuning are frozen before any holdout prediction or explanation.
    metrics, predicted = _holdout_metrics(best_pipeline, X_test, y_test, task_type)
    baseline_model = DummyClassifier(strategy='most_frequent') if task_type=='classification' else DummyRegressor(strategy='mean')
    baseline_model.fit(np.zeros((len(y_train),1)), y_train)
    baseline_predicted=baseline_model.predict(np.zeros((len(y_test),1)))
    if task_type=='classification':
        baseline_score=round(float(f1_score(y_test,baseline_predicted,average='macro',zero_division=0)),4)
        baseline=dict(primary_metric=baseline_score,primary_metric_name='f1_macro',strategy='most frequent training class')
    else:
        baseline=dict(primary_metric=round(float(r2_score(y_test,baseline_predicted)),4),primary_metric_name='r2_score',strategy='training mean')
    warnings = performance_warnings(metrics['primary_metric'], baseline['primary_metric'], best_entry['cv_score_mean'], task_type)
    best_entry.update(metrics, evaluation_partition="holdout")
    preprocessor = best_pipeline.named_steps["preprocessor"]
    feature_names = preprocessor.get_feature_names_out().tolist()
    transformed_train = pd.DataFrame(preprocessor.transform(X_train), columns=feature_names)
    transformed_test = pd.DataFrame(preprocessor.transform(X_test), columns=feature_names)
    report(90, 'Computing model explanations')
    xai_results = compute_feature_importance(best_pipeline.named_steps["model"], transformed_train,
        transformed_test, pd.Series(y_test), feature_names, task_type)
    if task_type == "classification":
        diagnostic = dict(type="confusion_matrix", matrix=confusion_matrix(y_test, predicted,
            labels=np.arange(len(label_encoder.classes_))).tolist(), labels=label_encoder.classes_.tolist())
    else:
        diagnostic = dict(type="residuals", actual=y_test.tolist()[:100], predicted=predicted.tolist()[:100],
            residuals=(y_test-predicted).tolist()[:100])
    probability_report=None; evaluation_data=None
    if task_type=='classification' and hasattr(best_pipeline,'predict_proba'):
        proba=best_pipeline.predict_proba(X_test)
        probability_report=probability_diagnostics(y_test,proba,label_encoder.classes_.tolist())
        evaluation_data=dict(actual=y_test.tolist(),probabilities=proba.tolist(),labels=label_encoder.classes_.tolist())
    run_id = run_id or str(uuid.uuid4())
    artifact_dir = ARTIFACTS_DIR / "models" / str(project_id) / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "champion.joblib"
    report(97, 'Saving selected model')
    used_columns = preprocessor.numeric_columns_ + preprocessor.categorical_columns_
    references={c:float(pd.to_numeric(X_train[c]).median()) for c in preprocessor.numeric_columns_}
    references.update({c:str(_normalize_features(X_train)[c].mode().iloc[0]) for c in preprocessor.categorical_columns_})
    with tempfile.TemporaryDirectory(prefix=".model-", dir=artifact_dir) as staging:
        staged_path = os.path.join(staging, "champion.joblib")
        joblib.dump(dict(pipeline=best_pipeline, task_type=task_type, target_column=target,
            label_encoder=label_encoder, feature_names=used_columns, optuna_tuning=tuning_report,
            reference_values=references,evaluation_data=evaluation_data), staged_path)
        os.replace(staged_path, model_path)
    return sanitize_for_json(dict(project_id=project_id, run_id=run_id, baseline=baseline, warnings=warnings, target_column=target, task_type=task_type,
        dataset_shape=dict(rows=len(data), features=len(used_columns)),
        dropped_missing_target_rows=len(df)-len(data), excluded_features=[c for c in df.columns if c != target and c not in used_columns],
        feature_columns=used_columns, leaderboard=leaderboard, selection_metric="cv_score_mean",
        cv_metric="f1_macro" if task_type == "classification" else "r2", cv_folds=cv.n_splits,
        evaluation=dict(holdout_rows=len(X_test), training_rows=len(X_train), test_used_for_selection=False,
            preprocessing="fitted within each training fold", **split_details),
        best_model=best_entry, failed_models=failures, optuna_tuning=tuning_report, xai=xai_results,
        feature_comparison=feature_comparison,selected_encoded_features=feature_names,probability_diagnostics=probability_report,
        diagnostic_chart=diagnostic, saved_model_path=str(model_path), total_runtime_sec=round(time.time()-start_time, 2)))


def predict_with_saved_model(model_path: str, input_data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Loads a serialized model pipeline and generates predictions for inference."""
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model artifact not found at {model_path}")

    bundle = joblib.load(model_path)
    from backend.services.model_tools import strict_inference

    records = [input_data] if isinstance(input_data, dict) else input_data
    df_input = pd.DataFrame(records)
    # A blank simulation field explicitly means missing. Invalid nonblank numbers
    # must fail the same validation used by batch inference, never silently impute.
    for feature in bundle.get("feature_names", []):
        if feature not in df_input:
            df_input[feature] = np.nan
    df_input = df_input.replace("", np.nan)
    preds, probabilities, _, warnings = strict_inference(bundle, df_input)
    task_type = bundle["task_type"]

    return sanitize_for_json({
        "predictions": preds.tolist(),
        "probabilities": probabilities.tolist() if probabilities is not None else None,
        "task_type": task_type,
        "count": len(df_input),
        "warnings": warnings,
    })
