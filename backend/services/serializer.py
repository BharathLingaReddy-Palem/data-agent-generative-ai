"""
serializer.py — Universal JSON Sanitizer
=========================================
Recursively converts all NumPy/Pandas scalar types, infinite/NaN floats,
timestamps, and complex structures into standard native Python types
compatible with JSON encoding in FastAPI.
"""

import math
from datetime import datetime, date
from typing import Any
import numpy as np
import pandas as pd


def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively converts arbitrary Python objects (including NumPy scalars,
    arrays, Pandas objects, NaNs, and infinite floats) into JSON-compliant
    native Python data structures (dict, list, int, float, str, bool, None).
    """
    if obj is None:
        return None

    # Booleans (must check before int because bool inherits from int)
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)

    # Integers
    if isinstance(obj, (int, np.integer)):
        return int(obj)

    # Floats & NumPy floats
    if isinstance(obj, (float, np.floating)):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return float(obj)

    # Strings
    if isinstance(obj, str):
        return obj

    # Timestamps & Dates
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()

    # NumPy arrays & Pandas Series
    if isinstance(obj, np.ndarray):
        return [sanitize_for_json(x) for x in obj.tolist()]
    if isinstance(obj, pd.Series):
        return [sanitize_for_json(x) for x in obj.tolist()]

    # Pandas DataFrame
    if isinstance(obj, pd.DataFrame):
        return sanitize_for_json(obj.to_dict(orient="records"))

    # Dictionaries
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}

    # Lists, Tuples, Sets
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(x) for x in obj]

    # Objects with custom .to_dict()
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        try:
            return sanitize_for_json(obj.to_dict())
        except Exception:
            pass

    # Fallback to string representation for foreign objects
    return str(obj)
