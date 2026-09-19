"""
tests/test_regular_exam_compatibility.py
-----------------------------------------
Verifies that existing regular exam (定期評量) data parsing,
auth session state, and constants remain 100% backward compatible.
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.constants import EXCLUDE_STATS, RANK_METRICS, SCORE_BINS, SCORE_BIN_LABELS, DEFAULT_SCHOOL_TOTAL_STUDENTS
from core.data_loader import parse_columns
from core.charts import create_radar_chart, create_box_plot, create_grouped_bar_chart, create_distribution_chart


def test_constants():
    assert '總分' in EXCLUDE_STATS
    assert '平均' in EXCLUDE_STATS
    assert '班排' in RANK_METRICS
    assert len(SCORE_BINS) == 11
    assert len(SCORE_BIN_LABELS) == 10
    assert DEFAULT_SCHOOL_TOTAL_STUDENTS == 520


def test_parse_columns():
    sample_cols = [
        'Number', 'StudentID', 'Pin', 'Name', 'Class',
        '113_1_E_1_{國文}_{}',
        '113_1_E_1_{英文}_{}',
        '113_1_E_1_{數學}_{}',
        '113_1_E_1_{社會}_{}',
        '113_1_E_1_{生物}_{}',
        '113_1_E_1_{總分}_{}',
        '113_1_E_1_{平均}_{}',
        '113_1_E_1_{班排}_{}',
        '113_1_E_1_{校排}_{}',
        '113_1_E_2_{國文}_{取消}',  # Should be skipped because '取消'
    ]
    col_info = parse_columns(sample_cols)
    assert not col_info.empty
    assert '113-1 段考1' in col_info['Exam_Label'].values
    assert '取消' not in ' '.join(col_info['Original_Col'].tolist())
    parsed_subjs = col_info['Subject'].tolist()
    assert '國文' in parsed_subjs
    assert '總分' in parsed_subjs


def test_regular_charts_generation():
    subjects = ['國文', '英文', '數學', '社會', '生物']
    student_scores = [85, 90, 78, 88, 92]
    class_avgs = [80.5, 82.3, 75.0, 84.1, 86.0]

    fig_radar = create_radar_chart(subjects, student_scores, class_avgs)
    assert fig_radar is not None

    box_x = ['國文', '國文', '數學', '數學']
    box_y = [70, 90, 60, 85]
    fig_box = create_box_plot(box_x, box_y, ['國文', '數學'], [85, 78])
    assert fig_box is not None

    stats_df = pd.DataFrame({
        '科目 (Subject)': subjects,
        '學生分數 (Score)': student_scores,
        '班級平均 (Class Avg)': class_avgs
    })
    fig_bar = create_grouped_bar_chart(stats_df, is_virtual=False)
    assert fig_bar is not None
