"""
tests/synthetic_fixtures.py
----------------------------
Safe synthetic test fixtures for automated testing:
- Zero real student PII (uses TEST001, 測試學生A, etc.)
- Multi-exam simulation for Grade 9 (mock_115_1, mock_115_2, mock_115_3, mock_115_4)
- Deterministic score progression for trend and comparison testing
"""

from typing import Dict, Any, List


def create_synthetic_student(
    seat_no: int,
    student_id: str,
    name: str,
    total_points: float,
    level_combo: str,
    class_rank: int,
    school_rank: int,
    chinese_pts: float = 6.0,
    math_pts: float = 6.0,
    english_pts: float = 5.0,
    social_pts: float = 5.0,
    science_pts: float = 5.0
) -> Dict[str, Any]:
    """Generates a synthetic student mock exam record."""
    subjects = {
        '國文': {
            'items_correct': 38,
            'weighted_score': 38.0,
            'points': chinese_pts,
            'tier': '精熟' if chinese_pts >= 5 else ('基礎' if chinese_pts >= 3 else '待加強'),
            'sub_level': 'A++' if chinese_pts == 7 else ('A+' if chinese_pts == 6 else ('A' if chinese_pts == 5 else 'B++')),
            'level_raw': '精熟(A+)' if chinese_pts == 6 else '精熟(A)',
            'promotion_gap': '晉級 A++ 尚差 2 題' if chinese_pts < 7 else '',
            'class_avg_points': 4.5,
            'school_avg_points': 4.2,
            'diff_from_class': round(chinese_pts - 4.5, 2),
            'diff_from_school': round(chinese_pts - 4.2, 2),
            'incorrect_items': [
                {
                    'q_num': 10,
                    'section': '單題',
                    'student_choice': 'B',
                    'correct_answer': 'C',
                    'domain': '閱讀理解',
                    'topic': '文意推論',
                    'goal': '理解文本主旨',
                    'class_correct_rate': 48.1,
                    'school_correct_rate': 52.3
                }
            ]
        },
        '英語': {
            'items_correct': 35,
            'reading_items': 35,
            'reading_level': 'A',
            'listening_items': 20,
            'listening_level': 'A',
            'weighted_score': 88.5,
            'points': english_pts,
            'tier': '精熟' if english_pts >= 5 else '基礎',
            'sub_level': 'A' if english_pts >= 5 else 'B++',
            'level_raw': '精熟(A)' if english_pts >= 5 else '基礎(B++)',
            'promotion_gap': '晉級 A+ 尚差 1 題',
            'class_avg_points': 4.2,
            'school_avg_points': 4.0,
            'diff_from_class': round(english_pts - 4.2, 2),
            'diff_from_school': round(english_pts - 4.0, 2),
            'incorrect_items': []
        },
        '數學': {
            'choice_items': 22,
            'nonchoice_score': 5.0,
            'weighted_score': 85.2,
            'points': math_pts,
            'tier': '精熟' if math_pts >= 5 else '基礎',
            'sub_level': 'A' if math_pts >= 5 else 'B++',
            'level_raw': '精熟(A)',
            'promotion_gap': '晉級 A+ 尚差 2 分',
            'class_avg_points': 4.0,
            'school_avg_points': 3.8,
            'diff_from_class': round(math_pts - 4.0, 2),
            'diff_from_school': round(math_pts - 3.8, 2),
            'incorrect_items': []
        },
        '社會': {
            'items_correct': 45,
            'weighted_score': 45.0,
            'points': social_pts,
            'tier': '精熟' if social_pts >= 5 else '基礎',
            'sub_level': 'A' if social_pts >= 5 else 'B++',
            'level_raw': '精熟(A)',
            'promotion_gap': '',
            'class_avg_points': 4.4,
            'school_avg_points': 4.1,
            'diff_from_class': round(social_pts - 4.4, 2),
            'diff_from_school': round(social_pts - 4.1, 2),
            'incorrect_items': []
        },
        '自然': {
            'items_correct': 42,
            'weighted_score': 42.0,
            'points': science_pts,
            'tier': '精熟' if science_pts >= 5 else '基礎',
            'sub_level': 'A' if science_pts >= 5 else 'B++',
            'level_raw': '精熟(A)',
            'promotion_gap': '',
            'class_avg_points': 4.1,
            'school_avg_points': 3.9,
            'diff_from_class': round(science_pts - 4.1, 2),
            'diff_from_school': round(science_pts - 3.9, 2),
            'incorrect_items': []
        }
    }

    return {
        'seat_num': seat_no,
        'seat_str': f"{seat_no:02d}",
        'name': name,
        'student_id': student_id,
        'total_points': total_points,
        'level_combo': level_combo,
        'rankings': {
            'class_rank': class_rank,
            'school_rank': school_rank,
            'district_rank': school_rank * 100,
            'district_male_rank': school_rank * 50,
            'district_female_rank': None
        },
        'diagnosis': {
            'relative_strengths': ['國文 (A+)', '數學 (A)'],
            'promotion_opportunities': ['英語: 距 A+ 僅差 1 題'],
            'priority_review': ['自然: 實驗試題']
        },
        'subjects': subjects
    }


def create_synthetic_exam_package(
    exam_id: str = "mock_115_1",
    school_year: str = "115",
    round_name: str = "第一次",
    round_num: int = 1,
    test_date: str = "2026/09/08",
    num_students: int = 5
) -> Dict[str, Any]:
    """Builds a complete normalized mock exam bundle with safe synthetic data."""
    students = []
    for i in range(1, num_students + 1):
        # Deterministic synthetic variation based on round_num and seat
        pts = 20.0 + (round_num * 2.0) - (i * 0.5)
        combo = "5A" if pts >= 28 else ("3A2B" if pts >= 24 else "1A4B")
        students.append(create_synthetic_student(
            seat_no=i,
            student_id=f"TEST{i:03d}",
            name=f"測試學生{chr(64 + i)}",
            total_points=round(pts, 1),
            level_combo=combo,
            class_rank=i,
            school_rank=i * 15,
            chinese_pts=min(7.0, 4.0 + round_num),
            math_pts=min(7.0, 4.0 + (round_num * 0.5)),
            english_pts=min(7.0, 4.0 + (round_num * 0.5)),
            social_pts=5.0,
            science_pts=5.0
        ))

    package = {
        'metadata': {
            'exam_id': exam_id,
            'exam_name': f"{school_year}{round_name}國中教育會考模擬測驗-第1~{round_num + 1}冊",
            'exam_label': f"{round_name}模擬考 (第1~{round_num + 1}冊)",
            'school_year': school_year,
            'round_name': round_name,
            'test_date': test_date,
            'cohort': {
                'class_students': num_students,
                'school_students': 500,
                'district_students': 50000,
                'class_num': '19'
            },
            'has_composition': False,
            'schema_version': 1
        },
        'benchmarks': {
            'averages': {
                '五科總積分': {'class_mean': 22.0, 'school_mean': 20.5, 'class_rank_in_school': 5},
                '國文': {'class_points': 5.0, 'school_points': 4.5, 'class_rank_in_school': 4},
                '英語': {'class_points': 4.8, 'school_points': 4.3, 'class_rank_in_school': 5},
                '數學': {'class_points': 4.6, 'school_points': 4.1, 'class_rank_in_school': 6},
                '社會': {'class_points': 4.9, 'school_points': 4.4, 'class_rank_in_school': 4},
                '自然': {'class_points': 4.7, 'school_points': 4.2, 'class_rank_in_school': 5}
            },
            'level_combos': {
                '5A': {'class': 2, 'school': 30, 'district': 3000},
                '4A1B': {'class': 3, 'school': 50, 'district': 5000},
                '3A2B': {'class': 5, 'school': 80, 'district': 8000}
            },
            'points_distribution': [
                {'points': 30.0, 'class_count': 1, 'class_top_pct': 3.7, 'school_top_pct': 2.1, 'district_top_pct': 1.9},
                {'points': 25.0, 'class_count': 5, 'class_top_pct': 18.5, 'school_top_pct': 15.0, 'district_top_pct': 14.2},
                {'points': 20.0, 'class_count': 10, 'class_top_pct': 55.0, 'school_top_pct': 48.0, 'district_top_pct': 45.0}
            ],
            'subject_tiers': {
                '國文': {'class': {'精熟': 10, '基礎': 15, '待加強': 2}},
                '英語': {'class': {'精熟': 8, '基礎': 16, '待加強': 3}},
                '數學': {'class': {'精熟': 7, '基礎': 17, '待加強': 3}}
            },
            'class_weak_questions': {
                '國文': [{'q_num': 15, 'domain': '語文常識', 'topic': '標點符號', 'goal': '運用', 'class_correct_rate': 40.0, 'school_correct_rate': 55.0, 'diff': -15.0}]
            }
        },
        'students': students,
        'subject_questions': {
            '國文': [{'q_num': 10, 'domain': '閱讀理解', 'topic': '文意推論', 'goal': '理解文本主旨', 'class_correct_rate': 48.1, 'school_correct_rate': 52.3}]
        }
    }
    return package


def get_four_synthetic_exams() -> List[Dict[str, Any]]:
    """Returns a sequence of 4 synthetic mock exams for Grade 9 testing."""
    rounds = [
        ("mock_115_1", "第一次", 1, "2026/09/08"),
        ("mock_115_2", "第二次", 2, "2026/12/15"),
        ("mock_115_3", "第三次", 3, "2027/02/24"),
        ("mock_115_4", "第四次", 4, "2027/04/18")
    ]
    return [
        create_synthetic_exam_package(
            exam_id=eid,
            school_year="115",
            round_name=rname,
            round_num=rnum,
            test_date=tdate,
            num_students=5
        )
        for eid, rname, rnum, tdate in rounds
    ]
