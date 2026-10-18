"""
experiment_tracker.py — Experiment Tracking & Reproducibility
=============================================================
Persists and tracks every AutoML training run, hyperparameter set,
evaluation metric, dataset version, and model artifact into local SQLite.
"""

import os
import json
import sqlite3
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from backend.config import DB_PATH
from backend.services.dataset_fingerprint import dataset_fingerprint


def init_db():
    """Initializes experiment tracking tables if not present."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                dataset_name TEXT,
                dataset_hash TEXT,
                target_column TEXT,
                task_type TEXT,
                best_model TEXT,
                primary_metric_name TEXT,
                primary_metric_value REAL,
                metrics_json TEXT,
                hyperparams_json TEXT,
                model_artifact_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to initialize experiments DB: {e}")


# Initialize on import
init_db()


def compute_dataset_hash(df_or_bytes: Any) -> str:
    """Full-content, versioned SHA-256; existing historical hashes are unchanged."""
    return dataset_fingerprint(df_or_bytes)


def log_experiment(
    experiment_id: str,
    project_id: str,
    dataset_name: str,
    dataset_hash: str,
    target_column: str,
    task_type: str,
    best_model: str,
    primary_metric_name: str,
    primary_metric_value: float,
    metrics: Dict[str, Any],
    hyperparameters: Optional[Dict[str, Any]] = None,
    model_artifact_path: Optional[str] = None,
) -> bool:
    """Logs a completed training experiment."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO experiments (
                id, project_id, dataset_name, dataset_hash, target_column,
                task_type, best_model, primary_metric_name, primary_metric_value,
                metrics_json, hyperparams_json, model_artifact_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            experiment_id,
            project_id,
            dataset_name,
            dataset_hash,
            target_column,
            task_type,
            best_model,
            primary_metric_name,
            float(primary_metric_value),
            json.dumps(metrics),
            json.dumps(hyperparameters or {}),
            model_artifact_path or "",
            datetime.utcnow().isoformat(),
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to log experiment: {e}")
        return False


def get_project_experiments(project_id: Optional[str] = None, owner_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all tracked experiments, optionally filtered by project_id."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if owner_id:
            cursor.execute('''SELECT e.* FROM experiments e JOIN projects p ON p.id=e.project_id
                WHERE p.owner_id=? AND (? IS NULL OR e.project_id=?)
                ORDER BY e.created_at DESC LIMIT 50''', (owner_id, project_id, project_id))
        elif project_id:
            cursor.execute("SELECT * FROM experiments WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
        else:
            cursor.execute("SELECT * FROM experiments ORDER BY created_at DESC LIMIT 50")
        rows = cursor.fetchall()
        conn.close()

        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "project_id": r["project_id"],
                "dataset_name": r["dataset_name"],
                "dataset_hash": r["dataset_hash"],
                "target_column": r["target_column"],
                "task_type": r["task_type"],
                "best_model": r["best_model"],
                "primary_metric_name": r["primary_metric_name"],
                "primary_metric_value": r["primary_metric_value"],
                "metrics": json.loads(r["metrics_json"] or "{}"),
                "hyperparameters": json.loads(r["hyperparams_json"] or "{}"),
                "model_artifact_path": r["model_artifact_path"],
                "created_at": r["created_at"],
            })
        return results
    except Exception as e:
        logger.error(f"Failed to fetch experiments: {e}")
        return []
