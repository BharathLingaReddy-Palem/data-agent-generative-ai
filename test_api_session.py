"""Shared authenticated session for manual live API checks."""
import os
import requests


def authenticated_session(base_url):
    username=os.environ.get('DS_TEST_USERNAME')
    password=os.environ.get('DS_TEST_PASSWORD')
    if not username or not password:
        raise RuntimeError('Set DS_TEST_USERNAME and DS_TEST_PASSWORD to an existing local account before running live API checks.')
    session=requests.Session()
    response=session.post(base_url+'/api/auth/login',json=dict(username=username,password=password),timeout=15)
    response.raise_for_status()
    session.headers['Authorization']='Bearer '+response.json()['access_token']
    return session
