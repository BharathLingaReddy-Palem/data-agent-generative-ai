"""Manual authenticated live profile check; creates a dataset on the backend."""
import os
from pathlib import Path
from test_api_session import authenticated_session


def main():
    base_url = os.environ.get('DS_TEST_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    with authenticated_session(base_url) as session:
        with (Path(__file__).parent/'data'/'test_noisy_sales.csv').open('rb') as source:
            response = session.post(base_url+'/api/profile',
                files={'file':('test_noisy_sales.csv', source, 'text/csv')}, timeout=30)
        response.raise_for_status()
        profile = response.json()
        assert profile['project_id'], 'Profile did not create a project.'
        assert profile['overview']['total_rows'] > 0, 'Dataset is empty.'
        assert profile['columns'], 'Column profiles are missing.'
        assert 0 <= profile['health']['score'] <= 100, 'Invalid health score.'
        print('Profile verified:', profile['overview']['total_rows'], 'rows; health', profile['health']['score'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
