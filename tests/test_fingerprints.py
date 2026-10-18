import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from backend.services.experiment_tracker import compute_dataset_hash
from backend.tools.caching import compute_dataset_fingerprint


@pytest.fixture
def dataset():
    return pd.read_csv(Path(__file__).parent/'data'/'retail_orders.csv')


def test_middle_row_changes_invalidate_experiment_and_cache_fingerprints(dataset):
    changed = dataset.copy()
    changed.loc[len(changed)//2, 'sales'] += 1
    pd.testing.assert_frame_equal(dataset.head(10), changed.head(10))
    pd.testing.assert_frame_equal(dataset.tail(10), changed.tail(10))
    before, after = compute_dataset_hash(dataset), compute_dataset_hash(changed)
    assert before != after and len(before) == 64
    assert compute_dataset_fingerprint(dataset) == before
    assert compute_dataset_fingerprint(changed) == after
    assert before == compute_dataset_hash(dataset.copy())


@pytest.mark.parametrize('change', ['value', 'dtype', 'name', 'columns', 'rows', 'index', 'index_name'])
def test_fingerprint_covers_values_schema_order_and_index(change):
    frame = pd.DataFrame({'a':np.arange(100), 'b':['value']*100})
    changed = frame.copy()
    if change == 'value': changed.loc[50,'b'] = 'middle'
    elif change == 'dtype': changed['a'] = changed['a'].astype(float)
    elif change == 'name': changed = changed.rename(columns={'a':'renamed'})
    elif change == 'columns': changed = changed[['b','a']]
    elif change == 'rows': changed.iloc[[50,51]] = changed.iloc[[51,50]].to_numpy()
    elif change == 'index': changed.index = pd.Index(range(1,101))
    else: changed.index.name = 'record'
    assert compute_dataset_hash(frame) != compute_dataset_hash(changed)


def test_full_float_precision_nulls_and_ambiguous_labels_are_distinct():
    frame = pd.DataFrame({'a':[1.0]*100})
    changed = frame.copy(); changed.loc[50,'a'] = np.nextafter(1.0, 2.0)
    assert compute_dataset_hash(frame) != compute_dataset_hash(changed)
    assert compute_dataset_hash(pd.DataFrame(columns=['a,b','c'])) != compute_dataset_hash(pd.DataFrame(columns=['a','b,c']))
    hashes = {compute_dataset_hash(pd.DataFrame({'a':pd.Series([item], dtype=object)})) for item in (None, np.nan, pd.NA, 'nan')}
    assert len(hashes) == 4
    assert compute_dataset_hash(pd.DataFrame([[1]], columns=[1])) != compute_dataset_hash(pd.DataFrame([[1]], columns=['1']))


def test_datetime_nullable_category_and_duplicate_indexes_hash_deterministically():
    frame = pd.DataFrame({'date':pd.date_range('2025-01-01',periods=3,tz='UTC'),
        'value':pd.Series([1,None,3],dtype='Int64'),
        'kind':pd.Categorical(['a','b','a'], categories=['a','b','unused'], ordered=True)})
    frame.index = pd.MultiIndex.from_tuples([('a',1),('a',1),('b',2)])
    assert compute_dataset_hash(frame) == compute_dataset_hash(frame.copy())
    changed = frame.copy(); changed['kind'] = changed['kind'].cat.reorder_categories(['b','a','unused'])
    assert compute_dataset_hash(frame) != compute_dataset_hash(changed)


def test_cache_queries_preserve_case_sensitive_literals_and_whitespace(dataset):
    assert compute_dataset_fingerprint(dataset, "SELECT * WHERE region='East'") != compute_dataset_fingerprint(dataset, "SELECT * WHERE region='east'")
    assert compute_dataset_fingerprint(dataset, "'a '") != compute_dataset_fingerprint(dataset, "'a'")
    assert compute_dataset_fingerprint(dataset, 'question') == compute_dataset_fingerprint(dataset.copy(), 'question')


def test_changed_middle_row_cannot_retrieve_cached_result(dataset, tmp_path, monkeypatch):
    from backend.tools import caching
    monkeypatch.setattr(caching, 'CACHE_DIR', tmp_path)
    monkeypatch.setattr(caching, '_MEMORY_CACHE', {})
    key = compute_dataset_fingerprint(dataset, 'question')
    caching.set_cached_result(key, {'total':float(dataset.sales.sum())})
    changed = dataset.copy(); changed.loc[300,'sales'] += 100
    changed_key = compute_dataset_fingerprint(changed, 'question')
    assert caching.get_cached_result(changed_key) is None
    assert caching.get_cached_result(key)['total'] == float(dataset.sales.sum())
    caching._MEMORY_CACHE.clear()
    assert caching.get_cached_result(changed_key) is None
    assert caching.get_cached_result(key) is not None


def test_hash_version_invalidates_legacy_keys_and_bytes_cover_all_content(dataset):
    old = hashlib.sha256()
    old.update(str(dataset.shape).encode())
    old.update(','.join(dataset.columns).encode())
    old.update(','.join(str(t) for t in dataset.dtypes).encode())
    old.update(pd.concat([dataset.head(10),dataset.tail(10)]).to_json(date_format='iso').encode())
    assert old.hexdigest() != compute_dataset_fingerprint(dataset)
    assert compute_dataset_hash(b'head-middle-tail') != compute_dataset_hash(b'head-MIDDLE-tail')
    assert compute_dataset_hash(bytearray(b'content')) == compute_dataset_hash(b'content')
    with pytest.raises(TypeError): compute_dataset_hash(object())
    with pytest.raises(TypeError): compute_dataset_hash(pd.DataFrame({'a':[object()]}))


def test_experiment_api_exposes_the_recorded_dataset_version(client, accounts, monkeypatch):
    import backend.services.experiment_tracker as tracker
    from tests.test_security import upload
    pid = upload(client, accounts[0])
    digest = compute_dataset_hash(pd.DataFrame({'x':range(100)}))
    assert tracker.log_experiment('hash-'+pid,pid,'test',digest,'x','regression','Ridge','r2_score',.8,{}, {})
    response = client.get(f'/api/experiments/{pid}', headers=accounts[0])
    assert response.status_code == 200
    assert response.json()[0]['dataset_hash'] == digest
    assert client.get(f'/api/experiments/{pid}', headers=accounts[1]).status_code == 404
