from contextlib import closing
"""Durable, bounded session snapshots; JSON codecs never execute serialized code."""
import gzip
import json
import math
import sqlite3
from datetime import datetime, date, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from backend.config import DB_PATH, MAX_PROJECTS_PER_USER, MAX_SESSION_STORAGE_BYTES


class SessionLimitError(ValueError):
    pass


def encode(value):
    if isinstance(value, pd.DataFrame):
        # Python's JSON float encoding preserves double precision; explicit tags
        # preserve infinities, dates and dtypes without pickle/joblib loading.
        return {"__frame__": True, "columns": list(value.columns),
            "dtypes": [str(t) for t in value.dtypes], "data": encode(value.to_numpy(dtype=object).tolist())}
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in list(value.items()) if not str(k).startswith('_')}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [encode(v) for v in value]
    if value is pd.NA or value is pd.NaT or value is None:
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, np.generic):
        return encode(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return {"__float__": "nan" if math.isnan(value) else "inf" if value > 0 else "-inf"}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, float, int, bool)):
        return value
    raise TypeError(f"Unsupported session value: {type(value).__name__}")


def decode(value):
    if isinstance(value, list):
        return [decode(v) for v in value]
    if isinstance(value, dict):
        if value.get("__frame__") is True:
            frame = pd.DataFrame(decode(value['data']), columns=value['columns'])
            for col, dtype in zip(frame.columns, value['dtypes']):
                if dtype.startswith('datetime64'):
                    frame[col] = pd.to_datetime(frame[col], utc='UTC' in dtype)
                elif dtype != 'category':
                    frame[col] = frame[col].astype(dtype)
            return frame
        if "__datetime__" in value:
            return pd.Timestamp(value['__datetime__'])
        if "__float__" in value:
            return float(value['__float__'])
        return {k: decode(v) for k, v in value.items()}
    return value


class SessionStore:
    def __init__(self, db_path=DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS dataset_sessions (
                project_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                snapshot BLOB NOT NULL, updated_at TEXT NOT NULL)''')
            conn.execute('CREATE INDEX IF NOT EXISTS sessions_owner ON dataset_sessions(owner_id)')

    def save(self, project_id, session):
        payload = gzip.compress(json.dumps(encode(session), ensure_ascii=False, allow_nan=False).encode('utf-8'))
        owner = session['owner_id']
        with closing(sqlite3.connect(self.db_path, timeout=30)) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            prior = conn.execute('SELECT owner_id FROM dataset_sessions WHERE project_id=?', (project_id,)).fetchone()
            if prior and prior[0] != owner:
                raise ValueError('Session ownership cannot be changed.')
            count, size = conn.execute('SELECT count(*), COALESCE(sum(length(snapshot)),0) FROM dataset_sessions WHERE owner_id=? AND project_id<>?', (owner, project_id)).fetchone()
            if count >= MAX_PROJECTS_PER_USER or size + len(payload) > MAX_SESSION_STORAGE_BYTES:
                raise SessionLimitError('Project or stored-data quota exceeded. Remove an old project before uploading more data.')
            conn.execute('INSERT OR REPLACE INTO dataset_sessions VALUES(?,?,?,?)',
                (project_id, owner, payload, datetime.now(timezone.utc).isoformat()))

    def load(self, project_id, owner_id=None):
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            row = conn.execute('SELECT owner_id,snapshot FROM dataset_sessions WHERE project_id=?', (project_id,)).fetchone()
        if not row or (owner_id is not None and row[0] != owner_id):
            return None
        return decode(json.loads(gzip.decompress(row[1])))

    def delete(self, project_id, owner_id):
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute('DELETE FROM dataset_sessions WHERE project_id=? AND owner_id=?', (project_id, owner_id))


session_store = SessionStore()
