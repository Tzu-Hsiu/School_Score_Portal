import streamlit as st
import pandas as pd
from core.data_loader import initialize_data
from core.auth import init_session_state, render_login_ui
from views import admin
from views import dashboard

# Ensure pandas doesn't throw warnings for future downcasting behavior
pd.set_option('future.no_silent_downcasting', True)

st.set_page_config(page_title="Student Score Portal", layout="wide")
st.title("📊 學生學習深度分析系統 (Advanced Student Analytics)")

# --- 1. Initialize State and Load Data ---
init_session_state()
df, col_info, available_exams, exclude_stats = initialize_data()

# --- 2. Render Login UI ---
if not st.session_state.logged_in:
    render_login_ui(df)

# --- 3. Main Application Routing ---
if st.session_state.logged_in:
    is_virtual = st.session_state.is_virtual_account
    is_teacher = st.session_state.is_teacher
    student_data = st.session_state.student_data
    student_name = st.session_state.student_name

    if is_teacher:
        admin.render(df, col_info, available_exams, exclude_stats)
    else:
        dashboard.render(df, col_info, available_exams, exclude_stats, is_virtual, student_data, student_name)