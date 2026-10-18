import os
import uuid
import logging
from typing import Union, Optional
import pandas as pd

from backend.graph.state import AgentState
from backend.services.r2_service import r2_service
from backend.services.supabase_service import db_service
from backend.services.cleaner import strip_column_names
from backend.services.upload_limits import parse_upload
from backend.config import MAX_UPLOAD_BYTES

logger = logging.getLogger(__name__)

def load_file_dataframe(source: Union[str, bytes], filename: str = "data.csv", sheet_name: Optional[Union[str, int]] = 0) -> pd.DataFrame:
    """
    Safely loads CSV or Excel files (.xlsx, .xls) from filepath or raw bytes
    with automatic encoding and delimiter detection.
    """
    if isinstance(source, bytes):
        contents = source
    else:
        with open(source, 'rb') as handle:
            contents = handle.read(MAX_UPLOAD_BYTES + 1)
    if '.' not in os.path.basename(filename):
        filename += '.csv'
    return parse_upload(contents, filename, sheet_name=sheet_name)

def csv_loader_node(state: AgentState) -> AgentState:
    """Agent 1 Node: Ingests CSV/Excel dataset, uploads to R2, and registers in Supabase."""
    logger.info("--> Running Agent 1: Dataset Loader (CSV / Excel)")
    
    dataset_name = state.get("dataset_name", "dataset")
    project_id = state.get("project_id") or str(uuid.uuid4())
    errors = state.get("errors", []).copy()

    df = None
    csv_url = state.get("csv_url", "")

    try:
        if state.get("csv_bytes"):
            df = load_file_dataframe(state["csv_bytes"], filename=dataset_name)
        elif state.get("file_path") and os.path.exists(state["file_path"]):
            df = load_file_dataframe(state["file_path"], filename=state["file_path"])
        elif state.get("df_raw") is not None:
            df = state["df_raw"].copy()
        else:
            raise ValueError("No valid file path, bytes, or DataFrame provided.")

        # Standardize column names (strip whitespace)
        df = strip_column_names(df)

        db_service.save_project(name=dataset_name, csv_url=csv_url, project_id=project_id,
                                owner_id=state.get("owner_id"), target_column=state.get("target_column"))
        # Background storage updates the same project, preserving its owner.
        import threading
        def _bg_sync(dframe, pid, dname, target_c):
            try:
                r2_key = f"datasets/{pid}/{dname}.csv"
                url = r2_service.upload_dataframe_csv(dframe, r2_key)
                db_service.save_project(name=dname, csv_url=url, target_column=target_c, project_id=pid)
            except Exception as bg_err:
                logger.debug(f"Background cloud storage notice: {bg_err}")

        threading.Thread(
            target=_bg_sync,
            args=(df.copy(), project_id, dataset_name, state.get("target_column")),
            daemon=True
        ).start()

    except Exception as e:
        logger.error(f"Dataset Loader failed: {e}")
        errors.append(f"Dataset Loader Error: {str(e)}")

    return {
        **state,
        "project_id": project_id,
        "dataset_name": dataset_name,
        "df_raw": df,
        "csv_url": csv_url,
        "errors": errors,
    }
