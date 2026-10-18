"""One JSON contract shared by synchronous and queued analysis."""
from backend.services.serializer import sanitize_for_json
from backend.services.report_artifacts import report_metadata


def build_analysis_response(project_id, state, report_root=None):
    fields = ('analysis_plan','schema_metadata','quality_audit','kpi_results','eda_results',
              'diagnostic_results','hypothesis_results','trend_results','benchmark_results')
    result = {key: state.get(key, {}) for key in fields}
    artifacts = report_metadata(project_id, state, report_root)
    result.update(project_id=project_id, dataset_name=state.get('dataset_name'),
        health_score=state.get('health_score'), eda_insights=state.get('eda_insights',''),
        charts=state.get('charts',[]), execution_steps=state.get('execution_steps',[]),
        errors=state.get('errors',[]), report_summary=state.get('report_summary',''),
        report_markdown=state.get('report_markdown',''), report_artifacts=artifacts,
        report_pdf_url=artifacts['pdf']['download_url'],
        report_pptx_url=artifacts['pptx']['download_url'])
    result['executive_report'] = dict(summary=result['report_summary'], markdown=result['report_markdown'],
        pdf_url=result['report_pdf_url'], pptx_url=result['report_pptx_url'])
    return sanitize_for_json(result)
