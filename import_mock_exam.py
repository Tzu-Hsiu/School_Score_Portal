#!/usr/bin/env python3
"""
import_mock_exam.py
--------------------
CLI utility and pipeline to import, validate, normalize, and verify
junior high school Mock Exam (國中教育會考模擬考) datasets.

Supported Vendor Reports:
- RN201 / RN202: 班級能力等級成績總表 (座號序 / 排名序)
- RN204: 班級學生各科知識點作答分析表 (題目層級作答、晉級差距、知識點)
- RN205: 班級成績統計總表 (班級/校/區常模、五科能力等級、總積分累積PR)
- RN207: 班級各科試題選項分析表 (各題選答率、正確答案、鑑別度)
- RN208: 班級學生數學非選成績統計表 (數學非選細部得分)

Usage:
    python import_mock_exam.py --data-dir <path_to_vendor_dir> [--output <path_to_json>]
"""

import os
import sys
import re
import json
import argparse
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.mock_sheets_sync import upload_mock_exam_to_google_sheets

try:
    import xlrd
except ImportError:
    xlrd = None

try:
    import openpyxl
except ImportError:
    openpyxl = None


def extract_level_details(level_str: str) -> Tuple[str, str]:
    """
    Parse '精熟(A++)' into ('精熟', 'A++').
    Returns (tier, sub_level).
    """
    if not level_str or not isinstance(level_str, str):
        return "", ""
    level_str = level_str.strip()
    match = re.match(r"(精熟|基礎|待加強)\(([A-C]\+*)\)", level_str)
    if match:
        return match.group(1), match.group(2)
    if level_str in ['A++', 'A+', 'A']:
        return '精熟', level_str
    if level_str in ['B++', 'B+', 'B']:
        return '基礎', level_str
    if level_str == 'C':
        return '待加強', level_str
    return level_str, level_str


def find_vendor_files(data_dir: str) -> Dict[str, str]:
    """Locates relevant vendor report files in data_dir."""
    files = os.listdir(data_dir)
    found = {}
    patterns = {
        'rn201': r'RN201.*\.xls$',
        'rn202': r'RN202.*\.xlsx?$',
        'rn204': r'RN204.*\.xlsx?$',
        'rn205': r'RN205.*\.xls$',
        'rn207': r'RN207.*\.xlsx?$',
        'rn208': r'RN208.*\.xls$',
    }
    for key, pat in patterns.items():
        for fname in sorted(files):
            if re.search(pat, fname, re.IGNORECASE):
                found[key] = os.path.join(data_dir, fname)
                break
    return found


def parse_rn205_metadata_and_benchmarks(file_path: str) -> Dict[str, Any]:
    """
    Parses RN205 to extract metadata (exam name, school info, cohort sizes)
    and official benchmarks (averages, combo distributions, score distributions).
    """
    if not xlrd:
        raise ImportError("xlrd package is required to read .xls files. Install via pip install xlrd.")

    wb = xlrd.open_workbook(file_path)
    sheet = wb.sheet_by_index(0)

    title = str(sheet.cell_value(0, 0)).strip()
    exam_name = str(sheet.cell_value(1, 0)).strip() if sheet.nrows > 1 else ""
    meta_line = str(sheet.cell_value(2, 0)).strip() if sheet.nrows > 2 else ""

    test_date = ""
    for c in range(sheet.ncols):
        val = str(sheet.cell_value(2, c)).strip()
        m_date = re.search(r"(\d{4}/\d{2}/\d{2})", val)
        if m_date:
            test_date = m_date.group(1)
            break

    cohort = {
        'class_students': 0,
        'school_students': 0,
        'district_students': 0,
        'district_male': 0,
        'district_female': 0,
        'total_cohort': 0,
        'school_code': '014558',
        'school_name': '新北市立義學國中',
        'grade': '09',
        'class_num': '19'
    }

    m_cls = re.search(r"全班：(\d+)", meta_line)
    if m_cls: cohort['class_students'] = int(m_cls.group(1))
    m_sch = re.search(r"全校：(\d+)", meta_line)
    if m_sch: cohort['school_students'] = int(m_sch.group(1))
    m_dst = re.search(r"全區：([\d,]+)", meta_line)
    if m_dst: cohort['district_students'] = int(m_dst.group(1).replace(',', ''))
    m_mal = re.search(r"區男：([\d,]+)", meta_line)
    if m_mal: cohort['district_male'] = int(m_mal.group(1).replace(',', ''))
    m_fem = re.search(r"區女：([\d,]+)", meta_line)
    if m_fem: cohort['district_female'] = int(m_fem.group(1).replace(',', ''))
    m_tot = re.search(r"總人數：([\d,]+)", meta_line)
    if m_tot: cohort['total_cohort'] = int(m_tot.group(1).replace(',', ''))
    m_cnum = re.search(r"班級：(\d+)", meta_line)
    if m_cnum: cohort['class_num'] = m_cnum.group(1)
    m_sname = re.search(r"（(\d+)）([^《\s]+)", meta_line)
    if m_sname:
        cohort['school_code'] = m_sname.group(1)
        cohort['school_name'] = m_sname.group(2)

    averages = {}
    try:
        averages['五科總積分'] = {
            'class_mean': float(sheet.cell_value(6, 6)) if sheet.cell_value(6, 6) != "" else None,
            'school_mean': float(sheet.cell_value(7, 6)) if sheet.cell_value(7, 6) != "" else None,
            'class_rank_in_school': int(float(sheet.cell_value(6, 8))) if sheet.cell_value(6, 8) != "" else None
        }
        averages['國文'] = {
            'class_items': float(sheet.cell_value(6, 12)) if sheet.cell_value(6, 12) != "" else None,
            'school_items': float(sheet.cell_value(7, 12)) if sheet.cell_value(7, 12) != "" else None,
            'class_points': float(sheet.cell_value(6, 14)) if sheet.cell_value(6, 14) != "" else None,
            'school_points': float(sheet.cell_value(7, 14)) if sheet.cell_value(7, 14) != "" else None,
            'class_rank_in_school': int(float(sheet.cell_value(6, 16))) if sheet.cell_value(6, 16) != "" else None
        }
        averages['數學'] = {
            'class_choice_items': float(sheet.cell_value(6, 20)) if sheet.cell_value(6, 20) != "" else None,
            'school_choice_items': float(sheet.cell_value(7, 20)) if sheet.cell_value(7, 20) != "" else None,
            'class_nonchoice_score': float(sheet.cell_value(6, 22)) if sheet.cell_value(6, 22) != "" else None,
            'school_nonchoice_score': float(sheet.cell_value(7, 22)) if sheet.cell_value(7, 22) != "" else None,
            'class_points': float(sheet.cell_value(6, 24)) if sheet.cell_value(6, 24) != "" else None,
            'school_points': float(sheet.cell_value(7, 24)) if sheet.cell_value(7, 24) != "" else None,
            'class_rank_in_school': int(float(sheet.cell_value(6, 26))) if sheet.cell_value(6, 26) != "" else None
        }
        averages['英語'] = {
            'class_reading_items': float(sheet.cell_value(6, 30)) if sheet.cell_value(6, 30) != "" else None,
            'school_reading_items': float(sheet.cell_value(7, 30)) if sheet.cell_value(7, 30) != "" else None,
            'class_listening_items': float(sheet.cell_value(6, 32)) if sheet.cell_value(6, 32) != "" else None,
            'school_listening_items': float(sheet.cell_value(7, 32)) if sheet.cell_value(7, 32) != "" else None,
            'class_points': float(sheet.cell_value(6, 34)) if sheet.cell_value(6, 34) != "" else None,
            'school_points': float(sheet.cell_value(7, 34)) if sheet.cell_value(7, 34) != "" else None,
            'class_rank_in_school': int(float(sheet.cell_value(6, 36))) if sheet.cell_value(6, 36) != "" else None
        }
        averages['社會'] = {
            'class_items': float(sheet.cell_value(6, 40)) if sheet.cell_value(6, 40) != "" else None,
            'school_items': float(sheet.cell_value(7, 40)) if sheet.cell_value(7, 40) != "" else None,
            'class_points': float(sheet.cell_value(6, 42)) if sheet.cell_value(6, 42) != "" else None,
            'school_points': float(sheet.cell_value(7, 42)) if sheet.cell_value(7, 42) != "" else None,
            'class_rank_in_school': int(float(sheet.cell_value(6, 44))) if sheet.cell_value(6, 44) != "" else None
        }
        averages['自然'] = {
            'class_items': float(sheet.cell_value(6, 48)) if sheet.cell_value(6, 48) != "" else None,
            'school_items': float(sheet.cell_value(7, 48)) if sheet.cell_value(7, 48) != "" else None,
            'class_points': float(sheet.cell_value(6, 50)) if sheet.cell_value(6, 50) != "" else None,
            'school_points': float(sheet.cell_value(7, 50)) if sheet.cell_value(7, 50) != "" else None,
            'class_rank_in_school': int(float(sheet.cell_value(6, 52))) if sheet.cell_value(6, 52) != "" else None
        }
    except Exception as e:
        print(f"Warning parsing RN205 averages: {e}")

    level_combos = {}
    try:
        # Row 10: combo names at c=4, 8, 12, 16...
        for c in range(4, sheet.ncols, 4):
            cname = str(sheet.cell_value(10, c)).strip()
            if not cname:
                continue
            c_cnt = sheet.cell_value(12, c)
            s_cnt = sheet.cell_value(13, c)
            d_cnt = sheet.cell_value(14, c)
            a_cnt = sheet.cell_value(15, c)
            level_combos[cname] = {
                'class': int(float(c_cnt)) if c_cnt != "" else 0,
                'school': int(float(s_cnt)) if s_cnt != "" else 0,
                'district': int(float(d_cnt)) if d_cnt != "" else 0,
                'all': int(float(a_cnt)) if a_cnt != "" else 0
            }
    except Exception as e:
        print(f"Warning parsing level combos: {e}")

    points_distribution = []
    try:
        for b in [26, 35]:
            for c in range(4, sheet.ncols, 4):
                val = sheet.cell_value(b, c)
                if val == "" or not str(val).replace(".0","").isdigit():
                    continue
                pt = float(val)
                cls_alloc = sheet.cell_value(b + 2, c)
                cls_cum_pct = sheet.cell_value(b + 3, c + 2)
                sch_alloc = sheet.cell_value(b + 4, c)
                sch_cum_pct = sheet.cell_value(b + 5, c + 2)
                dst_alloc = sheet.cell_value(b + 6, c)
                dst_cum_pct = sheet.cell_value(b + 7, c + 2)

                points_distribution.append({
                    'points': pt,
                    'class_count': int(float(cls_alloc)) if cls_alloc != "" else 0,
                    'class_top_pct': float(cls_cum_pct) if cls_cum_pct != "" else 0.0,
                    'school_count': int(float(sch_alloc)) if sch_alloc != "" else 0,
                    'school_top_pct': float(sch_cum_pct) if sch_cum_pct != "" else 0.0,
                    'district_count': int(float(dst_alloc)) if dst_alloc != "" else 0,
                    'district_top_pct': float(dst_cum_pct) if dst_cum_pct != "" else 0.0,
                })
    except Exception as e:
        print(f"Warning parsing points distribution: {e}")

    subject_tiers = {}
    subjects_order = ['國文', '數學', '英語', '社會', '自然']
    try:
        tier_names = ['精熟', '基礎', '待加強']
        for s_idx, subj in enumerate(subjects_order):
            base_col = 2 + s_idx * 6
            c_counts = {}
            s_counts = {}
            d_counts = {}
            for t_idx, tname in enumerate(tier_names):
                col = base_col + t_idx * 2
                if col < sheet.ncols:
                    c_cnt = sheet.cell_value(62, col)
                    s_cnt = sheet.cell_value(63, col)
                    d_cnt = sheet.cell_value(64, col)
                    c_counts[tname] = int(float(c_cnt)) if c_cnt != "" else 0
                    s_counts[tname] = int(float(s_cnt)) if s_cnt != "" else 0
                    d_counts[tname] = int(float(d_cnt)) if d_cnt != "" else 0
            subject_tiers[subj] = {
                'class': c_counts,
                'school': s_counts,
                'district': d_counts
            }
    except Exception as e:
        print(f"Warning parsing subject tiers: {e}")

    return {
        'title': title,
        'exam_name': exam_name,
        'test_date': test_date,
        'cohort': cohort,
        'averages': averages,
        'level_combos': level_combos,
        'points_distribution': points_distribution,
        'subject_tiers': subject_tiers
    }


def parse_rn201_or_rn202_students(file_path: str) -> List[Dict[str, Any]]:
    """Parses RN201 (xls) or RN202 (xlsx) to extract all student records."""
    students = []
    if file_path.endswith('.xlsx'):
        if not openpyxl:
            raise ImportError("openpyxl is required to read .xlsx files.")
        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb[wb.sheetnames[0]]
        rows = list(ws.iter_rows(values_only=True))

        for r_idx, row in enumerate(rows):
            if not row or len(row) < 3:
                continue
            c0 = str(row[0]).strip() if row[0] is not None else ""
            c1 = str(row[1]).strip() if row[1] is not None else ""
            if not (c0.isdigit() and c1.isdigit()):
                continue

            seat = int(c1)
            name = str(row[2]).strip() if row[2] is not None else ""
            tot_pts = float(row[3]) if row[3] is not None and str(row[3]).strip() != "" else 0.0
            combo = str(row[4]).strip() if row[4] is not None else ""

            chi_items = float(row[5]) if row[5] is not None and str(row[5]).strip() != "" else 0
            chi_level = str(row[6]).strip() if row[6] is not None else ""
            chi_pts = float(row[7]) if row[7] is not None and str(row[7]).strip() != "" else 0

            mat_choice = float(row[8]) if row[8] is not None and str(row[8]).strip() != "" else 0
            mat_q1 = float(row[9]) if row[9] is not None and str(row[9]).strip() != "" else 0
            mat_q2 = float(row[10]) if row[10] is not None and str(row[10]).strip() != "" else 0
            mat_nonchoice_score = float(row[11]) if row[11] is not None and str(row[11]).strip() != "" else 0
            mat_weighted = float(row[12]) if row[12] is not None and str(row[12]).strip() != "" else 0
            mat_level = str(row[13]).strip() if row[13] is not None else ""
            mat_pts = float(row[14]) if row[14] is not None and str(row[14]).strip() != "" else 0

            eng_read_items = float(row[15]) if row[15] is not None and str(row[15]).strip() != "" else 0
            eng_read_level = str(row[16]).strip() if row[16] is not None else ""
            eng_listen_items = float(row[17]) if row[17] is not None and str(row[17]).strip() != "" else 0
            eng_listen_level = str(row[18]).strip() if row[18] is not None else ""
            eng_weighted = float(row[19]) if row[19] is not None and str(row[19]).strip() != "" else 0
            eng_level = str(row[20]).strip() if row[20] is not None else ""
            eng_pts = float(row[21]) if row[21] is not None and str(row[21]).strip() != "" else 0

            soc_items = float(row[22]) if row[22] is not None and str(row[22]).strip() != "" else 0
            soc_level = str(row[23]).strip() if row[23] is not None else ""
            soc_pts = float(row[24]) if row[24] is not None and str(row[24]).strip() != "" else 0

            sci_items = float(row[25]) if row[25] is not None and str(row[25]).strip() != "" else 0
            sci_level = str(row[26]).strip() if row[26] is not None else ""
            sci_pts = float(row[27]) if row[27] is not None and str(row[27]).strip() != "" else 0

            comp_score = float(row[28]) if row[28] is not None and str(row[28]).strip() != "" else None
            comp_pts = float(row[29]) if row[29] is not None and str(row[29]).strip() != "" else None

            c_rank = int(float(row[30])) if row[30] is not None and str(row[30]).strip() != "" else None
            s_rank = int(float(row[31])) if row[31] is not None and str(row[31]).strip() != "" else None
            d_rank = int(float(row[32])) if row[32] is not None and str(row[32]).strip() != "" else None
            dm_rank = int(float(row[33])) if len(row) > 33 and row[33] is not None and str(row[33]).strip() != "" else None
            df_rank = int(float(row[34])) if len(row) > 34 and row[34] is not None and str(row[34]).strip() != "" else None

            students.append({
                'seat_num': seat,
                'seat_str': f"{seat:02d}",
                'name': name,
                'total_points': tot_pts,
                'level_combo': combo,
                'rankings': {
                    'class_rank': c_rank,
                    'school_rank': s_rank,
                    'district_rank': d_rank,
                    'district_male_rank': dm_rank,
                    'district_female_rank': df_rank
                },
                'subjects': {
                    '國文': {
                        'items_correct': chi_items,
                        'level_raw': chi_level,
                        'tier': extract_level_details(chi_level)[0],
                        'sub_level': extract_level_details(chi_level)[1],
                        'points': chi_pts
                    },
                    '數學': {
                        'choice_items': mat_choice,
                        'nonchoice_q1': mat_q1,
                        'nonchoice_q2': mat_q2,
                        'nonchoice_score': mat_nonchoice_score,
                        'weighted_score': mat_weighted,
                        'level_raw': mat_level,
                        'tier': extract_level_details(mat_level)[0],
                        'sub_level': extract_level_details(mat_level)[1],
                        'points': mat_pts
                    },
                    '英語': {
                        'reading_items': eng_read_items,
                        'reading_level': eng_read_level,
                        'listening_items': eng_listen_items,
                        'listening_level': eng_listen_level,
                        'weighted_score': eng_weighted,
                        'level_raw': eng_level,
                        'tier': extract_level_details(eng_level)[0],
                        'sub_level': extract_level_details(eng_level)[1],
                        'points': eng_pts
                    },
                    '社會': {
                        'items_correct': soc_items,
                        'level_raw': soc_level,
                        'tier': extract_level_details(soc_level)[0],
                        'sub_level': extract_level_details(soc_level)[1],
                        'points': soc_pts
                    },
                    '自然': {
                        'items_correct': sci_items,
                        'level_raw': sci_level,
                        'tier': extract_level_details(sci_level)[0],
                        'sub_level': extract_level_details(sci_level)[1],
                        'points': sci_pts
                    },
                    '作文': {
                        'score': comp_score,
                        'points': comp_pts
                    }
                }
            })
    else:
        if not xlrd:
            raise ImportError("xlrd package is required to read .xls files.")
        wb = xlrd.open_workbook(file_path)
        ws = wb.sheet_by_index(0)
        for r in range(ws.nrows):
            if r < 8: continue
            c1_val = str(ws.cell_value(r, 1)).replace('.0', '').strip()
            c2_val = str(ws.cell_value(r, 2)).replace('.0', '').strip()
            if not (c1_val.isdigit() and c2_val.isdigit()):
                continue
            seat = int(c2_val)
            name = str(ws.cell_value(r, 3)).strip()
            tot_pts = float(ws.cell_value(r, 4)) if ws.cell_value(r, 4) != "" else 0.0
            combo = str(ws.cell_value(r, 5)).strip()

            chi_items = float(ws.cell_value(r, 6)) if ws.cell_value(r, 6) != "" else 0
            chi_level = str(ws.cell_value(r, 7)).strip()
            chi_pts = float(ws.cell_value(r, 8)) if ws.cell_value(r, 8) != "" else 0

            mat_choice = float(ws.cell_value(r, 9)) if ws.cell_value(r, 9) != "" else 0
            mat_q1 = float(ws.cell_value(r, 10)) if ws.cell_value(r, 10) != "" else 0
            mat_q2 = float(ws.cell_value(r, 11)) if ws.cell_value(r, 11) != "" else 0
            mat_nonchoice_score = float(ws.cell_value(r, 12)) if ws.cell_value(r, 12) != "" else 0
            mat_weighted = float(ws.cell_value(r, 13)) if ws.cell_value(r, 13) != "" else 0
            mat_level = str(ws.cell_value(r, 14)).strip()
            mat_pts = float(ws.cell_value(r, 15)) if ws.cell_value(r, 15) != "" else 0

            eng_read_items = float(ws.cell_value(r, 16)) if ws.cell_value(r, 16) != "" else 0
            eng_read_level = str(ws.cell_value(r, 17)).strip()
            eng_listen_items = float(ws.cell_value(r, 18)) if ws.cell_value(r, 18) != "" else 0
            eng_listen_level = str(ws.cell_value(r, 19)).strip()
            eng_weighted = float(ws.cell_value(r, 20)) if ws.cell_value(r, 20) != "" else 0
            eng_level = str(ws.cell_value(r, 21)).strip()
            eng_pts = float(ws.cell_value(r, 22)) if ws.cell_value(r, 22) != "" else 0

            soc_items = float(ws.cell_value(r, 23)) if ws.cell_value(r, 23) != "" else 0
            soc_level = str(ws.cell_value(r, 24)).strip()
            soc_pts = float(ws.cell_value(r, 25)) if ws.cell_value(r, 25) != "" else 0

            sci_items = float(ws.cell_value(r, 26)) if ws.cell_value(r, 26) != "" else 0
            sci_level = str(ws.cell_value(r, 27)).strip()
            sci_pts = float(ws.cell_value(r, 28)) if ws.cell_value(r, 28) != "" else 0

            comp_score = float(ws.cell_value(r, 29)) if ws.cell_value(r, 29) != "" else None
            comp_pts = float(ws.cell_value(r, 30)) if ws.cell_value(r, 30) != "" else None

            c_rank = int(float(ws.cell_value(r, 31))) if ws.cell_value(r, 31) != "" else None
            s_rank = int(float(ws.cell_value(r, 32))) if ws.cell_value(r, 32) != "" else None
            d_rank = int(float(ws.cell_value(r, 33))) if ws.cell_value(r, 33) != "" else None
            dm_rank = int(float(ws.cell_value(r, 34))) if ws.ncols > 34 and ws.cell_value(r, 34) != "" else None
            df_rank = int(float(ws.cell_value(r, 35))) if ws.ncols > 35 and ws.cell_value(r, 35) != "" else None

            students.append({
                'seat_num': seat,
                'seat_str': f"{seat:02d}",
                'name': name,
                'total_points': tot_pts,
                'level_combo': combo,
                'rankings': {
                    'class_rank': c_rank,
                    'school_rank': s_rank,
                    'district_rank': d_rank,
                    'district_male_rank': dm_rank,
                    'district_female_rank': df_rank
                },
                'subjects': {
                    '國文': {
                        'items_correct': chi_items,
                        'level_raw': chi_level,
                        'tier': extract_level_details(chi_level)[0],
                        'sub_level': extract_level_details(chi_level)[1],
                        'points': chi_pts
                    },
                    '數學': {
                        'choice_items': mat_choice,
                        'nonchoice_q1': mat_q1,
                        'nonchoice_q2': mat_q2,
                        'nonchoice_score': mat_nonchoice_score,
                        'weighted_score': mat_weighted,
                        'level_raw': mat_level,
                        'tier': extract_level_details(mat_level)[0],
                        'sub_level': extract_level_details(mat_level)[1],
                        'points': mat_pts
                    },
                    '英語': {
                        'reading_items': eng_read_items,
                        'reading_level': eng_read_level,
                        'listening_items': eng_listen_items,
                        'listening_level': eng_listen_level,
                        'weighted_score': eng_weighted,
                        'level_raw': eng_level,
                        'tier': extract_level_details(eng_level)[0],
                        'sub_level': extract_level_details(eng_level)[1],
                        'points': eng_pts
                    },
                    '社會': {
                        'items_correct': soc_items,
                        'level_raw': soc_level,
                        'tier': extract_level_details(soc_level)[0],
                        'sub_level': extract_level_details(soc_level)[1],
                        'points': soc_pts
                    },
                    '自然': {
                        'items_correct': sci_items,
                        'level_raw': sci_level,
                        'tier': extract_level_details(sci_level)[0],
                        'sub_level': extract_level_details(sci_level)[1],
                        'points': sci_pts
                    },
                    '作文': {
                        'score': comp_score,
                        'points': comp_pts
                    }
                }
            })

    students.sort(key=lambda s: s['seat_num'])
    return students


def parse_rn204_item_and_gap_analysis(file_path: str) -> Dict[str, Any]:
    """Parses RN204 to get promotion gaps and question item analyses."""
    if not openpyxl:
        raise ImportError("openpyxl is required to parse RN204.")
    wb = openpyxl.load_workbook(file_path, data_only=True)
    
    student_gaps = {}
    student_missed = {}
    subject_questions = {}
    
    for sname in wb.sheetnames:
        ws = wb[sname]
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 7: continue

        subj_key = sname.strip()
        q_row = rows[2]
        q_cols = []
        for c in range(7, len(q_row)):
            val = q_row[c]
            if val is not None and str(val).replace('.0', '').isdigit():
                q_cols.append((c, int(float(val))))

        domains = {c: str(rows[3][c]).strip() if rows[3][c] is not None else "" for c, _ in q_cols}
        topics = {c: str(rows[4][c]).strip() if rows[4][c] is not None else "" for c, _ in q_cols}
        goals = {c: str(rows[5][c]).strip() if rows[5][c] is not None else "" for c, _ in q_cols}

        class_rates = {}
        school_rates = {}
        for r_idx in range(len(rows) - 8, len(rows)):
            r_str = " ".join([str(v) for v in rows[r_idx][:7] if v is not None])
            if '班級答對率' in r_str:
                class_rates = {c: float(rows[r_idx][c]) if rows[r_idx][c] is not None and str(rows[r_idx][c]).replace('.','',1).isdigit() else 0.0 for c, _ in q_cols}
            elif '校內答對率' in r_str:
                school_rates = {c: float(rows[r_idx][c]) if rows[r_idx][c] is not None and str(rows[r_idx][c]).replace('.','',1).isdigit() else 0.0 for c, _ in q_cols}

        q_list = []
        for c, q_num in q_cols:
            q_list.append({
                'q_num': q_num,
                'domain': domains.get(c, ''),
                'topic': topics.get(c, ''),
                'goal': goals.get(c, ''),
                'class_correct_rate': class_rates.get(c, 0.0),
                'school_correct_rate': school_rates.get(c, 0.0)
            })
        subject_questions[subj_key] = q_list

        for r_idx in range(6, len(rows)):
            row = rows[r_idx]
            seat_val = row[1]
            if seat_val is None or not str(seat_val).isdigit():
                continue
            seat = int(seat_val)
            gap_val = str(row[3]).strip() if row[3] is not None else ""

            if seat not in student_gaps:
                student_gaps[seat] = {}
                student_missed[seat] = {}

            student_gaps[seat][subj_key] = gap_val
            student_missed[seat][subj_key] = []

            for c, q_num in q_cols:
                ans = str(row[c]).strip() if row[c] is not None else ""
                if ans != "-":
                    student_missed[seat][subj_key].append({
                        'q_num': q_num,
                        'student_choice': ans if ans else "(未作答)",
                        'domain': domains.get(c, ''),
                        'topic': topics.get(c, ''),
                        'goal': goals.get(c, ''),
                        'class_correct_rate': class_rates.get(c, 0.0),
                        'school_correct_rate': school_rates.get(c, 0.0)
                    })

    return {
        'student_gaps': student_gaps,
        'student_missed': student_missed,
        'subject_questions': subject_questions
    }


def parse_rn207_item_options(file_path: str) -> Dict[str, Dict[int, Dict[str, Any]]]:
    """Parses RN207 to retrieve correct answer and options distribution for each question."""
    if not openpyxl:
        return {}
    wb = openpyxl.load_workbook(file_path, data_only=True)
    options_data = {}
    for sname in wb.sheetnames:
        ws = wb[sname]
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 3: continue
        subj_key = sname.strip()
        options_data[subj_key] = {}
        for r_idx in range(3, len(rows)):
            row = rows[r_idx]
            if not row or row[0] is None or not str(row[0]).isdigit():
                continue
            q_num = int(row[0])
            ans = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""
            options_data[subj_key][q_num] = {
                'correct_answer': ans,
                'opt_a': float(row[5]) if len(row) > 5 and row[5] is not None and str(row[5]).replace('.','',1).isdigit() else 0.0,
                'opt_b': float(row[6]) if len(row) > 6 and row[6] is not None and str(row[6]).replace('.','',1).isdigit() else 0.0,
                'opt_c': float(row[7]) if len(row) > 7 and row[7] is not None and str(row[7]).replace('.','',1).isdigit() else 0.0,
                'opt_d': float(row[8]) if len(row) > 8 and row[8] is not None and str(row[8]).replace('.','',1).isdigit() else 0.0,
            }
    return options_data


def enrich_and_validate(
    students: List[Dict[str, Any]],
    benchmarks: Dict[str, Any],
    rn204_data: Dict[str, Any],
    rn207_data: Dict[str, Dict[int, Dict[str, Any]]],
    roster_map: Optional[Dict[Tuple[int, str], Dict[str, str]]] = None
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Merges student scores, rankings, gaps, missed questions, and diagnoses."""
    warnings = []
    enriched_students = []

    df_temp = pd.DataFrame([
        {
            'tot': s['total_points'],
            'chi_pts': s['subjects']['國文']['points'],
            'mat_pts': s['subjects']['數學']['points'],
            'eng_pts': s['subjects']['英語']['points'],
            'soc_pts': s['subjects']['社會']['points'],
            'sci_pts': s['subjects']['自然']['points'],
        } for s in students
    ])

    computed_tot_mean = df_temp['tot'].mean()
    expected_tot_mean = benchmarks.get('averages', {}).get('五科總積分', {}).get('class_mean')
    if expected_tot_mean is not None and abs(computed_tot_mean - expected_tot_mean) > 0.05:
        warnings.append(f"Class total points mean mismatch: computed={computed_tot_mean:.2f}, expected={expected_tot_mean:.2f}")

    subj_avg = benchmarks.get('averages', {})
    stu_gaps = rn204_data.get('student_gaps', {})
    stu_missed = rn204_data.get('student_missed', {})

    for stu in students:
        seat = stu['seat_num']
        name = stu['name']

        student_id = ""
        pin = ""
        if roster_map and (seat, name) in roster_map:
            student_id = roster_map[(seat, name)].get('StudentID', '')
            pin = roster_map[(seat, name)].get('Pin', '')
        elif roster_map and seat in [k[0] for k in roster_map.keys()]:
            for (r_seat, r_name), r_val in roster_map.items():
                if r_seat == seat:
                    student_id = r_val.get('StudentID', '')
                    pin = r_val.get('Pin', '')
                    break

        stu['student_id'] = student_id
        stu['pin'] = pin

        for subj in ['國文', '數學', '英語', '社會', '自然']:
            gap_str = ""
            if subj in ['國文', '社會', '自然']:
                gap_str = stu_gaps.get(seat, {}).get(subj, "")
            elif subj == '數學':
                gap_str = stu_gaps.get(seat, {}).get('數學', "")
            elif subj == '英語':
                r_gap = stu_gaps.get(seat, {}).get('英語閱讀', "")
                l_gap = stu_gaps.get(seat, {}).get('英語聽力', "")
                gap_str = f"閱讀差{r_gap}分 / 聽力差{l_gap}分" if (r_gap or l_gap) else ""

            stu['subjects'][subj]['promotion_gap'] = gap_str

            c_pts_avg = subj_avg.get(subj, {}).get('class_points', 0.0)
            s_pts_avg = subj_avg.get(subj, {}).get('school_points', 0.0)
            cur_pts = stu['subjects'][subj]['points']
            stu['subjects'][subj]['class_avg_points'] = c_pts_avg
            stu['subjects'][subj]['school_avg_points'] = s_pts_avg
            stu['subjects'][subj]['diff_from_class'] = round(cur_pts - c_pts_avg, 2) if c_pts_avg else 0.0
            stu['subjects'][subj]['diff_from_school'] = round(cur_pts - s_pts_avg, 2) if s_pts_avg else 0.0

            missed_list = []
            if subj in ['國文', '數學', '社會', '自然']:
                missed_list = stu_missed.get(seat, {}).get(subj, [])
            elif subj == '英語':
                r_missed = stu_missed.get(seat, {}).get('英語閱讀', [])
                for rm in r_missed:
                    rm_copy = dict(rm)
                    rm_copy['section'] = '閱讀'
                    missed_list.append(rm_copy)
                l_missed = stu_missed.get(seat, {}).get('英語聽力', [])
                for lm in l_missed:
                    lm_copy = dict(lm)
                    lm_copy['section'] = '聽力'
                    missed_list.append(lm_copy)

            for m in missed_list:
                subj_rn207_key = subj
                if subj == '英語':
                    subj_rn207_key = '英語閱讀' if m.get('section') == '閱讀' else '英語聽力'
                opt_info = rn207_data.get(subj_rn207_key, {}).get(m['q_num'], {})
                m['correct_answer'] = opt_info.get('correct_answer', '')

            stu['subjects'][subj]['incorrect_items'] = missed_list

        strengths = []
        opportunities = []
        priorities = []

        for subj in ['國文', '數學', '英語', '社會', '自然']:
            diff_sch = stu['subjects'][subj]['diff_from_school']
            diff_cls = stu['subjects'][subj]['diff_from_class']
            tier = stu['subjects'][subj]['tier']
            gap = str(stu['subjects'][subj].get('promotion_gap', '')).strip()

            if diff_sch >= 0.8 or tier == '精熟':
                strengths.append(subj)

            if gap and gap.replace('.','',1).isdigit():
                g_num = float(gap)
                if 0 < g_num <= 2.0:
                    unit = "題" if subj in ['國文', '社會', '自然'] else "分"
                    opportunities.append(f"{subj}（差 {gap} {unit}晉級）")

            if diff_cls < -0.5 or tier == '待加強':
                priorities.append(subj)

        stu['diagnosis'] = {
            'relative_strengths': strengths,
            'promotion_opportunities': opportunities,
            'priority_review': priorities
        }
        enriched_students.append(stu)

    return enriched_students, warnings


def build_mock_exam_package(
    data_dir: str,
    output_file: Optional[str] = None,
    roster_csv: Optional[str] = None,
    exam_id: Optional[str] = None,
    upload_google_sheets: bool = False,
    replace_existing: bool = True,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Main entry point for importing a mock exam directory into a single normalized bundle."""
    files = find_vendor_files(data_dir)
    print(f"🔎 Scanning folder: {data_dir}")
    print(f"   Found files: {list(files.keys())}")

    if not files.get('rn201') and not files.get('rn202'):
        raise FileNotFoundError("Missing RN201 or RN202 grade report in directory.")
    if not files.get('rn205'):
        raise FileNotFoundError("Missing RN205 benchmark summary report in directory.")

    benchmarks = parse_rn205_metadata_and_benchmarks(files['rn205'])
    student_file = files.get('rn202') or files['rn201']
    students = parse_rn201_or_rn202_students(student_file)

    rn204_data = {'student_gaps': {}, 'student_missed': {}, 'subject_questions': {}}
    if files.get('rn204'):
        rn204_data = parse_rn204_item_and_gap_analysis(files['rn204'])

    rn207_data = {}
    if files.get('rn207'):
        rn207_data = parse_rn207_item_options(files['rn207'])

    roster_map = {}
    if roster_csv and os.path.exists(roster_csv):
        rdf = pd.read_csv(roster_csv)
        for _, r in rdf.iterrows():
            seat = int(r.get('Number', r.get('座號', 0)))
            name = str(r.get('Name', r.get('姓名', ''))).strip()
            sid = str(r.get('StudentID', r.get('學號', ''))).strip()
            pin = str(r.get('Pin', r.get('密碼', ''))).strip()
            roster_map[(seat, name)] = {'StudentID': sid, 'Pin': pin}
    else:
        try:
            import toml
            from google.oauth2.service_account import Credentials
            import gspread
            secrets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml")
            if os.path.exists(secrets_path):
                secrets = toml.load(secrets_path)
                if "gcp_service_account" in secrets:
                    scopes = [
                        "https://www.googleapis.com/auth/spreadsheets.readonly",
                        "https://www.googleapis.com/auth/drive.readonly"
                    ]
                    creds = Credentials.from_service_account_info(dict(secrets["gcp_service_account"]), scopes=scopes)
                    client = gspread.authorize(creds)
                    sheet = client.open("School_Master_Score").sheet1
                    data = sheet.get_all_records()
                    for r in data:
                        seat = int(r.get('Number', 0))
                        name = str(r.get('Name', '')).strip()
                        sid = str(r.get('StudentID', '')).strip()
                        pin = str(r.get('Pin', '')).strip()
                        roster_map[(seat, name)] = {'StudentID': sid, 'Pin': pin}
        except Exception as e:
            pass

    enriched_students, warnings = enrich_and_validate(
        students, benchmarks, rn204_data, rn207_data, roster_map
    )

    class_weak_questions = {}
    for subj, qlist in rn204_data.get('subject_questions', {}).items():
        weak_in_subj = []
        for q in qlist:
            c_rate = q.get('class_correct_rate', 0.0)
            s_rate = q.get('school_correct_rate', 0.0)
            if s_rate > 0 and (c_rate - s_rate) <= -5.0:
                weak_in_subj.append({
                    'q_num': q['q_num'],
                    'domain': q['domain'],
                    'topic': q['topic'],
                    'goal': q['goal'],
                    'class_correct_rate': c_rate,
                    'school_correct_rate': s_rate,
                    'diff': round(c_rate - s_rate, 1)
                })
        if weak_in_subj:
            class_weak_questions[subj] = weak_in_subj

    exam_name = benchmarks.get('exam_name', '115第一次國中教育會考模擬測驗-第1~2冊')
    m_year = re.search(r"(\d{3})", exam_name)
    school_year = m_year.group(1) if m_year else "115"
    m_round = re.search(r"第([一二三四五\d]+)次", exam_name)
    round_label = m_round.group(0) if m_round else "第一次"
    chinese_digits = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5'}
    round_digit = chinese_digits.get(m_round.group(1), m_round.group(1)) if m_round else "1"

    if not exam_id:
        exam_id = f"mock_{school_year}_{round_digit}"

    package = {
        'metadata': {
            'exam_id': exam_id,
            'exam_name': exam_name,
            'exam_label': f"{round_label}模擬考 (第1~2冊)",
            'school_year': school_year,
            'round_name': round_label,
            'test_date': benchmarks.get('test_date', '2026/09/08'),
            'cohort': benchmarks.get('cohort', {}),
            'has_composition': False
        },
        'benchmarks': {
            'averages': benchmarks.get('averages', {}),
            'level_combos': benchmarks.get('level_combos', {}),
            'points_distribution': benchmarks.get('points_distribution', []),
            'subject_tiers': benchmarks.get('subject_tiers', {}),
            'class_weak_questions': class_weak_questions
        },
        'students': enriched_students,
        'subject_questions': rn204_data.get('subject_questions', {})
    }

    if dry_run:
        print("\n" + "=" * 50)
        print("🔍 DRY RUN VALIDATION PREVIEW (No changes made)")
        print("=" * 50)
        print(f"Exam ID:        {exam_id}")
        print(f"Exam Name:      {exam_name}")
        print(f"Test Date:      {benchmarks.get('test_date')}")
        print(f"Student Count:  {len(enriched_students)}")
        print(f"Class Mean:     {benchmarks.get('averages', {}).get('五科總積分', {}).get('class_mean')}")
        from core.mock_sheets_sync import serialize_mock_package_to_tables
        tables = serialize_mock_package_to_tables(package)
        print("\nNormalized Google Sheets tables plan:")
        for tname, tdata in tables.items():
            print(f"  - MockExam_{tname.capitalize()}: {len(tdata) - 1} rows (columns: {len(tdata[0])})")
        print("=" * 50 + "\n")
        return package

    # 1. Save local JSON cache
    if not output_file:
        out_dir = os.path.join(os.path.dirname(__file__), "data", "mock_exams")
        os.makedirs(out_dir, exist_ok=True)
        output_file = os.path.join(out_dir, f"{exam_id}.json")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(package, f, ensure_ascii=False, indent=2)

    print(f"✅ Successfully imported {len(enriched_students)} students!")
    print(f"📦 Saved local mock exam bundle to: {output_file}")

    if warnings:
        print(f"⚠️ Warnings during import ({len(warnings)}):")
        for w in warnings:
            print(f"   - {w}")

    # 2. Upload to Google Sheets if requested
    if upload_google_sheets:
        print("\n☁️ Uploading normalized mock exam package to Google Sheets (School_Master_Score)...")
        try:
            import toml
            from google.oauth2.service_account import Credentials
            secrets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml")
            if not os.path.exists(secrets_path):
                raise FileNotFoundError(f"Missing secrets file at: {secrets_path}")
            secrets = toml.load(secrets_path)
            gcp_creds = dict(secrets["gcp_service_account"])
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_info(gcp_creds, scopes=scopes)
            uploaded_counts = upload_mock_exam_to_google_sheets(
                package=package,
                creds=creds,
                spreadsheet_name="School_Master_Score",
                replace_existing=replace_existing,
                dry_run=False
            )
            print("🎉 Google Sheets sync successful! Rows uploaded:")
            for sheet_name, count in uploaded_counts.items():
                print(f"   - {sheet_name}: {count} records")
        except Exception as e:
            sa_email = gcp_creds.get('client_email', 'unknown') if 'gcp_creds' in locals() else 'school-api@student-score-portal.iam.gserviceaccount.com'
            print("\n" + "!" * 60)
            print("⚠️ Google Sheets Upload Failed!")
            print(f"Error: {e}")
            if "403" in str(e) or "permission" in str(e).lower():
                print("\n【權限不足提示 (Permission Error 403)】:")
                print(f"Google 試算表 `School_Master_Score` 目前僅授予 Service Account 檢視權限 (Viewer)，無法新增工作表或寫入成績。")
                print(f"請前往 Google Drive / Sheets，將試算表共用權限調整如下：")
                print(f"1. 開啟試算表：https://docs.google.com/spreadsheets/d/1wlVD_J3ZPP94BqpgNqvAgsBqPsvNyRW4YtZ9fVu83Ak/edit")
                print(f"2. 點擊右上角「共用」(Share)。")
                print(f"3. 找到 Service Account 帳號：\n   👉 {sa_email}")
                print(f"4. 將其角色由「檢視者」(Viewer) 改為「編輯者」(Editor) 並儲存。")
                print(f"5. 重新執行匯入指令即可完成同步上傳：")
                print(f"   python import_mock_exam.py --data-dir \"{data_dir}\" --upload-google-sheets")
            print("!" * 60 + "\n")

    return package


def main():
    parser = argparse.ArgumentParser(description="Import Mock Exam vendor files into normalized JSON and Google Sheets.")
    parser.add_argument("--data-dir", required=True, help="Directory containing vendor mock exam files.")
    parser.add_argument("--output", required=False, default=None, help="Destination JSON path.")
    parser.add_argument("--roster", required=False, default=None, help="Optional CSV roster mapping seat/name to StudentID.")
    parser.add_argument("--exam-id", required=False, default=None, help="Custom ExamID identifier (e.g. mock_115_1).")
    parser.add_argument("--upload-google-sheets", action="store_true", help="Upload the normalized mock exam package directly to Google Spreadsheet.")
    parser.add_argument("--replace-existing", action="store_true", default=True, help="Replace existing records in Google Sheets for this ExamID (idempotent).")
    parser.add_argument("--dry-run", action="store_true", help="Perform parsing and validation without writing to disk or Google Sheets.")
    args = parser.parse_args()

    try:
        build_mock_exam_package(
            data_dir=args.data_dir,
            output_file=args.output,
            roster_csv=args.roster,
            exam_id=args.exam_id,
            upload_google_sheets=args.upload_google_sheets,
            replace_existing=args.replace_existing,
            dry_run=args.dry_run
        )
    except Exception as e:
        print(f"❌ Error during import: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
