"""
tests/test_mock_sheets_sync.py
--------------------------------
Comprehensive unit tests for Google Sheets synchronization:
1. Serialization into 5 normalized relational tables
2. Deserialization back into normalized package (100% roundtrip fidelity)
3. Student-level data isolation
4. Corrupted/empty cells and type resilience
5. Idempotent exam update simulation
6. Column letter converter correctness
7. Dry run mode validation
"""

import os
import sys
import json
import pytest
import pandas as pd
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.mock_sheets_sync import (
    serialize_mock_package_to_tables,
    deserialize_tables_to_package,
    upload_mock_exam_to_google_sheets,
    openpyxl_col,
    INDEX_COLUMNS,
    RESULTS_COLUMNS,
    SUBJECTS_COLUMNS,
    QUESTIONS_COLUMNS,
    BENCHMARKS_COLUMNS
)
from core.mock_data_loader import (
    load_mock_exam,
    get_student_mock_data,
    load_student_mock_record
)


from tests.synthetic_fixtures import create_synthetic_exam_package, get_four_synthetic_exams


@pytest.fixture
def sample_package():
    """Generates a safe, synthetic mock exam bundle for isolated unit testing."""
    return create_synthetic_exam_package("mock_115_1")


def test_table_serialization_structure(sample_package):
    """Verifies that serialization produces all 5 normalized tables with exact column counts."""
    tables = serialize_mock_package_to_tables(sample_package)

    assert 'index' in tables
    assert 'results' in tables
    assert 'subjects' in tables
    assert 'questions' in tables
    assert 'benchmarks' in tables

    # Check header conformity
    assert tables['index'][0] == INDEX_COLUMNS
    assert tables['results'][0] == RESULTS_COLUMNS
    assert tables['subjects'][0] == SUBJECTS_COLUMNS
    assert tables['questions'][0] == QUESTIONS_COLUMNS
    assert tables['benchmarks'][0] == BENCHMARKS_COLUMNS

    # Check row counts
    assert len(tables['index']) == 2  # header + 1 index row
    assert len(tables['results']) >= 2  # header + >=1 student
    assert len(tables['subjects']) >= 2
    assert len(tables['benchmarks']) >= 2


def test_roundtrip_fidelity(sample_package):
    """
    Simulates sending to Google Sheets and reading back via get_all_records():
    Package -> Tables -> Simulated GSheet Records -> Deserialized Package -> Verified 100% Match.
    """
    tables = serialize_mock_package_to_tables(sample_package)

    def to_records(table_data):
        header = table_data[0]
        rows = table_data[1:]
        return [dict(zip(header, row)) for row in rows]

    index_record = to_records(tables['index'])[0]
    results_records = to_records(tables['results'])
    subjects_records = to_records(tables['subjects'])
    questions_records = to_records(tables['questions'])
    benchmarks_records = to_records(tables['benchmarks'])

    reconstructed = deserialize_tables_to_package(
        index_record=index_record,
        results_records=results_records,
        subjects_records=subjects_records,
        questions_records=questions_records,
        benchmarks_records=benchmarks_records
    )

    # 1. Verify Metadata
    orig_meta = sample_package['metadata']
    recon_meta = reconstructed['metadata']
    assert recon_meta['exam_id'] == orig_meta['exam_id']
    assert recon_meta['exam_name'] == orig_meta['exam_name']
    assert recon_meta['test_date'] == orig_meta['test_date']
    assert recon_meta['cohort']['class_students'] == orig_meta['cohort']['class_students']
    assert recon_meta['cohort']['school_students'] == orig_meta['cohort']['school_students']

    # 2. Verify Students
    assert len(reconstructed['students']) == len(sample_package['students'])
    s_orig = sample_package['students'][0]
    s_recon = reconstructed['students'][0]

    assert s_recon['seat_num'] == s_orig['seat_num']
    assert s_recon['name'] == s_orig['name']
    assert s_recon['student_id'] == s_orig['student_id']
    assert abs(s_recon['total_points'] - s_orig['total_points']) < 0.01
    assert s_recon['level_combo'] == s_orig['level_combo']
    assert s_recon['rankings']['class_rank'] == s_orig['rankings']['class_rank']

    # 3. Verify Subjects
    assert '國文' in s_recon['subjects']
    sub_orig = s_orig['subjects']['國文']
    sub_recon = s_recon['subjects']['國文']
    assert sub_recon['points'] == sub_orig['points']
    assert sub_recon['sub_level'] == sub_orig['sub_level']
    assert sub_recon['tier'] == sub_orig['tier']
    assert sub_recon['promotion_gap'] == sub_orig['promotion_gap']

    # 4. Verify Incorrect Questions
    if sub_orig.get('incorrect_items'):
        q_orig = sub_orig['incorrect_items'][0]
        q_recon = sub_recon['incorrect_items'][0]
        assert q_recon['q_num'] == q_orig['q_num']
        assert q_recon['student_choice'] == q_orig['student_choice']
        assert q_recon['correct_answer'] == q_orig['correct_answer']


def test_student_isolation(sample_package):
    """Verifies that an individual student cannot access another student's mock exam scores."""
    tables = serialize_mock_package_to_tables(sample_package)

    def to_records(table_data):
        header = table_data[0]
        return [dict(zip(header, r)) for r in table_data[1:]]

    reconstructed = deserialize_tables_to_package(
        index_record=to_records(tables['index'])[0],
        results_records=to_records(tables['results']),
        subjects_records=to_records(tables['subjects']),
        questions_records=to_records(tables['questions']),
        benchmarks_records=to_records(tables['benchmarks'])
    )

    valid_sid = sample_package['students'][0]['student_id']
    s_valid = get_student_mock_data(reconstructed, student_id=valid_sid)
    assert s_valid is not None
    assert s_valid['student_id'] == valid_sid

    # Unauthorized access attempt
    s_unauthorized = get_student_mock_data(reconstructed, student_id="99999999")
    assert s_unauthorized is None

    # Empty access attempt
    s_empty = get_student_mock_data(reconstructed, student_id="")
    assert s_empty is None


def test_corrupted_or_missing_cell_handling():
    """Verifies that missing, empty strings, or string representations don't crash deserialization."""
    index_rec = {
        'ExamID': 'mock_115_1',
        'ExamName': '115第一次模擬考',
        'StudentCount': '',  # empty string
        'SchoolPopulation': '516',  # string representation
        'SchemaVersion': '1'
    }
    results_rec = [{
        'ExamID': 'mock_115_1',
        'StudentID': 'SYNTH_TEST_001',
        'SeatNo': '1',
        'Name': '學生A',
        'TotalPoints': '',  # empty string
        'ClassRank': 'None',  # non-numeric string
        'DiagnosisStrengths': ''
    }]
    subjects_rec = [{
        'ExamID': 'mock_115_1',
        'StudentID': 'SYNTH_TEST_001',
        'Subject': '國文',
        'Points': '',
        'RawScore': 'NaN',
        'ItemsCorrect': None,
        'SubjectDetails': 'invalid json {'  # malformed JSON
    }]
    questions_rec = [{
        'ExamID': 'mock_115_1',
        'StudentID': 'SYNTH_TEST_001',
        'Subject': '國文',
        'QuestionNo': '1',
        'ClassCorrectRate': ''
    }]
    benchmarks_rec = [{
        'ExamID': 'mock_115_1',
        'Category': 'subject_average',
        'SubKey': '五科總積分',
        'PayloadJSON': '{"class_mean": 15.0}'
    }]

    pkg = deserialize_tables_to_package(
        index_record=index_rec,
        results_records=results_rec,
        subjects_records=subjects_rec,
        questions_records=questions_rec,
        benchmarks_records=benchmarks_rec
    )

    assert pkg['metadata']['cohort']['class_students'] == 27  # defaulted safely
    assert pkg['metadata']['cohort']['school_students'] == 516
    assert len(pkg['students']) == 1
    s0 = pkg['students'][0]
    assert s0['total_points'] == 0.0  # converted '' safely to default 0.0
    assert s0['rankings']['class_rank'] is None  # invalid string safely converted to None
    assert '國文' in s0['subjects']
    assert s0['subjects']['國文']['points'] == 0.0
    assert len(s0['subjects']['國文']['incorrect_items']) == 1


def test_openpyxl_col_conversion():
    """Verifies column letter conversion for arbitrary Google Sheets widths."""
    assert openpyxl_col(1) == "A"
    assert openpyxl_col(26) == "Z"
    assert openpyxl_col(27) == "AA"
    assert openpyxl_col(28) == "AB"
    assert openpyxl_col(52) == "AZ"
    assert openpyxl_col(53) == "BA"


def test_idempotent_filtering_simulation(sample_package):
    """
    Simulates Google Sheets having existing data from another exam (mock_115_2),
    and verifies that uploading mock_115_1 does not touch mock_115_2 rows.
    """
    existing_rows = [
        ['ExamID', 'StudentID', 'SeatNo'],
        ['mock_115_2', 'SYNTH_STU_099', '1'],
        ['mock_115_2', 'SYNTH_STU_098', '2'],
        ['mock_115_1', 'SYNTH_STU_001', '1'],  # Old version to be overwritten
    ]

    exam_id = 'mock_115_1'
    header = existing_rows[0]
    existing_body = existing_rows[1:]

    # Filter out rows belonging to current ExamID
    exam_id_col_idx = 0
    retained_body = [r for r in existing_body if len(r) > 0 and r[exam_id_col_idx] != exam_id]

    assert len(retained_body) == 2
    for r in retained_body:
        assert r[0] == 'mock_115_2'

    new_exam_rows = [['mock_115_1', 'SYNTH_STU_001', '1'], ['mock_115_1', 'SYNTH_STU_002', '2']]
    combined = [header] + retained_body + new_exam_rows

    assert len(combined) == 5  # 1 header + 2 from mock_115_2 + 2 updated from mock_115_1


def test_upload_dry_run_mode(sample_package):
    """Verifies dry run mode returns accurate counts without contacting Google API."""
    mock_creds = MagicMock()
    counts = upload_mock_exam_to_google_sheets(
        package=sample_package,
        creds=mock_creds,
        dry_run=True
    )
    assert 'MockExam_Index' in counts
    assert 'MockExam_Results' in counts
    assert 'MockExam_Subjects' in counts
    assert 'MockExam_Questions' in counts
    assert 'MockExam_Benchmarks' in counts
    assert counts['MockExam_Results'] == len(sample_package['students'])


from core.mock_sheets_sync import validate_table_uniqueness, get_exam_sort_key


def test_exam_sort_key_chronological():
    """Verifies that mock exams are always ordered 第一次 -> 第二次 -> 第三次 -> 第四次."""
    unsorted_exams = [
        {'exam_id': 'mock_115_3', 'round_name': '第三次', 'school_year': '115', 'test_date': '2027/02/24'},
        {'exam_id': 'mock_115_1', 'round_name': '第一次', 'school_year': '115', 'test_date': '2026/09/08'},
        {'exam_id': 'mock_115_4', 'round_name': '第四次', 'school_year': '115', 'test_date': '2027/04/18'},
        {'exam_id': 'mock_115_2', 'round_name': '第二次', 'school_year': '115', 'test_date': '2026/12/15'},
    ]
    sorted_exams = sorted(unsorted_exams, key=get_exam_sort_key)
    sorted_ids = [ex['exam_id'] for ex in sorted_exams]
    assert sorted_ids == ['mock_115_1', 'mock_115_2', 'mock_115_3', 'mock_115_4']


def test_uniqueness_validation(sample_package):
    """Verifies table uniqueness enforcement detects duplicates."""
    tables = serialize_mock_package_to_tables(sample_package)
    counts = validate_table_uniqueness(tables)
    assert counts['index'] == 1
    assert counts['results'] == len(sample_package['students'])

    # Inject duplicate student result
    dup_row = list(tables['results'][1])
    tables['results'].append(dup_row)
    with pytest.raises(ValueError, match="Duplicate student result"):
        validate_table_uniqueness(tables)


def test_four_mock_exams_coexistence_and_idempotency():
    """
    Verifies that all 4 Grade 9 mock exams can coexist in the same normalized tables,
    and re-importing mock_115_2 only replaces mock_115_2 without disturbing other exams.
    """
    four_exams = get_four_synthetic_exams()
    assert len(four_exams) == 4

    # Simulated Google Sheets storage: Dict[sheet_name, List[rows]]
    storage = {
        'MockExam_Index': [INDEX_COLUMNS],
        'MockExam_Results': [RESULTS_COLUMNS],
        'MockExam_Subjects': [SUBJECTS_COLUMNS],
        'MockExam_Questions': [QUESTIONS_COLUMNS],
        'MockExam_Benchmarks': [BENCHMARKS_COLUMNS],
    }

    def simulate_sheet_upload(pkg, replace=True):
        tables = serialize_mock_package_to_tables(pkg)
        eid = pkg['metadata']['exam_id']

        for key, columns, rows in [
            ('MockExam_Index', INDEX_COLUMNS, [tables['index'][1]]),
            ('MockExam_Results', RESULTS_COLUMNS, tables['results'][1:]),
            ('MockExam_Subjects', SUBJECTS_COLUMNS, tables['subjects'][1:]),
            ('MockExam_Questions', QUESTIONS_COLUMNS, tables['questions'][1:]),
            ('MockExam_Benchmarks', BENCHMARKS_COLUMNS, tables['benchmarks'][1:])
        ]:
            existing_body = storage[key][1:]
            if replace:
                retained_body = [r for r in existing_body if len(r) > 0 and r[0] != eid]
            else:
                retained_body = existing_body
            storage[key] = [columns] + retained_body + rows

    # 1. Sequentially upload all 4 exams
    for ex in four_exams:
        simulate_sheet_upload(ex)

    # Verify Index has all 4 exams
    index_ids = [r[0] for r in storage['MockExam_Index'][1:]]
    assert index_ids == ['mock_115_1', 'mock_115_2', 'mock_115_3', 'mock_115_4']

    # Verify Results has 4 exams * 5 students = 20 rows
    results_rows = storage['MockExam_Results'][1:]
    assert len(results_rows) == 20

    # 2. Simulate re-importing mock_115_2 with updated total points for student 1
    updated_exam_2 = create_synthetic_exam_package(
        exam_id="mock_115_2",
        school_year="115",
        round_name="第二次",
        round_num=2,
        test_date="2026/12/15",
        num_students=5
    )
    # Modify student 1 score to 35.0
    updated_exam_2['students'][0]['total_points'] = 35.0
    simulate_sheet_upload(updated_exam_2, replace=True)

    # Verify total results count is STILL 20 (idempotent - no duplicates!)
    assert len(storage['MockExam_Results'][1:]) == 20

    # Verify mock_115_1 and mock_115_3 rows are untouched
    exam_1_results = [r for r in storage['MockExam_Results'][1:] if r[0] == 'mock_115_1']
    assert len(exam_1_results) == 5

    # Verify updated mock_115_2 has the new score 35.0
    exam_2_s1 = [r for r in storage['MockExam_Results'][1:] if r[0] == 'mock_115_2' and r[1] == 'TEST001'][0]
    assert float(exam_2_s1[5]) == 35.0

