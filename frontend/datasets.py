"""Load complete samples and save Streamlit's active dataset using shared services."""
import io
import requests
import pandas as pd
from backend.services.session_store import session_store
from backend.services.supabase_service import db_service
from backend.services.upload_limits import validate_dataset_size


def fetch_sample_dataframe(backend_url, token, metadata):
    response = requests.get(f"{backend_url.rstrip('/')}/api/datasets/{metadata['project_id']}/download",
        headers={'Authorization': 'Bearer ' + token}, timeout=30)
    response.raise_for_status()
    frame = pd.read_csv(io.StringIO(response.text))
    if len(frame) != metadata['shape']['rows']:
        raise ValueError('Sample download did not contain the complete dataset.')
    return frame


def save_active_dataset(state, owner_id):
    project_id = state['project_id']
    validate_dataset_size(state['df'])
    existing = session_store.load(project_id, owner_id) or {}
    existing.update(project_id=project_id, owner_id=owner_id,
        dataset_name=state['dataset_name'], df=state['df'])
    if state.get('analysis') is not None:
        existing['analysis'] = state['analysis']
    session_store.save(project_id, existing)
    db_service.save_project(state['dataset_name'], '', project_id=project_id, owner_id=owner_id)
