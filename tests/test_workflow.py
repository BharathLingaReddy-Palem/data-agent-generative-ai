import backend.graph.workflow as workflow


def test_dependencies_and_parallel_error_merge(monkeypatch):
    order=[]
    monkeypatch.setattr(workflow,'csv_loader_node',lambda s:s)
    monkeypatch.setattr(workflow,'supervisor_node',lambda s:dict(s,active_agents=['quality','kpi','eda','hypothesis','visualization','report']))
    def schema(s):
        order.append('schema');return dict(s,schema_metadata={'ready':True},df_clean='normalized dataframe')
    def quality(s):
        assert s['schema_metadata']['ready'];assert s['df_clean']=='normalized dataframe'
        order.append('quality');return dict(s,health_score=90)
    def kpi(s):
        return dict(s,kpi_results={'sales':10},errors=s['errors']+['KPI warning'])
    def eda(s):
        return dict(s,eda_results={'rows':10},errors=s['errors']+['EDA warning'])
    def trend(s):
        order.append('trend');return dict(s,trend_results={'ready':True})
    def hypothesis(s):raise RuntimeError('Hypothesis failure')
    def visualization(s):
        assert s['trend_results']['ready'];order.append('visualization');return dict(s,charts=[{'trend':True}])
    def report(s):
        assert s['charts'];order.append('report');return dict(s,report_summary='done')
    for name,fn in [('schema',schema),('quality',quality),('kpi',kpi),('eda',eda),('trend',trend),('hypothesis',hypothesis),('visualization',visualization),('report',report)]:
        monkeypatch.setattr(workflow,name+'_agent_node',fn)
    result=workflow.run_analyst_pipeline(dict(execution_steps=[],errors=[]))
    assert order.index('schema')<order.index('quality')
    assert order.index('trend')<order.index('visualization')<order.index('report')
    assert result['kpi_results']=={'sales':10} and result['eda_results']=={'rows':10}
    assert 'KPI warning' in result['errors'] and 'EDA warning' in result['errors']
    assert any('Hypothesis failure' in e for e in result['errors'])


def test_parallel_failures_preserve_warnings_and_duplicate_occurrences(monkeypatch):
    monkeypatch.setattr(workflow,'csv_loader_node',lambda s:s)
    monkeypatch.setattr(workflow,'supervisor_node',lambda s:dict(s,active_agents=['kpi','eda']))
    monkeypatch.setattr(workflow,'schema_agent_node',lambda s:s)
    monkeypatch.setattr(workflow,'trend_agent_node',lambda s:s)
    def kpi(s):
        s['errors'].extend(['shared warning','shared warning'])
        s['execution_steps'].append('KPI attempted')
        raise RuntimeError('KPI failed')
    def eda(s):
        return dict(s,errors=s['errors']+['shared warning','EDA failed'])
    monkeypatch.setattr(workflow,'kpi_agent_node',kpi)
    monkeypatch.setattr(workflow,'eda_agent_node',eda)
    result=workflow.run_analyst_pipeline(dict(errors=['existing'],execution_steps=['loaded']))
    assert result['errors'].count('existing')==1
    assert result['errors'].count('shared warning')==3
    assert 'EDA failed' in result['errors'] and any('KPI failed' in e for e in result['errors'])
    assert result['execution_steps']==['loaded','KPI attempted']


def test_progress_tracks_completed_stages_and_callback_never_leaks(monkeypatch):
    progress = []
    monkeypatch.setattr(workflow,'csv_loader_node',lambda s:s)
    monkeypatch.setattr(workflow,'supervisor_node',lambda s:dict(s,active_agents=['schema','quality','kpi','eda']))
    def node(name):
        def run(state):
            assert '_progress_callback' not in state
            assert progress[-1][1].startswith('Running ')
            assert name in progress[-1][1]
            return state
        return run
    for name in ('schema','quality','kpi','eda','trend'):
        monkeypatch.setattr(workflow,name+'_agent_node',node(name))
    result = workflow.run_analyst_pipeline(dict(errors=[],execution_steps=[],_progress_callback=lambda pct,step:progress.append((pct,step))))
    assert '_progress_callback' not in result
    assert [p for p,s in progress] == sorted(p for p,s in progress)
    assert any(step=='Finished schema' for pct,step in progress)
    assert any(step=='Finished quality' for pct,step in progress)
    assert any(step=='Finished kpi + eda' for pct,step in progress)
    assert max(p for p,s in progress) < 100  # Only job completion can report 100.
