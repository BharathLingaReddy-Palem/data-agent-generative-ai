"""Immutable dataset versions and version-bound runs, stored without pickle."""
from contextlib import closing
from datetime import datetime, timezone
import gzip
import json
import sqlite3
import uuid
from backend.config import DB_PATH, MAX_SESSION_STORAGE_BYTES
from backend.services.session_store import encode, decode
from backend.services.experiment_tracker import compute_dataset_hash
from backend.services.profiler import profile_dataset


class WorkspaceStore:
    def __init__(self, path=DB_PATH):
        self.path = str(path)
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute('''CREATE TABLE IF NOT EXISTS dataset_versions (
              id TEXT PRIMARY KEY, project_id TEXT NOT NULL, owner_id TEXT NOT NULL,
              created_at TEXT NOT NULL, metadata TEXT NOT NULL, frame BLOB NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS workspace_runs (
              id TEXT PRIMARY KEY, project_id TEXT NOT NULL, owner_id TEXT NOT NULL,
              created_at TEXT NOT NULL, result TEXT NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS report_templates (
              id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, name TEXT NOT NULL, settings TEXT NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS cleaning_recipes (
              id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, name TEXT NOT NULL, plan TEXT NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS cleaning_audits (
              version_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, owner_id TEXT NOT NULL, changes BLOB NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS prediction_batches (
              id TEXT PRIMARY KEY, project_id TEXT NOT NULL, owner_id TEXT NOT NULL, metadata TEXT NOT NULL, frame BLOB NOT NULL)''')

    def save_batch(self, session, metadata, frame):
        bid=str(uuid.uuid4());payload=gzip.compress(json.dumps(encode(frame),allow_nan=False).encode())
        with closing(sqlite3.connect(self.path,timeout=30)) as c,c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT count(*) FROM prediction_batches WHERE project_id=? AND owner_id=?',(session['project_id'],session['owner_id'])).fetchone()[0]>=20:
                raise ValueError('This project has reached its 20 prediction-batch limit.')
            used=c.execute('SELECT COALESCE(sum(length(frame)),0) FROM prediction_batches WHERE owner_id=?',(session['owner_id'],)).fetchone()[0]
            if used+len(payload)>MAX_SESSION_STORAGE_BYTES: raise ValueError('Prediction batch storage limit reached.')
            c.execute('INSERT INTO prediction_batches VALUES(?,?,?,?,?)',(bid,session['project_id'],session['owner_id'],json.dumps(metadata),payload))
        return bid

    def batch(self, session, batch_id):
        with closing(sqlite3.connect(self.path)) as c:
            row=c.execute('SELECT metadata,frame FROM prediction_batches WHERE id=? AND project_id=? AND owner_id=?',(batch_id,session['project_id'],session['owner_id'])).fetchone()
        if not row: raise ValueError('Prediction batch not found.')
        return json.loads(row[0]),decode(json.loads(gzip.decompress(row[1])))

    def recipes(self, owner_id):
        with closing(sqlite3.connect(self.path)) as c:
            return [dict(id=r[0],name=r[1],plan=json.loads(r[2])) for r in c.execute(
                'SELECT id,name,plan FROM cleaning_recipes WHERE owner_id=? ORDER BY name',(owner_id,))]

    def save_recipe(self, owner_id, name, plan):
        if not name.strip() or len(name)>100: raise ValueError('Recipe name must contain 1–100 characters.')
        entries=self.recipes(owner_id); existing=next((r for r in entries if r['name']==name.strip()),None)
        if not existing and len(entries)>=30: raise ValueError('Recipe limit reached (30).')
        if len(json.dumps(plan))>20000: raise ValueError('Recipe is too large.')
        rid=existing['id'] if existing else str(uuid.uuid4())
        with closing(sqlite3.connect(self.path)) as c,c:
            c.execute('INSERT OR REPLACE INTO cleaning_recipes VALUES(?,?,?,?)',(rid,owner_id,name.strip(),json.dumps(plan)))
        return rid

    def save_audit(self, session, version_id, changes):
        from backend.services.serializer import sanitize_for_json
        payload=gzip.compress(json.dumps(sanitize_for_json(changes),allow_nan=False,default=str).encode())
        if len(payload)>10*1024*1024: raise ValueError('Audit exceeds 10 MB. Apply a smaller recipe.')
        with closing(sqlite3.connect(self.path)) as c,c:
            c.execute('INSERT INTO cleaning_audits VALUES(?,?,?,?)',(version_id,session['project_id'],session['owner_id'],payload))

    def audit(self, session, version_id):
        with closing(sqlite3.connect(self.path)) as c:
            row=c.execute('SELECT changes FROM cleaning_audits WHERE version_id=? AND project_id=? AND owner_id=?',
                (version_id,session['project_id'],session['owner_id'])).fetchone()
        if not row: raise ValueError('This version has no detailed cleaning audit.')
        return json.loads(gzip.decompress(row[0]))

    def versions(self, session):
        with closing(sqlite3.connect(self.path)) as c:
            return [dict(id=r[0], created_at=r[1], audit_available=bool(r[3]), **json.loads(r[2])) for r in c.execute(
                'SELECT v.id,v.created_at,v.metadata,EXISTS(SELECT 1 FROM cleaning_audits a WHERE a.version_id=v.id AND a.owner_id=v.owner_id AND a.project_id=v.project_id) FROM dataset_versions v WHERE v.project_id=? AND v.owner_id=? ORDER BY v.created_at',
                (session['project_id'],session['owner_id']))]

    def add_version(self, session, frame, label, steps, parent=None):
        items=self.versions(session)
        if len(items)>=20:
            raise ValueError('This project has reached its 20-version limit. Create a new project for further versions.')
        payload=gzip.compress(json.dumps(encode(frame),allow_nan=False).encode())
        meta=dict(label=label, parent_version_id=parent, steps=steps, rows=len(frame), columns=len(frame.columns),
                  dataset_hash=compute_dataset_hash(frame), health=profile_dataset(frame)['health']['score'])
        vid=str(uuid.uuid4())
        with closing(sqlite3.connect(self.path,timeout=30)) as c,c:
            c.execute('BEGIN IMMEDIATE')
            used=c.execute('SELECT COALESCE(sum(length(frame)),0) FROM dataset_versions WHERE owner_id=?',
                           (session['owner_id'],)).fetchone()[0]
            if used+len(payload)>MAX_SESSION_STORAGE_BYTES:
                raise ValueError('Stored version data exceeds your storage limit.')
            c.execute('INSERT INTO dataset_versions VALUES(?,?,?,?,?,?)',(vid,session['project_id'],session['owner_id'],
                datetime.now(timezone.utc).isoformat(),json.dumps(meta),payload))
        return vid

    def frame(self, session, version_id):
        with closing(sqlite3.connect(self.path)) as c:
            row=c.execute('SELECT frame FROM dataset_versions WHERE id=? AND project_id=? AND owner_id=?',
                (version_id,session['project_id'],session['owner_id'])).fetchone()
        if not row:
            raise ValueError('Dataset version not found.')
        return decode(json.loads(gzip.decompress(row[0])))

    def ensure(self, session):
        if not session.get('active_version_id'):
            versions=self.versions(session)
            if versions:
                session['active_version_id']=versions[-1]['id']
            else:
                original=self.add_version(session,session['df'],'Original upload',[])
                session['active_version_id']=original
                if session.get('df_cleaned') is not None:
                    session['active_version_id']=self.add_version(session,session['df_cleaned'],'Previous cleaned data',
                        [dict(operation='legacy_cleaning',details=session.get('cleaning_audit',{}))],original)
        return session['active_version_id']

    def save_run(self, session, result, kind, settings):
        if len(self.runs(session)) >= 100:
            raise ValueError('This project has reached its 100 saved-run limit. Create a new project for further experiments.')
        run_id=result.get('run_id') or str(uuid.uuid4())
        record=dict(result,run_id=run_id,kind=kind,version_id=session['active_version_id'],settings=settings)
        with closing(sqlite3.connect(self.path)) as c,c:
            c.execute('INSERT OR REPLACE INTO workspace_runs VALUES(?,?,?,?,?)',(run_id,session['project_id'],
                session['owner_id'],datetime.now(timezone.utc).isoformat(),json.dumps(record,allow_nan=False)))
        return record

    def runs(self, session):
        with closing(sqlite3.connect(self.path)) as c:
            return [dict(json.loads(r[1]),created_at=r[0]) for r in c.execute(
                'SELECT created_at,result FROM workspace_runs WHERE project_id=? AND owner_id=? ORDER BY created_at DESC',
                (session['project_id'],session['owner_id']))]

    def templates(self, owner_id):
        with closing(sqlite3.connect(self.path)) as c:
            return [dict(id=r[0],name=r[1],settings=json.loads(r[2])) for r in c.execute(
                'SELECT id,name,settings FROM report_templates WHERE owner_id=? ORDER BY name',(owner_id,))]

    def save_template(self, owner_id, name, settings):
        if not name.strip() or len(name)>100: raise ValueError('Template name must contain 1–100 characters.')
        entries=self.templates(owner_id)
        existing=next((e for e in entries if e['name']==name),None)
        if not existing and len(entries)>=30: raise ValueError('Template limit reached (30).')
        tid=existing['id'] if existing else str(uuid.uuid4())
        with closing(sqlite3.connect(self.path)) as c,c:
            c.execute('INSERT OR REPLACE INTO report_templates VALUES(?,?,?,?)',(tid,owner_id,name,json.dumps(settings)))
        return tid
