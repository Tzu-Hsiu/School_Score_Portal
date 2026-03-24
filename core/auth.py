import streamlit as st
import pandas as pd

def init_session_state():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.is_virtual_account = False
        st.session_state.is_teacher = False
        st.session_state.student_data = pd.DataFrame()
        st.session_state.student_name = ""

def render_login_ui(df):
    st.markdown("請輸入學號與專屬密碼來查詢成績 (Please enter Student ID and PIN)")
    default_id = st.query_params.get("id", "")

    col1, col2 = st.columns(2)
    with col1:
        user_id = st.text_input("學號 / 帳號 (ID)", value=default_id)
    with col2:
        user_pin = st.text_input("密碼 (PIN)", type="password")

    login_button = st.button("登入查詢 (Login)")

    try: TEACHER_SECURE_PIN = str(st.secrets["teacher"]["pin"])
    except: TEACHER_SECURE_PIN = None

    try: VIRTUAL_SECURE_PIN = str(st.secrets["virtual"]["pin"])
    except: VIRTUAL_SECURE_PIN = None

    if login_button:
        is_virtual = (user_id == 'demo' and user_pin == VIRTUAL_SECURE_PIN and VIRTUAL_SECURE_PIN is not None)
        is_teacher = (user_id == 'teacher' and user_pin == TEACHER_SECURE_PIN and TEACHER_SECURE_PIN is not None)
        
        if is_teacher:
            st.session_state.logged_in = True
            st.session_state.is_teacher = True
            st.session_state.is_virtual_account = False
            st.session_state.student_data = df
            st.session_state.student_name = "教師管理員"
            st.rerun()
        elif is_virtual:
            st.session_state.logged_in = True
            st.session_state.is_teacher = False
            st.session_state.is_virtual_account = True
            st.session_state.student_data = pd.DataFrame()
            st.session_state.student_name = "班級總覽"
            st.rerun()
        else:
            s_data = df[(df['StudentID'] == user_id) & (df['Pin'] == user_pin)]
            if s_data.empty:
                st.error("學號或密碼錯誤，請重新確認。(Invalid ID or PIN.)")
                st.session_state.logged_in = False
            else:
                st.session_state.logged_in = True
                st.session_state.is_teacher = False
                st.session_state.is_virtual_account = False
                st.session_state.student_data = s_data
                st.session_state.student_name = s_data.iloc[0]['Name']
                st.rerun()
