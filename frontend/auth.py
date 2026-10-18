"""Shared login gate for every Streamlit page."""
import streamlit as st
from backend.config import AUTH_ALLOW_REGISTRATION
from backend.services.auth_service import auth_service


def require_login():
    token = st.session_state.get('auth_token')
    if token:
        try:
            user = auth_service.authenticate(token)
            with st.sidebar:
                st.caption('Signed in as ' + user['username'])
                if st.button('Sign out', key='auth_logout'):
                    auth_service.logout(user['session_id'])
                    st.session_state.clear()
                    st.rerun()
            return user
        except ValueError:
            st.session_state.clear()
    st.title('Sign in to Data Analyst')
    creating = st.checkbox('Create a new account') if AUTH_ALLOW_REGISTRATION else False
    with st.form('account_login'):
        username = st.text_input('Username')
        password = st.text_input('Password (at least 12 characters for a new account)', type='password')
        submitted = st.form_submit_button('Create account' if creating else 'Sign in')
    if submitted:
        try:
            if creating:
                auth_service.register(username,password)
            result = auth_service.login(username,password)
            st.session_state['auth_token'] = result['access_token']
            st.rerun()
        except (ValueError,PermissionError) as exc:
            st.error(str(exc))
    st.stop()
