import streamlit as st
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

@st.cache_data(ttl=600)
def load_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        gcp_creds = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_creds, scope)
    except KeyError:
        st.error("找不到 `gcp_service_account` 憑證！請確認你的 `.streamlit/secrets.toml` 檔案設定正確。")
        st.stop()
    except Exception as e:
        st.error(f"讀取 Secrets 時發生錯誤 (Error reading secrets): {e}")
        st.stop()
        
    try:
        client = gspread.authorize(creds)
        sheet = client.open("School_Master_Score").sheet1 
        data = sheet.get_all_records()
        return pd.DataFrame(data).replace('', np.nan)
    except Exception as e:
        st.error(f"Google Sheets 連線失敗 (Google API Error): {e}")
        st.stop()


def parse_columns(columns):
    parsed_data = []
    pattern = r"(?P<year>\w+)_(?P<sem>\w+)_(?P<type>[EQ])_(?P<num>[\w\-]+)_+\{(?P<subject>.*?)\}_+\{(?P<detail>.*?)\}"
    for col in columns:
        match = re.match(pattern, str(col))
        if match:
            exam_label = f"{match.group('year')}-{match.group('sem')} 段考{match.group('num')}"
            parsed_data.append({
                "Original_Col": col,
                "Year": match.group("year"),
                "Semester": match.group("sem"),
                "Exam_Type": match.group("type"),
                "Number": match.group("num"),
                "Subject": match.group("subject"),
                "Exam_Label": exam_label
            })
    return pd.DataFrame(parsed_data)


def initialize_data():
    df = load_data()
    col_info = parse_columns(df.columns)
    
    if not col_info.empty:
        col_info.sort_values(by=['Year', 'Semester', 'Number'], inplace=True)
    available_exams = col_info['Exam_Label'].unique().tolist() if not col_info.empty else []
    exclude_stats = ['總分', '平均', '班排', '校排']

    # --- OPTIMIZATION: Convert all exam columns to numeric upfront ---
    exam_cols = col_info['Original_Col'].tolist() if not col_info.empty else []
    for col in exam_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'StudentID' in df.columns:
        df['StudentID'] = df['StudentID'].astype(str)
    if 'Pin' in df.columns:
        df['Pin'] = df['Pin'].astype(str)
    
    # Calculate missing total scores, averages, and class ranks
    for exam in available_exams:
        exam_df = col_info[col_info['Exam_Label'] == exam]
        exam_cols = exam_df['Original_Col'].tolist()
        subject_cols = [col for col in exam_cols if exam_df.loc[exam_df['Original_Col'] == col, 'Subject'].iloc[0] not in exclude_stats]
        
        total_col = next((col for col in exam_cols if exam_df.loc[exam_df['Original_Col'] == col, 'Subject'].iloc[0] == '總分'), None)
        avg_col = next((col for col in exam_cols if exam_df.loc[exam_df['Original_Col'] == col, 'Subject'].iloc[0] == '平均'), None)
        crank_col = next((col for col in exam_cols if exam_df.loc[exam_df['Original_Col'] == col, 'Subject'].iloc[0] == '班排'), None)
        
        if total_col and subject_cols:
            mask = df[total_col].isna()
            if mask.any():
                df.loc[mask, total_col] = df.loc[mask, subject_cols].sum(axis=1, skipna=True)
        
        if avg_col and total_col and subject_cols:
            mask = df[avg_col].isna()
            if mask.any():
                num_subjects = len(subject_cols)
                df.loc[mask, avg_col] = df.loc[mask, total_col] / num_subjects
        
        if crank_col and total_col:
            mask = df[crank_col].isna()
            if mask.any():
                valid_mask = df[total_col].notna()
                if valid_mask.any():
                    ranks = df.loc[valid_mask, total_col].rank(method='min', ascending=False)
                    df.loc[valid_mask, crank_col] = ranks
    
    return df, col_info, available_exams, exclude_stats
