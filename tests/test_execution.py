import pandas as pd
import pytest
from backend.tools.python_tool import execute_python


@pytest.fixture
def data():
    return pd.DataFrame({'region':['East','West','East','West'],'sales':[100,200,50,0],'profit':[20,-10,-10,0]})


@pytest.mark.parametrize('code,expected',[
    ("result=df['sales'].sum()",350),
    ("result=df.groupby('region')['sales'].sum().to_dict()",{'East':150,'West':200}),
    ("result=df[df['sales']>100]['sales'].mean()",200),
    ("result=df['profit'].sum()",0),
    ("result=df['region'].str.lower().value_counts().to_dict()",{'east':2,'west':2}),
    ("result=df.groupby('region').agg({'sales':'sum','profit':'mean'}).round(2).to_dict()",{'sales':{'East':150,'West':200},'profit':{'East':5,'West':-5}}),
])
def test_analytics(data,code,expected):
    result=execute_python(code,data)
    assert result['success'],result
    assert result['result']==expected


@pytest.mark.parametrize('code',[
    "import os\nresult=os.environ", "result=open('secret.txt').read()",
    "result=df.__class__.__mro__", "result=pd.read_csv('secret.csv')",
    "result=df.to_csv('exfiltration.csv')", "result=df.agg('to_csv')",
    "result=df.groupby('region').agg('to_pickle')", "result=np.load('model.pkl')",
    "result=getattr(df,'to_pickle')('model.pkl')", "while True: pass",
    "result=df.apply(lambda x: x)", "result=df.query('sales > 0')",
    "result=__import__('subprocess').run(['whoami'])", "result=[1]*1000000000",
    "result=(x for x in df)", "result=eval('1+1')",
])
def test_unsafe_operations_blocked(data,code):
    result=execute_python(code,data)
    assert not result['success'],result
    assert 'PolicyError' in result['error'],result


def test_wall_clock_limit(data):
    result=execute_python("result=df['sales'].sum()",data,timeout_seconds=0.01)
    assert not result['success'] and 'timed out' in result['error'],result


def test_resource_limit_leaves_parent_alive(data):
    result=execute_python("result=df['sales'].sum()",data,memory_mb=64)
    assert not result['success'],result
    assert execute_python("result=len(df)",data)['result']==4


def test_dataframe_not_modified(data):
    original=data.copy()
    result=execute_python("result=df.fillna(0).head(2)",data)
    assert result['success'],result
    pd.testing.assert_frame_equal(data,original)


def test_concurrent_worker_capacity(data,monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    import backend.tools.python_tool as tool
    ready=threading.Barrier(3)
    release=threading.Event()
    def occupied(*args,**kwargs):
        ready.wait(timeout=5)
        assert release.wait(timeout=5)
        return dict(success=True,result=1,stdout='',error=None)
    monkeypatch.setattr(tool,'_execute_python',occupied)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(tool.execute_python,'result=1',data) for _ in range(2)]
        try:
            ready.wait(timeout=5)
            result=tool.execute_python('result=1',data)
            assert not result['success'] and 'busy' in result['error']
        finally:
            release.set()
        assert all(f.result()['success'] for f in futures)
