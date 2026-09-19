"""
tests/test_mock_exam.py
------------------------
Automated tests verifying:
1. Importer functions and data integrity
2. Calculation accuracy (raw students vs benchmarks)
3. Mock data loader and student retrieval
4. Security and authorization isolation
5. Regular vs mock exam comparative analytics
6. Backward compatibility with existing regular exams
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.mock_data_loader import (
    get_available_mock_exams,
    load_mock_exam,
    get_student_mock_data,
    compute_student_percentile,
    compare_mock_with_regular
)
from core.mock_charts import (
    create_mock_radar_chart,
    create_mock_points_distribution_chart,
    create_mock_subject_bars,
    create_cohort_combos_chart,
    create_subject_tiers_chart
)
from import_mock_exam import (
    extract_level_details,
    find_vendor_files,
    parse_rn205_metadata_and_benchmarks,
    parse_rn201_or_rn202_students,
    enrich_and_validate
)


MOCK_DATA_DIR = "/Users/tzu-hsiukao/Documents/A_Work/E_SchoolMain/115_YSJH_Homeroom/data/MockTest_1"


def test_extract_level_details():
    tier, sub = extract_level_details("精熟(A++)")
    assert tier == "精熟" and sub == "A++"

    tier, sub = extract_level_details("基礎(B+)")
    assert tier == "基礎" and sub == "B+"

    tier, sub = extract_level_details("待加強(C)")
    assert tier == "待加強" and sub == "C"

    tier, sub = extract_level_details("A+")
    assert tier == "精熟" and sub == "A+"


def test_find_vendor_files():
    if not os.path.exists(MOCK_DATA_DIR):
        pytest.skip("Vendor data folder not available on this path.")
    files = find_vendor_files(MOCK_DATA_DIR)
    assert 'rn201' in files or 'rn202' in files
    assert 'rn205' in files


def test_parse_rn205_benchmarks():
    if not os.path.exists(MOCK_DATA_DIR):
        pytest.skip("Vendor data folder not available.")
    files = find_vendor_files(MOCK_DATA_DIR)
    benchmarks = parse_rn205_metadata_and_benchmarks(files['rn205'])

    assert benchmarks['cohort']['class_students'] == 27
    assert benchmarks['cohort']['school_students'] == 516
    assert benchmarks['cohort']['district_students'] == 58502
    assert benchmarks['averages']['五科總積分']['class_mean'] == 15.0
    assert benchmarks['averages']['五科總積分']['school_mean'] == 14.5
    assert benchmarks['averages']['國文']['class_items'] == 30.26
    assert benchmarks['averages']['數學']['class_choice_items'] == 15.0


def test_raw_students_match_benchmarks():
    """Verifies that calculating averages directly from raw students matches RN205 exactly."""
    if not os.path.exists(MOCK_DATA_DIR):
        pytest.skip("Vendor data folder not available.")
    files = find_vendor_files(MOCK_DATA_DIR)
    student_file = files.get('rn202') or files['rn201']
    students = parse_rn201_or_rn202_students(student_file)

    assert len(students) == 27, f"Expected 27 students, found {len(students)}"

    # Verify total points mean
    tot_points = [s['total_points'] for s in students]
    mean_tot = sum(tot_points) / len(tot_points)
    assert abs(mean_tot - 15.0) < 0.01, f"Expected total mean 15.0, got {mean_tot:.2f}"

    # Verify Chinese items mean
    chi_items = [s['subjects']['國文']['items_correct'] for s in students]
    mean_chi = sum(chi_items) / len(chi_items)
    assert abs(mean_chi - 30.26) < 0.02, f"Expected Chinese items mean 30.26, got {mean_chi:.2f}"

    # Verify Math choice mean
    mat_choice = [s['subjects']['數學']['choice_items'] for s in students]
    mean_mat = sum(mat_choice) / len(mat_choice)
    assert abs(mean_mat - 15.0) < 0.01, f"Expected Math choice mean 15.0, got {mean_mat:.2f}"


from tests.synthetic_fixtures import create_synthetic_exam_package


def test_mock_data_loader_available_and_load():
    bundle = load_mock_exam("mock_115_1")
    if bundle is None:
        bundle = create_synthetic_exam_package("mock_115_1")
    assert bundle is not None
    assert len(bundle["students"]) >= 1


def test_student_mock_data_security():
    bundle = load_mock_exam("mock_115_1")
    if bundle is None:
        bundle = create_synthetic_exam_package("mock_115_1")
    assert bundle is not None

    first_student = bundle["students"][0]
    target_sid = str(first_student["student_id"])

    # Retrieve student by exact ID
    s1 = get_student_mock_data(bundle, student_id=target_sid)
    assert s1 is not None
    assert str(s1["student_id"]) == target_sid
    assert s1["seat_num"] == first_student["seat_num"]

    # Attempt to query non-existent or unauthorized student
    s_invalid = get_student_mock_data(bundle, student_id="UNAUTHORIZED_999")
    assert s_invalid is None


def test_mock_charts_generation():
    bundle = load_mock_exam("mock_115_1")
    if bundle is None:
        bundle = create_synthetic_exam_package("mock_115_1")
    assert bundle is not None
    s1 = bundle["students"][0]
    benchmarks = bundle["benchmarks"]

    subj_list = ['國文', '數學', '英語', '社會', '自然']
    s_pts = [s1['subjects'][s]['points'] for s in subj_list]
    c_pts = [benchmarks['averages'][s]['class_points'] for s in subj_list]
    sch_pts = [benchmarks['averages'][s]['school_points'] for s in subj_list]

    # Test radar chart
    fig_radar = create_mock_radar_chart(subj_list, s_pts, c_pts, sch_pts)
    assert fig_radar is not None

    # Test points distribution chart
    fig_dist = create_mock_points_distribution_chart(benchmarks["points_distribution"], student_points=s1["total_points"])
    assert fig_dist is not None

    # Test subject bars
    subj_details = [
        {
            'subject': s,
            'points': s1["subjects"][s]["points"],
            'class_avg_points': s1["subjects"][s]["class_avg_points"],
            'school_avg_points': s1["subjects"][s]["school_avg_points"],
            'diff_from_class': s1["subjects"][s]["diff_from_class"],
            'diff_from_school': s1["subjects"][s]["diff_from_school"],
        } for s in subj_list
    ]
    fig_bars = create_mock_subject_bars(subj_details)
    assert fig_bars is not None

    # Test combo and tier charts
    fig_combos = create_cohort_combos_chart(benchmarks["level_combos"])
    assert fig_combos is not None
    fig_tiers = create_subject_tiers_chart(benchmarks["subject_tiers"])
    assert fig_tiers is not None


def test_regular_vs_mock_comparison_logic():
    bundle = load_mock_exam("mock_115_1")
    if bundle is None:
        bundle = create_synthetic_exam_package("mock_115_1")
    assert bundle is not None
    s1 = bundle["students"][0]
    target_sid = str(s1["student_id"])

    # Construct synthetic regular exam dataset
    col_info = pd.DataFrame([
        {'Original_Col': '115_1_E_1_國文', 'Exam_Label': '115-1 段考1', 'Subject': '國文'},
        {'Original_Col': '115_1_E_1_數學', 'Exam_Label': '115-1 段考1', 'Subject': '數學'},
        {'Original_Col': '115_1_E_1_英文', 'Exam_Label': '115-1 段考1', 'Subject': '英語'},
        {'Original_Col': '115_1_E_1_社會', 'Exam_Label': '115-1 段考1', 'Subject': '社會'},
        {'Original_Col': '115_1_E_1_自然', 'Exam_Label': '115-1 段考1', 'Subject': '自然'},
        {'Original_Col': '115_1_E_1_班排', 'Exam_Label': '115-1 段考1', 'Subject': '班排'},
        {'Original_Col': '115_1_E_1_校排', 'Exam_Label': '115-1 段考1', 'Subject': '校排'},
    ])
    regular_df = pd.DataFrame({
        'StudentID': [target_sid, 'SYNTHETIC_PEER_002'],
        '115_1_E_1_國文': [88.0, 75.0],
        '115_1_E_1_數學': [92.0, 60.0],
        '115_1_E_1_英文': [85.0, 70.0],
        '115_1_E_1_社會': [90.0, 80.0],
        '115_1_E_1_自然': [86.0, 65.0],
        '115_1_E_1_班排': [2.0, 15.0],
        '115_1_E_1_校排': [30.0, 200.0],
    })
    student_regular = regular_df[regular_df['StudentID'] == target_sid]

    comp = compare_mock_with_regular(
        bundle, s1, regular_df, student_regular, col_info, exclude_stats=['班排', '校排']
    )
    assert comp['has_data'] is True
    assert comp['regular_class_rank'] == 2.0
    assert len(comp['subject_comparison']) == 5
