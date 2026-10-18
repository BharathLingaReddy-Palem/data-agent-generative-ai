"""Partitions shared by training and tuning; no holdout-driven selection."""
import numpy as np
import pandas as pd
from sklearn.model_selection import (train_test_split, StratifiedKFold, KFold,
    GroupShuffleSplit, GroupKFold, TimeSeriesSplit)


class FixedFolds:
    def __init__(self, folds):
        self.folds = list(folds)
        self.n_splits = len(self.folds)
    def split(self, X=None, y=None, groups=None):
        return iter(self.folds)
    def get_n_splits(self, X=None, y=None, groups=None):
        return self.n_splits


def partitions(data, y, task, strategy='random', group_column=None, date_column=None, holdout_fraction=.2):
    if not .1 <= holdout_fraction <= .4:
        raise ValueError('Holdout fraction must be between 0.1 and 0.4.')
    if strategy=='grouped' and group_column is None: raise ValueError('Choose a group column.')
    indices=np.arange(len(data)); details=dict(split_strategy=strategy)
    if strategy=='random':
        train,test=train_test_split(indices,test_size=holdout_fraction,random_state=42,
            stratify=y if task=='classification' else None)
        folds=min(5,int(pd.Series(np.asarray(y)[train]).value_counts().min())) if task=='classification' else min(5,len(train)//2)
        if folds<2: raise ValueError('Too few training observations per class for validation.')
        cv=StratifiedKFold(folds,shuffle=True,random_state=42) if task=='classification' else KFold(folds,shuffle=True,random_state=42)
    elif strategy=='grouped':
        if group_column not in data or data[group_column].isna().any():
            raise ValueError('Choose a group column with no missing values.')
        groups=data[group_column].astype(str).to_numpy()
        if len(set(groups))<5: raise ValueError('Grouped evaluation needs at least five distinct groups.')
        train,test=next(GroupShuffleSplit(n_splits=1,test_size=holdout_fraction,random_state=42).split(indices,y,groups))
        train_groups=groups[train]
        cv=FixedFolds(GroupKFold(min(5,len(set(train_groups)))).split(train,y[train],train_groups))
        details.update(group_column=group_column,training_groups=len(set(train_groups)),holdout_groups=len(set(groups[test])),group_overlap=0)
    elif strategy=='chronological':
        if date_column not in data: raise ValueError('Choose a date column for chronological evaluation.')
        dates=pd.to_datetime(data[date_column],format='mixed',errors='coerce',utc=True)
        if dates.isna().any(): raise ValueError('The date column contains missing or invalid dates. Clean these first.')
        unique=np.sort(dates.unique())
        if len(unique)<10: raise ValueError('Chronological evaluation needs at least ten distinct dates.')
        cut=unique[max(1,int(len(unique)*(1-holdout_fraction)))]
        train=indices[dates<cut]; test=indices[dates>=cut]
        train=train[np.argsort(dates.iloc[train].to_numpy(),kind='stable')]
        test=test[np.argsort(dates.iloc[test].to_numpy(),kind='stable')]
        # Split unique dates rather than rows: equal timestamps never cross a fold boundary.
        training_dates=np.sort(dates.iloc[train].unique())
        date_folds=TimeSeriesSplit(min(5,len(training_dates)-1)).split(training_dates)
        folds=[]
        td=dates.iloc[train]
        for a,b in date_folds:
            folds.append((np.flatnonzero(td.isin(training_dates[a])),np.flatnonzero(td.isin(training_dates[b]))))
        cv=FixedFolds(folds)
        details.update(date_column=date_column,training_end=dates.iloc[train].max().isoformat(),holdout_start=dates.iloc[test].min().isoformat())
    else: raise ValueError('Choose random, grouped or chronological evaluation.')
    if len(train)<8 or len(test)<2: raise ValueError('This split leaves too few training or holdout rows.')
    if task=='classification':
        expected=set(y)
        if set(y[train])!=expected: raise ValueError('Training partition is missing a class. Choose another split or collect more data.')
        for a,b in cv.split(data.iloc[train],y[train]):
            if len(b)<2 or set(y[train][a])!=expected:
                raise ValueError('A validation fold has too few rows or is missing a training class. Choose another split or collect more data.')
    elif any(len(b)<2 for a,b in cv.split(data.iloc[train],y[train])):
        raise ValueError('Each validation fold needs at least two rows for R².')
    return train,test,cv,details


def performance_warnings(score, baseline, cv_score, task):
    warnings=[]
    if score<=baseline: warnings.append('Holdout performance does not beat the simple baseline. Do not rely on this model yet.')
    if (task=='regression' and score<.3) or (task=='classification' and score<.5):
        warnings.append('Holdout performance is poor. Review features, data quality and the split before using predictions.')
    if cv_score-score>.15: warnings.append('Holdout performance is substantially below cross-validation. Check distribution shifts and leakage-prone features.')
    return warnings
