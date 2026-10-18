"""Project-scoped local exports and their public API metadata."""
from pathlib import Path
import re
from backend.config import REPORTS_DIR

REPORT_TYPES = {
    'pdf': ('executive_report.pdf', 'application/pdf'),
    'pptx': ('executive_presentation.pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation'),
}


def report_path(project_id, format, root=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', project_id) or format not in REPORT_TYPES:
        raise ValueError('Invalid report location.')
    base = Path(root if root is not None else REPORTS_DIR).resolve()
    path = base / project_id / REPORT_TYPES[format][0]
    if path.resolve() != path:
        raise ValueError('Report must remain in its project directory.')
    return path


def report_metadata(project_id, state=None, root=None):
    result = {}
    for format, (filename, media_type) in REPORT_TYPES.items():
        path = report_path(project_id, format, root)
        # If this run failed, do not advertise an older run's export as its output.
        generated = state is None or bool(state.get(f'report_{format}_path'))
        available = generated and path.is_file()
        result[format] = dict(available=available, filename=filename, media_type=media_type,
            download_url=f'/api/reports/{project_id}/{format}/download' if available else None)
    return result
