from contextlib import closing
"""SQLite is the ownership authority; Supabase is an optional server-side mirror."""
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from backend.config import DB_PATH, ENABLE_CLOUD_SYNC, SUPABASE_URL, SUPABASE_KEY
logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self, db_path=DB_PATH):
        self.local_db_path = Path(db_path)
        self.local_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.supabase = None
        self._init_local_db()
        if ENABLE_CLOUD_SYNC and SUPABASE_URL and SUPABASE_KEY:
            from supabase import create_client
            self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    def _init_local_db(self):
        with closing(sqlite3.connect(self.local_db_path)) as conn, conn:
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE name='projects'").fetchone()
            if exists and 'owner_id' not in [r[1] for r in conn.execute('PRAGMA table_info(projects)')]:
                backup = str(self.local_db_path) + '.bak-' + datetime.now().strftime('%Y%m%d%H%M%S') + '-' + uuid.uuid4().hex[:8]
                with closing(sqlite3.connect(backup)) as target, target:
                    conn.backup(target)
                conn.execute('BEGIN IMMEDIATE')
                # Another API/Streamlit process may have migrated while we backed up.
                if 'owner_id' not in [r[1] for r in conn.execute('PRAGMA table_info(projects)')]:
                    conn.execute('ALTER TABLE projects ADD COLUMN owner_id TEXT')
                conn.commit()
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, csv_url TEXT NOT NULL,
                    task_type TEXT, target_column TEXT, status TEXT DEFAULT 'completed',
                    created_at TEXT NOT NULL, owner_id TEXT);
                CREATE INDEX IF NOT EXISTS projects_owner ON projects(owner_id);
                CREATE TABLE IF NOT EXISTS model_leaderboard (
                    id TEXT PRIMARY KEY, project_id TEXT, model_name TEXT NOT NULL,
                    model_url TEXT, accuracy REAL, f1_score REAL, rmse REAL, r2_score REAL,
                    is_best INTEGER DEFAULT 0, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY, project_id TEXT, pdf_url TEXT NOT NULL,
                    summary TEXT, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY, project_id TEXT, role TEXT NOT NULL,
                    content TEXT NOT NULL, created_at TEXT NOT NULL);
            ''')
            for table in ('reports', 'chat_messages', 'model_leaderboard', 'experiments'):
                if conn.execute('SELECT 1 FROM sqlite_master WHERE name=?', (table,)).fetchone():
                    conn.execute(f'''INSERT OR IGNORE INTO projects(id,name,csv_url,status,created_at)
                        SELECT DISTINCT project_id, 'Recovered historical project', '', 'legacy', ?
                        FROM {table} WHERE project_id IS NOT NULL''', (self._now(),))

    def _mirror(self, table, records, upsert=False):
        if self.supabase:
            try:
                records = dict(records)
                if 'is_best' in records:
                    records['is_best'] = bool(records['is_best'])
                query = self.supabase.table(table)
                (query.upsert(records) if upsert else query.insert(records)).execute()
            except Exception:
                logger.warning('Cloud mirror failed for %s; local records retained.', table)

    def get_project(self, project_id):
        with closing(sqlite3.connect(self.local_db_path)) as conn, conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
        return dict(row) if row else None

    def save_project(self, name, csv_url, task_type=None, target_column=None, project_id=None, owner_id=None):
        project_id = project_id or str(uuid.uuid4())
        with closing(sqlite3.connect(self.local_db_path)) as conn, conn:
            old = conn.execute('SELECT owner_id FROM projects WHERE id=?', (project_id,)).fetchone()
            if old and owner_id is not None and old[0] != owner_id:
                raise ValueError('Project ownership cannot be changed.')
            conn.execute('''INSERT INTO projects(id,name,csv_url,task_type,target_column,status,created_at,owner_id)
                VALUES(?,?,?,?,?,'completed',?,?) ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, csv_url=excluded.csv_url,
                task_type=COALESCE(excluded.task_type,projects.task_type),
                target_column=COALESCE(excluded.target_column,projects.target_column)''',
                (project_id,name,csv_url,task_type,target_column,self._now(),owner_id))
        self._mirror('projects', self.get_project(project_id), upsert=True)
        return project_id

    def _save_child(self, table, project_id, fields):
        if not self.get_project(project_id):
            raise ValueError('Register the project before saving its records.')
        record = dict(id=str(uuid.uuid4()), project_id=project_id, **fields, created_at=self._now())
        with closing(sqlite3.connect(self.local_db_path)) as conn, conn:
            conn.execute(f'INSERT INTO {table} ({",".join(record)}) VALUES ({",".join("?" for _ in record)})', tuple(record.values()))
        self._mirror(table, record)

    def save_chat_message(self, project_id, role, content):
        self._save_child('chat_messages', project_id, dict(role=role, content=content))

    def save_report(self, project_id, pdf_url, summary=''):
        self._save_child('reports', project_id, dict(pdf_url=pdf_url, summary=summary))

    def save_model_leaderboard(self, project_id, leaderboard):
        for item in leaderboard:
            fields = {k: item.get(k) for k in ('model_name','model_url','accuracy','f1_score','rmse','r2_score')}
            fields['is_best'] = int(bool(item.get('is_best')))
            self._save_child('model_leaderboard', project_id, fields)


db_service = DatabaseService()
