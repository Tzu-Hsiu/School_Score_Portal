"""
core/mock_data_loader.py
-------------------------
Loads and manages normalized Mock Exam (國中會考模擬考) datasets,
provides student lookups, statistical calculations, and comparative analysis
between regular exams (段考) and mock exams (模擬考).
"""

import os
import json
import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any, Optional, Tuple
from core.mock_sheets_sync import (
    fetch_mock_index_from_sheets,
    fetch_mock_exam_from_sheets,
    get_exam_sort_key
)


MOCK_EXAMS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "mock_exams")


def get_gspread_client() -> Optional[Any]:
    """
    Acquires an authorized gspread client using either Streamlit secrets
    or a local .streamlit/secrets.toml file.
    """
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly"
    ]

    # 1. Try st.secrets
    try:
        if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
            gcp_creds = dict(st.secrets["gcp_service_account"])
            creds = Credentials.from_service_account_info(gcp_creds, scopes=scopes)
            return gspread.authorize(creds)
    except Exception:
        pass

    # 2. Try reading .streamlit/secrets.toml directly
    try:
        import toml
        secrets_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".streamlit",
            "secrets.toml"
        )
        if os.path.exists(secrets_path):
            secrets = toml.load(secrets_path)
            if "gcp_service_account" in secrets:
                creds = Credentials.from_service_account_info(
                    dict(secrets["gcp_service_account"]),
                    scopes=scopes
                )
                return gspread.authorize(creds)
    except Exception:
        pass

    return None


@st.cache_data(ttl=600)
def get_available_mock_exams() -> List[Dict[str, Any]]:
    """
    Discovers all available mock exams.
    First checks the Google Spreadsheet (School_Master_Score -> MockExam_Index).
    Falls back to or supplements with local cached bundles in data/mock_exams.
    Returns list of exam metadata sorted chronologically.
    """
    exams = []
    seen_ids = set()

    # 1. Primary: Try Google Sheets
    client = get_gspread_client()
    if client:
        try:
            remote_exams = fetch_mock_index_from_sheets(client)
            for ex in remote_exams:
                eid = ex.get('exam_id')
                if eid and eid not in seen_ids:
                    exams.append(ex)
                    seen_ids.add(eid)
        except Exception as e:
            # Non-blocking fallback
            pass

    # 2. Fallback / Local Cache: Check data/mock_exams
    if os.path.exists(MOCK_EXAMS_DIR):
        for fname in sorted(os.listdir(MOCK_EXAMS_DIR)):
            if fname.endswith(".json") and not fname.startswith("."):
                path = os.path.join(MOCK_EXAMS_DIR, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        meta = data.get("metadata", {})
                        eid = meta.get("exam_id")
                        if eid and eid not in seen_ids:
                            meta["file_path"] = path
                            meta["source"] = "local_json"
                            exams.append(meta)
                            seen_ids.add(eid)
                        elif eid and eid in seen_ids:
                            # Attach local file_path as fallback if available
                            for ex in exams:
                                if ex.get("exam_id") == eid:
                                    ex["file_path"] = path
                except Exception as e:
                    print(f"Error reading local mock exam file {fname}: {e}")

    # Sort deterministically: school_year -> round_number -> test_date
    exams.sort(key=get_exam_sort_key)
    return exams


@st.cache_data(ttl=600)
def load_mock_exam(exam_id: str, include_questions: bool = True) -> Optional[Dict[str, Any]]:
    """
    Loads a full mock exam bundle by exam_id.
    Primary: Queries Google Sheets (School_Master_Score).
    Fallback: Reads local JSON file from data/mock_exams.
    Supports include_questions=False for lightweight queries.
    """
    # 1. Primary: Try Google Sheets
    client = get_gspread_client()
    if client:
        try:
            bundle = fetch_mock_exam_from_sheets(client, exam_id, include_questions=include_questions)
            if bundle:
                return bundle
        except Exception as e:
            # Fallback to local file
            pass

    # 2. Fallback: Search in available mock exams list
    available = get_available_mock_exams()
    for ex in available:
        if ex.get("exam_id") == exam_id and "file_path" in ex:
            if os.path.exists(ex["file_path"]):
                with open(ex["file_path"], "r", encoding="utf-8") as f:
                    return json.load(f)

    # 3. Direct local file check
    direct_path = os.path.join(MOCK_EXAMS_DIR, f"{exam_id}.json")
    if os.path.exists(direct_path):
        with open(direct_path, "r", encoding="utf-8") as f:
            return json.load(f)

    return None


def load_student_mock_record(
    exam_id: str,
    student_id: str,
    student_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Convenience method to load and return exclusively the authenticated student's record.
    """
    bundle = load_mock_exam(exam_id)
    if not bundle:
        return None
    return get_student_mock_data(bundle, student_id=student_id, student_name=student_name)


def get_student_mock_data(
    exam_data: Dict[str, Any],
    student_id: Optional[str] = None,
    student_name: Optional[str] = None,
    seat_num: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Securely retrieves an individual student's mock exam record from the bundle.
    Matches by student_id first, then student_name, then seat_num.
    """
    if not exam_data or "students" not in exam_data:
        return None

    students = exam_data["students"]

    # 1. Match by StudentID
    if student_id:
        sid_str = str(student_id).strip()
        for s in students:
            if str(s.get("student_id", "")).strip() == sid_str:
                return s

    # 2. Match by Student Name
    if student_name:
        sname_str = str(student_name).strip()
        for s in students:
            if str(s.get("name", "")).strip() == sname_str:
                return s

    # 3. Match by Seat Number
    if seat_num is not None:
        try:
            snum_int = int(seat_num)
            for s in students:
                if s.get("seat_num") == snum_int:
                    return s
        except (ValueError, TypeError):
            pass

    return None


def compute_student_percentile(points: float, points_distribution: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Looks up exact PR / Top% in official points distribution table.
    """
    result = {'class_top_pct': None, 'school_top_pct': None, 'district_top_pct': None}
    if not points_distribution:
        return result

    for row in points_distribution:
        if row.get('points') == points:
            result['class_top_pct'] = row.get('class_top_pct')
            result['school_top_pct'] = row.get('school_top_pct')
            result['district_top_pct'] = row.get('district_top_pct')
            break

    # If exact point not matched, interpolate or find closest
    if result['school_top_pct'] is None and points_distribution:
        sorted_dist = sorted(points_distribution, key=lambda r: r['points'], reverse=True)
        for r in sorted_dist:
            if points >= r['points']:
                result['class_top_pct'] = r.get('class_top_pct')
                result['school_top_pct'] = r.get('school_top_pct')
                result['district_top_pct'] = r.get('district_top_pct')
                break

    return result


def compare_mock_with_regular(
    mock_exam_data: Dict[str, Any],
    student_mock: Dict[str, Any],
    regular_df: pd.DataFrame,
    student_regular_data: pd.DataFrame,
    col_info: pd.DataFrame,
    exclude_stats: List[str]
) -> Dict[str, Any]:
    """
    Statistically sound comparison between regular exams (段考) and mock exam (模擬考).
    
    Why raw scores cannot be directly compared:
    - Regular exams use 0-100 continuous score scales, designed around school curriculum pacing.
    - Mock exams use the Taiwan Comprehensive Assessment Program (CAP / 會考) criteria-referenced
      3-tier 7-level system (A++, A+, A, B++, B+, B, C) with comprehensive scope (第1~2冊).
    
    Valid normalized metrics:
    1. Class Standing (% from Top): `(class_rank / class_size) * 100`
    2. School Standing (% from Top): `(school_rank / school_size) * 100`
    3. Relative Strengths Consistency: compares subject rankings within student between regular and mock.
    """
    if student_mock is None or student_regular_data.empty or regular_df.empty or col_info.empty:
        return {'has_data': False}

    # Find latest available regular exam with scores for this student
    available_exams = col_info['Exam_Label'].unique().tolist()
    latest_regular_exam = None
    regular_subj_ranks = {}

    for ex in reversed(available_exams):
        e_cols = col_info[col_info['Exam_Label'] == ex]
        s_cols = e_cols[~e_cols['Subject'].isin(exclude_stats)]
        has_scores = False
        for _, r in s_cols.iterrows():
            c_name = r['Original_Col']
            if c_name in student_regular_data.columns and pd.notna(student_regular_data[c_name].iloc[0]):
                has_scores = True
                break
        if has_scores:
            latest_regular_exam = ex
            break

    if not latest_regular_exam:
        return {'has_data': False}

    # Extract regular exam ranks and metrics
    e_cols = col_info[col_info['Exam_Label'] == latest_regular_exam]
    crank_col = e_cols[e_cols['Subject'] == '班排']['Original_Col']
    srank_col = e_cols[e_cols['Subject'] == '校排']['Original_Col']

    reg_c_rank = student_regular_data[crank_col.values[0]].iloc[0] if not crank_col.empty else np.nan
    reg_s_rank = student_regular_data[srank_col.values[0]].iloc[0] if not srank_col.empty else np.nan
    reg_c_total = len(regular_df[crank_col.values[0]].dropna()) if not crank_col.empty else len(regular_df)
    reg_s_total = 520

    reg_c_pct = round((reg_c_rank / reg_c_total) * 100, 1) if pd.notna(reg_c_rank) and reg_c_total > 0 else np.nan
    reg_s_pct = round((reg_s_rank / reg_s_total) * 100, 1) if pd.notna(reg_s_rank) else np.nan

    # Extract mock exam ranks
    mock_c_rank = student_mock.get('rankings', {}).get('class_rank')
    mock_s_rank = student_mock.get('rankings', {}).get('school_rank')
    cohort = mock_exam_data.get('metadata', {}).get('cohort', {})
    mock_c_total = cohort.get('class_students', 27)
    mock_s_total = cohort.get('school_students', 516)

    mock_c_pct = round((mock_c_rank / mock_c_total) * 100, 1) if mock_c_rank and mock_c_total > 0 else np.nan
    mock_s_pct = round((mock_s_rank / mock_s_total) * 100, 1) if mock_s_rank and mock_s_total > 0 else np.nan

    # Subject consistency analysis
    subject_comparison = []
    for subj in ['國文', '英語', '數學', '社會', '自然']:
        # Regular score & z-score
        reg_subj_col = e_cols[e_cols['Subject'] == subj]['Original_Col']
        reg_score = np.nan
        reg_z = np.nan
        if not reg_subj_col.empty:
            c_name = reg_subj_col.values[0]
            if c_name in regular_df.columns:
                all_s = regular_df[c_name].dropna()
                mean_s = all_s.mean()
                std_s = all_s.std()
                if c_name in student_regular_data.columns:
                    val = student_regular_data[c_name].iloc[0]
                    if pd.notna(val):
                        reg_score = float(val)
                        reg_z = round((reg_score - mean_s) / std_s, 2) if std_s > 0 else 0.0

        # Mock points & diff
        mock_subj_info = student_mock.get('subjects', {}).get(subj, {})
        mock_points = mock_subj_info.get('points')
        mock_level = mock_subj_info.get('sub_level')
        mock_diff_class = mock_subj_info.get('diff_from_class', 0.0)

        # Consistency assessment
        status = "表現持平"
        if pd.notna(reg_z) and mock_points is not None:
            if reg_z >= 0.5 and mock_diff_class >= 0.5:
                status = "平穩優勢"
            elif reg_z <= -0.5 and mock_diff_class <= -0.5:
                status = "需共同加強"
            elif mock_diff_class > reg_z + 0.5:
                status = "模擬考突出"
            elif reg_z > mock_diff_class + 0.5:
                status = "段考優於模考"

        subject_comparison.append({
            'subject': subj,
            'regular_score': reg_score,
            'regular_z': reg_z,
            'mock_level': mock_level,
            'mock_points': mock_points,
            'mock_diff_class': mock_diff_class,
            'status': status
        })

    return {
        'has_data': True,
        'latest_regular_exam': latest_regular_exam,
        'regular_class_rank': reg_c_rank,
        'regular_class_pct': reg_c_pct,
        'regular_school_rank': reg_s_rank,
        'regular_school_pct': reg_s_pct,
        'mock_class_rank': mock_c_rank,
        'mock_class_pct': mock_c_pct,
        'mock_school_rank': mock_s_rank,
        'mock_school_pct': mock_s_pct,
        'subject_comparison': subject_comparison
    }
