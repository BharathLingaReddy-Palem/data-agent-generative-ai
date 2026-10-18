"""Versioned full-content SHA-256 fingerprints for experiments and cache keys."""
import hashlib
import json
import math
from datetime import date, datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd


def _value(value):
    """Typed values avoid ambiguous labels, float rounding and null collisions."""
    if value is pd.NA:
        return ['pd.NA']
    if value is pd.NaT:
        return ['NaT']
    if value is None:
        return ['None']
    if isinstance(value, np.datetime64):
        return _value(pd.Timestamp(value))
    if isinstance(value, np.timedelta64):
        return _value(pd.Timedelta(value))
    if isinstance(value, np.generic):
        return _value(value.item())
    if isinstance(value, bool):
        return ['bool', value]
    if isinstance(value, int):
        return ['int', str(value)]
    if isinstance(value, float):
        return ['float', 'nan' if math.isnan(value) else value.hex()]
    if isinstance(value, str):
        return ['str', value]
    if isinstance(value, bytes):
        return ['bytes', value.hex()]
    if isinstance(value, (pd.Timestamp, datetime)):
        return ['datetime', value.isoformat()]
    if isinstance(value, date):
        return ['date', value.isoformat()]
    if isinstance(value, (pd.Timedelta, timedelta)):
        return ['timedelta', str(pd.Timedelta(value).value)]
    if isinstance(value, pd.Period):
        return ['period', str(value.ordinal), value.freqstr]
    if isinstance(value, Decimal):
        return ['decimal', str(value)]
    if isinstance(value, complex):
        return ['complex', value.real.hex(), value.imag.hex()]
    if isinstance(value, (tuple, list)):
        return [type(value).__name__, [_value(item) for item in value]]
    if isinstance(value, dict):
        items = [[_value(key), _value(item)] for key, item in value.items()]
        return ['dict', sorted(items, key=lambda item: _json(item[0]))]
    raise TypeError(f'Unsupported dataset value: {type(value).__name__}')


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _dtype(dtype):
    if isinstance(dtype, pd.CategoricalDtype):
        return ['category', dtype.ordered, [_value(item) for item in dtype.categories]]
    return str(dtype)


def dataset_fingerprint(data):
    """Hash every row, row order/index, column label/order and dtype, without sampling.

    The v2 domain tag invalidates old sample-based cache entries. Raw file bytes
    have a separate domain; their digest is intentionally different from a frame.
    Unsupported inputs raise instead of sharing a misleading 'unhashed' value.
    """
    if isinstance(data, (bytes, bytearray, memoryview)):
        return hashlib.sha256(b'ds-agent:bytes:v2\0' + bytes(data)).hexdigest()
    if not isinstance(data, pd.DataFrame):
        raise TypeError('Expected a pandas DataFrame or file bytes.')
    hasher = hashlib.sha256(b'ds-agent:dataset:v2\0')
    metadata = dict(shape=list(data.shape), columns=[_value(c) for c in data.columns],
        dtypes=[_dtype(dtype) for dtype in data.dtypes],
        index_dtype=_dtype(data.index.dtype), index_names=[_value(n) for n in data.index.names],
        column_names=[_value(n) for n in data.columns.names])
    hasher.update(_json(metadata) + b'\n')
    # Stream rows instead of materializing a second whole-data JSON snapshot.
    for index, row in zip(data.index, data.itertuples(index=False, name=None)):
        hasher.update(_json([_value(index), [_value(cell) for cell in row]]) + b'\n')
    return hasher.hexdigest()
