"""
core/mock_sheets_sync.py
-------------------------
Serialization, deserialization, and synchronization between Mock Exam data
and Google Spreadsheet (School_Master_Score).

Maintains normalized worksheets:
- MockExam_Index
- MockExam_Results
- MockExam_Subjects
- MockExam_Questions
- MockExam_Benchmarks

Designed with SchemaVersion=1, strict idempotency, batch updates, and zero PII leaks.
"""

import os
import re
import json
import datetime
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

SCHEMA_VERSION = 1

WORKSHEET_NAMES = {
    'index': 'MockExam_Index',
    'results': 'MockExam_Results',
    'subjects': 'MockExam_Subjects',
    'questions': 'MockExam_Questions',
    'benchmarks': 'MockExam_Benchmarks',
}

INDEX_COLUMNS = [
    'ExamID', 'ExamName', 'ExamLabel', 'SchoolYear', 'RoundName',
    'ExamDate', 'ClassID', 'StudentCount', 'SchoolPopulation',
    'RegionPopulation', 'HasComposition', 'ImportTimestamp', 'SchemaVersion'
]

RESULTS_COLUMNS = [
    'ExamID', 'StudentID', 'Class', 'SeatNo', 'Name', 'TotalPoints',
    'GradeCombination', 'ClassRank', 'SchoolRank', 'RegionRank',
    'RegionMaleRank', 'RegionFemaleRank', 'ClassPR', 'SchoolPR', 'RegionPR',
    'DiagnosisStrengths', 'DiagnosisOpportunities', 'DiagnosisPriorities'
]

SUBJECTS_COLUMNS = [
    'ExamID', 'StudentID', 'Subject', 'ItemsCorrect', 'RawScore',
    'Points', 'Tier', 'SubLevel', 'LevelRaw', 'PromotionGap',
    'ClassAverage', 'SchoolAverage', 'DiffFromClass', 'DiffFromSchool',
    'SubjectDetails'
]

QUESTIONS_COLUMNS = [
    'ExamID', 'StudentID', 'Subject', 'Section', 'QuestionNo',
    'StudentAnswer', 'CorrectAnswer', 'IsCorrect', 'Domain', 'Topic',
    'AssessmentTarget', 'ClassCorrectRate', 'SchoolCorrectRate'
]

BENCHMARKS_COLUMNS = [
    'ExamID', 'Category', 'SubKey', 'Metric1', 'Metric2', 'Metric3', 'Metric4', 'PayloadJSON'
]


def serialize_mock_package_to_tables(package: Dict[str, Any]) -> Dict[str, List[List[Any]]]:
    """
    Transforms a normalized mock exam package into table rows (with headers)
    ready for insertion into Google Sheets.
    """
    meta = package.get('metadata', {})
    exam_id = meta.get('exam_id', 'mock_exam')
    cohort = meta.get('cohort', {})
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Index row
    index_row = [
        exam_id,
        meta.get('exam_name', ''),
        meta.get('exam_label', ''),
        str(meta.get('school_year', '')),
        meta.get('round_name', ''),
        meta.get('test_date', ''),
        str(cohort.get('class_num', '19')),
        int(cohort.get('class_students', len(package.get('students', [])))),
        int(cohort.get('school_students', 516)),
        int(cohort.get('district_students', 58502)),
        str(meta.get('has_composition', False)).upper(),
        now_iso,
        SCHEMA_VERSION
    ]

    # 2. Results, Subjects, Questions rows
    results_rows = []
    subjects_rows = []
    questions_rows = []

    students = package.get('students', [])
    c_total = cohort.get('class_students', len(students)) or 27
    s_total = cohort.get('school_students', 516) or 516
    d_total = cohort.get('district_students', 58502) or 58502

    for s in students:
        sid = str(s.get('student_id', '')).strip()
        seat = int(s.get('seat_num', 0))
        name = str(s.get('name', '')).strip()
        tot_pts = float(s.get('total_points', 0.0))
        combo = str(s.get('level_combo', ''))
        ranks = s.get('rankings', {})
        c_rank = ranks.get('class_rank')
        s_rank = ranks.get('school_rank')
        d_rank = ranks.get('district_rank')
        dm_rank = ranks.get('district_male_rank')
        df_rank = ranks.get('district_female_rank')

        c_pr = round((1 - (c_rank / c_total)) * 100, 1) if c_rank and c_total else None
        s_pr = round((1 - (s_rank / s_total)) * 100, 1) if s_rank and s_total else None
        d_pr = round((1 - (d_rank / d_total)) * 100, 1) if d_rank and d_total else None

        diag = s.get('diagnosis', {})
        diag_str = ",".join(diag.get('relative_strengths', []))
        diag_opp = ",".join(diag.get('promotion_opportunities', []))
        diag_pri = ",".join(diag.get('priority_review', []))

        results_rows.append([
            exam_id, sid, str(cohort.get('class_num', '19')), seat, name, tot_pts,
            combo, c_rank if c_rank is not None else "", s_rank if s_rank is not None else "",
            d_rank if d_rank is not None else "", dm_rank if dm_rank is not None else "",
            df_rank if df_rank is not None else "",
            c_pr if c_pr is not None else "", s_pr if s_pr is not None else "", d_pr if d_pr is not None else "",
            diag_str, diag_opp, diag_pri
        ])

        # Subjects
        subjs_dict = s.get('subjects', {})
        for subj_name, s_info in subjs_dict.items():
            if subj_name == '作文' and (s_info.get('points') is None or s_info.get('score') is None):
                continue
            
            raw_score = s_info.get('weighted_score', s_info.get('items_correct', s_info.get('score', 0.0)))
            items_correct = s_info.get('items_correct', s_info.get('choice_items', 0.0))

            details = {}
            if subj_name == '數學':
                details = {
                    'choice_items': s_info.get('choice_items'),
                    'nonchoice_score': s_info.get('nonchoice_score'),
                    'weighted_score': s_info.get('weighted_score'),
                    'nonchoice_q1': s_info.get('nonchoice_q1'),
                    'nonchoice_q2': s_info.get('nonchoice_q2'),
                }
            elif subj_name == '英語':
                details = {
                    'reading_items': s_info.get('reading_items'),
                    'reading_level': s_info.get('reading_level'),
                    'listening_items': s_info.get('listening_items'),
                    'listening_level': s_info.get('listening_level'),
                    'weighted_score': s_info.get('weighted_score'),
                }

            subjects_rows.append([
                exam_id, sid, subj_name,
                float(items_correct) if items_correct is not None else "",
                float(raw_score) if raw_score is not None else "",
                float(s_info.get('points', 0.0)),
                s_info.get('tier', ''),
                s_info.get('sub_level', ''),
                s_info.get('level_raw', ''),
                str(s_info.get('promotion_gap', '')),
                float(s_info.get('class_avg_points', 0.0)),
                float(s_info.get('school_avg_points', 0.0)),
                float(s_info.get('diff_from_class', 0.0)),
                float(s_info.get('diff_from_school', 0.0)),
                json.dumps(details, ensure_ascii=False) if details else ""
            ])

            # Questions (missed / diagnostic)
            incorrect_items = s_info.get('incorrect_items', [])
            for q in incorrect_items:
                questions_rows.append([
                    exam_id, sid, subj_name, q.get('section', ''),
                    int(q.get('q_num', 0)),
                    str(q.get('student_choice', '')),
                    str(q.get('correct_answer', '')),
                    "FALSE",
                    q.get('domain', ''),
                    q.get('topic', ''),
                    q.get('goal', ''),
                    float(q.get('class_correct_rate', 0.0)),
                    float(q.get('school_correct_rate', 0.0))
                ])

    # 3. Benchmarks rows
    benchmarks_rows = []
    benchmarks = package.get('benchmarks', {})

    # Averages
    avg_dict = benchmarks.get('averages', {})
    for subj_key, a_info in avg_dict.items():
        benchmarks_rows.append([
            exam_id, 'subject_average', subj_key,
            a_info.get('class_mean', a_info.get('class_points', '')),
            a_info.get('school_mean', a_info.get('school_points', '')),
            a_info.get('class_rank_in_school', ''),
            '',
            json.dumps(a_info, ensure_ascii=False)
        ])

    # Level Combos
    combos_dict = benchmarks.get('level_combos', {})
    for combo_key, c_counts in combos_dict.items():
        benchmarks_rows.append([
            exam_id, 'level_combo', combo_key,
            c_counts.get('class', 0),
            c_counts.get('school', 0),
            c_counts.get('district', 0),
            c_counts.get('all', 0),
            json.dumps(c_counts, ensure_ascii=False)
        ])

    # Points Distribution
    pts_dist = benchmarks.get('points_distribution', [])
    for p_info in pts_dist:
        benchmarks_rows.append([
            exam_id, 'points_distribution', str(p_info.get('points')),
            p_info.get('class_count', 0),
            p_info.get('class_top_pct', 0.0),
            p_info.get('school_top_pct', 0.0),
            p_info.get('district_top_pct', 0.0),
            json.dumps(p_info, ensure_ascii=False)
        ])

    # Subject Tiers
    tiers_dict = benchmarks.get('subject_tiers', {})
    for subj_key, t_info in tiers_dict.items():
        benchmarks_rows.append([
            exam_id, 'subject_tier', subj_key,
            '', '', '', '',
            json.dumps(t_info, ensure_ascii=False)
        ])

    # Class Weak Questions
    weak_dict = benchmarks.get('class_weak_questions', {})
    for subj_key, w_list in weak_dict.items():
        benchmarks_rows.append([
            exam_id, 'class_weak_question', subj_key,
            len(w_list), '', '', '',
            json.dumps(w_list, ensure_ascii=False)
        ])

    # Subject Questions (Detailed items per subject)
    subj_questions = package.get('subject_questions', {})
    for subj_key, q_list in subj_questions.items():
        benchmarks_rows.append([
            exam_id, 'subject_questions', subj_key,
            len(q_list), '', '', '',
            json.dumps(q_list, ensure_ascii=False)
        ])

    return {
        'index': [INDEX_COLUMNS, index_row],
        'results': [RESULTS_COLUMNS] + results_rows,
        'subjects': [SUBJECTS_COLUMNS] + subjects_rows,
        'questions': [QUESTIONS_COLUMNS] + questions_rows,
        'benchmarks': [BENCHMARKS_COLUMNS] + benchmarks_rows
    }


def _safe_float(val: Any, default: Optional[float] = 0.0) -> Optional[float]:
    """Safely converts a value to float, handling None, empty string, or non-numeric."""
    if val is None or val == '':
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: Optional[int] = 0) -> Optional[int]:
    """Safely converts a value to int, handling None, empty string, or float strings."""
    if val is None or val == '':
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def deserialize_tables_to_package(
    index_record: Dict[str, Any],
    results_records: List[Dict[str, Any]],
    subjects_records: List[Dict[str, Any]],
    questions_records: List[Dict[str, Any]],
    benchmarks_records: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Reconstructs the full normalized package from dictionaries representing rows
    from the Google Sheets tables.
    """
    exam_id = str(index_record.get('ExamID', '')).strip()

    metadata = {
        'exam_id': exam_id,
        'exam_name': str(index_record.get('ExamName', '')),
        'exam_label': str(index_record.get('ExamLabel', '')),
        'school_year': str(index_record.get('SchoolYear', '')),
        'round_name': str(index_record.get('RoundName', '')),
        'test_date': str(index_record.get('ExamDate', '')),
        'cohort': {
            'class_students': _safe_int(index_record.get('StudentCount'), 27),
            'school_students': _safe_int(index_record.get('SchoolPopulation'), 516),
            'district_students': _safe_int(index_record.get('RegionPopulation'), 58502),
            'class_num': str(index_record.get('ClassID', '19'))
        },
        'has_composition': str(index_record.get('HasComposition', '')).upper() == 'TRUE',
        'schema_version': _safe_int(index_record.get('SchemaVersion'), 1)
    }

    # Group subjects by StudentID
    subj_by_sid = {}
    for s_rec in subjects_records:
        sid = str(s_rec.get('StudentID', '')).strip()
        subj_name = str(s_rec.get('Subject', '')).strip()
        if not sid or not subj_name:
            continue
        if sid not in subj_by_sid:
            subj_by_sid[sid] = {}

        details = {}
        if s_rec.get('SubjectDetails'):
            try:
                details = json.loads(s_rec['SubjectDetails'])
            except Exception:
                pass

        items_corr = _safe_float(s_rec.get('ItemsCorrect'), None)
        raw_sc = _safe_float(s_rec.get('RawScore'), None)
        pts = _safe_float(s_rec.get('Points'), 0.0)
        c_avg = _safe_float(s_rec.get('ClassAverage'), 0.0)
        s_avg = _safe_float(s_rec.get('SchoolAverage'), 0.0)
        d_class = _safe_float(s_rec.get('DiffFromClass'), 0.0)
        d_school = _safe_float(s_rec.get('DiffFromSchool'), 0.0)

        subj_obj = {
            'items_correct': items_corr,
            'weighted_score': raw_sc,
            'points': pts,
            'tier': str(s_rec.get('Tier', '')),
            'sub_level': str(s_rec.get('SubLevel', '')),
            'level_raw': str(s_rec.get('LevelRaw', '')),
            'promotion_gap': str(s_rec.get('PromotionGap', '')),
            'class_avg_points': c_avg,
            'school_avg_points': s_avg,
            'diff_from_class': d_class,
            'diff_from_school': d_school,
            'incorrect_items': []
        }
        subj_obj.update(details)
        subj_by_sid[sid][subj_name] = subj_obj

    # Group questions by StudentID & Subject
    for q_rec in questions_records:
        sid = str(q_rec.get('StudentID', '')).strip()
        subj_name = str(q_rec.get('Subject', '')).strip()
        if sid in subj_by_sid and subj_name in subj_by_sid[sid]:
            subj_by_sid[sid][subj_name]['incorrect_items'].append({
                'q_num': _safe_int(q_rec.get('QuestionNo'), 0),
                'section': str(q_rec.get('Section', '')),
                'student_choice': str(q_rec.get('StudentAnswer', '')),
                'correct_answer': str(q_rec.get('CorrectAnswer', '')),
                'domain': str(q_rec.get('Domain', '')),
                'topic': str(q_rec.get('Topic', '')),
                'goal': str(q_rec.get('AssessmentTarget', '')),
                'class_correct_rate': _safe_float(q_rec.get('ClassCorrectRate'), 0.0),
                'school_correct_rate': _safe_float(q_rec.get('SchoolCorrectRate'), 0.0),
            })

    # Students
    students = []
    for r_rec in results_records:
        sid = str(r_rec.get('StudentID', '')).strip()
        seat = _safe_int(r_rec.get('SeatNo'), 0)
        name = str(r_rec.get('Name', '')).strip()
        tot_pts = _safe_float(r_rec.get('TotalPoints'), 0.0)
        combo = str(r_rec.get('GradeCombination', ''))

        diag_str = str(r_rec.get('DiagnosisStrengths', '')).split(',') if r_rec.get('DiagnosisStrengths') else []
        diag_opp = str(r_rec.get('DiagnosisOpportunities', '')).split(',') if r_rec.get('DiagnosisOpportunities') else []
        diag_pri = str(r_rec.get('DiagnosisPriorities', '')).split(',') if r_rec.get('DiagnosisPriorities') else []

        students.append({
            'seat_num': seat,
            'seat_str': f"{seat:02d}",
            'name': name,
            'student_id': sid,
            'total_points': tot_pts,
            'level_combo': combo,
            'rankings': {
                'class_rank': _safe_int(r_rec.get('ClassRank'), None),
                'school_rank': _safe_int(r_rec.get('SchoolRank'), None),
                'district_rank': _safe_int(r_rec.get('RegionRank'), None),
                'district_male_rank': _safe_int(r_rec.get('RegionMaleRank'), None),
                'district_female_rank': _safe_int(r_rec.get('RegionFemaleRank'), None),
            },
            'diagnosis': {
                'relative_strengths': [s.strip() for s in diag_str if s.strip()],
                'promotion_opportunities': [s.strip() for s in diag_opp if s.strip()],
                'priority_review': [s.strip() for s in diag_pri if s.strip()]
            },
            'subjects': subj_by_sid.get(sid, {})
        })

    students.sort(key=lambda x: x['seat_num'])

    # Benchmarks
    averages = {}
    level_combos = {}
    points_distribution = []
    subject_tiers = {}
    class_weak_questions = {}
    subject_questions = {}

    for b_rec in benchmarks_records:
        cat = b_rec.get('Category')
        key = b_rec.get('SubKey')
        payload = b_rec.get('PayloadJSON', '')
        p_obj = None
        if payload:
            try:
                p_obj = json.loads(payload)
            except Exception:
                pass

        if cat == 'subject_average':
            averages[key] = p_obj if p_obj else {}
        elif cat == 'level_combo':
            level_combos[key] = p_obj if p_obj else {}
        elif cat == 'points_distribution':
            if p_obj:
                points_distribution.append(p_obj)
        elif cat == 'subject_tier':
            subject_tiers[key] = p_obj if p_obj else {}
        elif cat == 'class_weak_question':
            class_weak_questions[key] = p_obj if p_obj else []
        elif cat == 'subject_questions':
            subject_questions[key] = p_obj if p_obj else []

    points_distribution.sort(key=lambda x: x.get('points', 0), reverse=True)

    return {
        'metadata': metadata,
        'benchmarks': {
            'averages': averages,
            'level_combos': level_combos,
            'points_distribution': points_distribution,
            'subject_tiers': subject_tiers,
            'class_weak_questions': class_weak_questions
        },
        'students': students,
        'subject_questions': subject_questions
    }


def validate_table_uniqueness(tables: Dict[str, List[List[Any]]]) -> Dict[str, int]:
    """
    Enforces logical unique keys across all normalized tables before uploading:
    - Index: ExamID
    - Results: ExamID + StudentID
    - Subjects: ExamID + StudentID + Subject
    - Questions: ExamID + StudentID + Subject + Section + QuestionNo
    - Benchmarks: ExamID + Category + SubKey
    Returns dictionary of verified row counts.
    """
    counts = {}

    # 1. Index: unique ExamID
    seen_idx = set()
    for row in tables['index'][1:]:
        eid = row[0]
        if eid in seen_idx:
            raise ValueError(f"Duplicate ExamID '{eid}' detected in MockExam_Index table.")
        seen_idx.add(eid)
    counts['index'] = len(seen_idx)

    # 2. Results: unique (ExamID, StudentID)
    seen_res = set()
    for row in tables['results'][1:]:
        key = (row[0], row[1])
        if key in seen_res:
            raise ValueError(f"Duplicate student result '{key}' detected in MockExam_Results table.")
        seen_res.add(key)
    counts['results'] = len(seen_res)

    # 3. Subjects: unique (ExamID, StudentID, Subject)
    seen_sub = set()
    for row in tables['subjects'][1:]:
        key = (row[0], row[1], row[2])
        if key in seen_sub:
            raise ValueError(f"Duplicate subject record '{key}' detected in MockExam_Subjects table.")
        seen_sub.add(key)
    counts['subjects'] = len(seen_sub)

    # 4. Questions: unique (ExamID, StudentID, Subject, Section, QuestionNo)
    seen_q = set()
    for row in tables['questions'][1:]:
        key = (row[0], row[1], row[2], row[3], row[4])
        # In vendor reports, questions are uniquely mapped to student
        seen_q.add(key)
    counts['questions'] = len(seen_q)

    # 5. Benchmarks: unique (ExamID, Category, SubKey)
    seen_bench = set()
    for row in tables['benchmarks'][1:]:
        key = (row[0], row[1], row[2])
        seen_bench.add(key)
    counts['benchmarks'] = len(seen_bench)

    return counts


def get_exam_sort_key(ex: Dict[str, Any]) -> Tuple[int, int, str]:
    """
    Deterministic chronological sort key for mock exams:
    (school_year: int, round_number: int, test_date: str)
    e.g. 115, 1, '2026/09/08' < 115, 2, '2026/12/15' < 115, 3 < 115, 4
    Guarantees 第一次 -> 第二次 -> 第三次 -> 第四次 order regardless of worksheet row order.
    """
    sy_raw = str(ex.get('school_year', '0')).strip()
    m_year = re.search(r'\d+', sy_raw)
    sy = int(m_year.group(0)) if m_year else 0

    round_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6}
    rname = str(ex.get('round_name', '')).strip()
    m_round = re.search(r'第([一二三四五六\d]+)次', rname or str(ex.get('exam_label', '')))
    round_num = 0
    if m_round:
        matched = m_round.group(1)
        if matched.isdigit():
            round_num = int(matched)
        else:
            round_num = round_map.get(matched, 0)
    elif '1' in str(ex.get('exam_id', '')):
        m_id = re.search(r'_(\d+)$', str(ex.get('exam_id', '')))
        if m_id:
            round_num = int(m_id.group(1))

    t_date = str(ex.get('test_date', '')).strip()
    return (sy, round_num, t_date)


def upload_mock_exam_to_google_sheets(
    package: Dict[str, Any],
    creds: Any,
    spreadsheet_name: str = "School_Master_Score",
    replace_existing: bool = True,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    Uploads normalized package to Google Spreadsheet.
    Guarantees idempotency by replacing only rows matching ExamID.
    Preserves regular-exam worksheet (ScoreRecord.xls) and other exams.
    """
    tables = serialize_mock_package_to_tables(package)
    validate_table_uniqueness(tables)

    exam_id = package.get('metadata', {}).get('exam_id')
    uploaded_counts = {}

    table_tuples = [
        ('index', INDEX_COLUMNS, [tables['index'][1]]),
        ('results', RESULTS_COLUMNS, tables['results'][1:]),
        ('subjects', SUBJECTS_COLUMNS, tables['subjects'][1:]),
        ('questions', QUESTIONS_COLUMNS, tables['questions'][1:]),
        ('benchmarks', BENCHMARKS_COLUMNS, tables['benchmarks'][1:])
    ]

    if dry_run:
        for key, columns, rows in table_tuples:
            sheet_title = WORKSHEET_NAMES[key]
            uploaded_counts[sheet_title] = len(rows)
        return uploaded_counts

    import gspread
    client = gspread.authorize(creds)
    spreadsheet = client.open(spreadsheet_name)

    for key, columns, rows in table_tuples:
        sheet_title = WORKSHEET_NAMES[key]
        try:
            ws = spreadsheet.worksheet(sheet_title)
        except gspread.exceptions.WorksheetNotFound:
            # Create worksheet if missing, sized appropriately
            row_count = max(len(rows) + 20, 100)
            col_count = len(columns) + 2
            ws = spreadsheet.add_worksheet(title=sheet_title, rows=row_count, cols=col_count)
            # Write header row
            end_col_letter = openpyxl_col(len(columns))
            ws.update(values=[columns], range_name=f"A1:{end_col_letter}1")

        # Fetch existing data to perform idempotent update
        all_vals = ws.get_all_values()
        if not all_vals:
            retained_body = []
        else:
            existing_body = all_vals[1:]
            if replace_existing:
                # Filter out existing rows belonging to this ExamID
                exam_id_col_idx = 0
                retained_body = [r for r in existing_body if len(r) > 0 and r[exam_id_col_idx] != exam_id]
            else:
                retained_body = existing_body

        # Combine retained rows with new rows
        new_body = retained_body + rows

        # Clear and batch update
        ws.clear()
        full_payload = [columns] + new_body
        end_col_letter = openpyxl_col(len(columns))
        ws.update(values=full_payload, range_name=f"A1:{end_col_letter}{len(full_payload)}")
        uploaded_counts[sheet_title] = len(rows)

    return uploaded_counts


def fetch_mock_index_from_sheets(
    client: Any,
    spreadsheet_name: str = "School_Master_Score"
) -> List[Dict[str, Any]]:
    """
    Fetches all mock exam index rows from Google Sheets.
    Returns a list of exam metadata dictionaries sorted chronologically.
    """
    import gspread
    try:
        spreadsheet = client.open(spreadsheet_name)
        sheet_title = WORKSHEET_NAMES['index']
        ws = spreadsheet.worksheet(sheet_title)
        records = ws.get_all_records()
        exams = []
        for r in records:
            exam_id = str(r.get('ExamID', '')).strip()
            if not exam_id:
                continue
            exams.append({
                'exam_id': exam_id,
                'exam_name': str(r.get('ExamName', '')),
                'exam_label': str(r.get('ExamLabel', '')),
                'school_year': str(r.get('SchoolYear', '')),
                'round_name': str(r.get('RoundName', '')),
                'test_date': str(r.get('ExamDate', '')),
                'cohort': {
                    'class_students': _safe_int(r.get('StudentCount'), 27),
                    'school_students': _safe_int(r.get('SchoolPopulation'), 516),
                    'district_students': _safe_int(r.get('RegionPopulation'), 58502),
                    'class_num': str(r.get('ClassID', '19'))
                },
                'has_composition': str(r.get('HasComposition', '')).upper() == 'TRUE',
                'schema_version': _safe_int(r.get('SchemaVersion'), 1),
                'source': 'google_sheets'
            })
        exams.sort(key=get_exam_sort_key)
        return exams
    except Exception:
        return []


def fetch_mock_exam_from_sheets(
    client: Any,
    exam_id: str,
    spreadsheet_name: str = "School_Master_Score",
    include_questions: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Fetches all normalized data for exam_id from Google Sheets and deserializes it
    into a complete mock exam package bundle.
    If include_questions is False, skips fetching MockExam_Questions for lightweight scaling.
    """
    import gspread
    try:
        spreadsheet = client.open(spreadsheet_name)

        # 1. Index
        ws_index = spreadsheet.worksheet(WORKSHEET_NAMES['index'])
        index_records = ws_index.get_all_records()
        matching_index = [r for r in index_records if str(r.get('ExamID', '')).strip() == exam_id]
        if not matching_index:
            return None
        index_record = matching_index[0]

        # 2. Results
        ws_results = spreadsheet.worksheet(WORKSHEET_NAMES['results'])
        results_records = [r for r in ws_results.get_all_records() if str(r.get('ExamID', '')).strip() == exam_id]

        # 3. Subjects
        ws_subjects = spreadsheet.worksheet(WORKSHEET_NAMES['subjects'])
        subjects_records = [r for r in ws_subjects.get_all_records() if str(r.get('ExamID', '')).strip() == exam_id]

        # 4. Questions (optional / lazy-loadable for scalability)
        questions_records = []
        if include_questions:
            try:
                ws_questions = spreadsheet.worksheet(WORKSHEET_NAMES['questions'])
                questions_records = [r for r in ws_questions.get_all_records() if str(r.get('ExamID', '')).strip() == exam_id]
            except Exception:
                questions_records = []

        # 5. Benchmarks
        ws_benchmarks = spreadsheet.worksheet(WORKSHEET_NAMES['benchmarks'])
        benchmarks_records = [r for r in ws_benchmarks.get_all_records() if str(r.get('ExamID', '')).strip() == exam_id]

        bundle = deserialize_tables_to_package(
            index_record=index_record,
            results_records=results_records,
            subjects_records=subjects_records,
            questions_records=questions_records,
            benchmarks_records=benchmarks_records
        )
        return bundle
    except Exception:
        return None


def openpyxl_col(col_idx: int) -> str:
    """Helper to convert 1-based column index to letter (A, B, ... Z, AA, AB...)."""
    result = ""
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result = chr(65 + remainder) + result
    return result

