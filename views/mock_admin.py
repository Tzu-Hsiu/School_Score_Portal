"""
views/mock_admin.py
--------------------
Teacher Admin Panel for Mock Exam analysis (教師模擬考管理與數據決策後台).
Provides aggregated cohort statistics, 5A/level distribution, full class transcripts,
item-level weakness diagnosis, and secure student-level inspection for homeroom teachers.
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from core.mock_data_loader import get_available_mock_exams, load_mock_exam
from core.mock_charts import (
    create_mock_radar_chart,
    create_mock_points_distribution_chart,
    create_cohort_combos_chart,
    create_subject_tiers_chart
)


def render(regular_df: pd.DataFrame, col_info: pd.DataFrame, exclude_stats: List[str]):
    """Renders the Teacher Mock Exam Panel."""
    st.success("👨‍🏫 歡迎進入【模擬考教師管理與深度分析後台】！")

    available_mocks = get_available_mock_exams()
    if not available_mocks:
        st.warning("⚠️ 系統目前尚未匯入任何模擬考資料。")
        st.info("請於終端機執行 `python import_mock_exam.py --data-dir <目錄路徑>` 進行匯入。")
        return

    # Select exam
    exam_labels = [f"{ex['exam_label']} ({ex['test_date']})" for ex in available_mocks]
    label_to_id = {f"{ex['exam_label']} ({ex['test_date']})": ex['exam_id'] for ex in available_mocks}
    selected_label = st.selectbox("📌 選擇分析之模擬考 (Select Mock Exam)", exam_labels, key="teacher_mock_select")
    selected_id = label_to_id[selected_label]

    exam_bundle = load_mock_exam(selected_id)
    if not exam_bundle:
        st.error("無法載入模擬考資料。")
        return

    metadata = exam_bundle.get("metadata", {})
    benchmarks = exam_bundle.get("benchmarks", {})
    students = exam_bundle.get("students", [])
    cohort = metadata.get("cohort", {})

    # Scoped responsive styles for admin view
    st.markdown("""
    <style>
    [data-testid="stMetricValue"] {
        font-size: clamp(1.3rem, 2.5vw, 1.85rem) !important;
        word-break: break-word !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: clamp(0.82rem, 1.2vw, 0.95rem) !important;
        font-weight: 600 !important;
    }
    @media (max-width: 680px) {
        [data-testid="column"] {
            min-width: 100% !important;
            margin-bottom: 0.5rem !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    tab_m1, tab_m2, tab_m3, tab_m4 = st.tabs([
        "📊 班級常模與統計落點 (Cohort Overview)",
        "📋 全班成績總表與匯出 (Class Master Table)",
        "🔍 學生個別深度診斷 (Student Inspector)",
        "🎯 試題弱項與教學複習指引 (Item Diagnostics)"
    ])

    # --- TAB 1: Aggregated Cohort Stats ---
    with tab_m1:
        st.subheader("🏫 本班模擬考總體表現 vs 全校／全區常模")

        averages = benchmarks.get("averages", {})
        tot_avg = averages.get("五科總積分", {})

        c_mean = tot_avg.get('class_mean', 0.0)
        s_mean = tot_avg.get('school_mean', 0.0)
        diff_sch = c_mean - s_mean

        # Row 1: Points comparisons (responsive 2x2)
        k1, k2 = st.columns(2)
        k1.metric("班級五科總積分平均", f"{c_mean:.2f} 分", delta=f"{diff_sch:+.2f} 分 (vs 校平均)")
        k2.metric("全校五科總積分平均", f"{s_mean:.2f} 分")

        # Row 2: Standing and Size
        k3, k4 = st.columns(2)
        k3.metric("本班全校排名 (班排名)", f"第 {tot_avg.get('class_rank_in_school', '-')} 名 / 共 19 班")
        k4.metric("應考人數", f"{cohort.get('class_students', len(students))} 人 (全校 {cohort.get('school_students', 516)} 人)")

        st.markdown("---")

        # Subject Stats Table
        st.markdown("#### 📚 各科目班級統計指標 (Subject Statistical Breakdown)")
        subj_rows = []
        df_students = pd.DataFrame([
            {
                '國文': s['subjects']['國文']['points'],
                '數學': s['subjects']['數學']['points'],
                '英語': s['subjects']['英語']['points'],
                '社會': s['subjects']['社會']['points'],
                '自然': s['subjects']['自然']['points'],
                '總積分': s['total_points']
            } for s in students
        ])

        for s in ['國文', '英語', '數學', '社會', '自然']:
            pts_series = df_students[s]
            s_bench = averages.get(s, {})
            diff_val = pts_series.mean() - s_bench.get('school_points', 0)
            subj_rows.append({
                '科目': s,
                '班平均': f"{pts_series.mean():.2f}",
                '校平均': f"{s_bench.get('school_points', 0):.2f}",
                'vs 校平均': f"{diff_val:+.2f}",
                '中位數': f"{pts_series.median():.1f}",
                '標準差': f"{pts_series.std():.2f}",
                '最高分': f"{pts_series.max():g}",
                '最低分': f"{pts_series.min():g}",
                '全校班排': f"第 {s_bench.get('class_rank_in_school', '-')} 名"
            })

        df_subj_stats = pd.DataFrame(subj_rows)

        def style_admin_diff(val):
            if not val or not isinstance(val, str): return ''
            if val.startswith('+'): return 'color: #27ae60; font-weight: bold;'
            if val.startswith('-'): return 'color: #e74c3c; font-weight: bold;'
            return ''

        styled_subj_stats = df_subj_stats.style.map(style_admin_diff, subset=['vs 校平均'])
        st.dataframe(styled_subj_stats, use_container_width=True, hide_index=True)

        st.markdown("---")

        # Visualizations
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown("**🕸️ 班級平均 vs 全校平均 能力雷達圖**")
            subj_list = ['國文', '數學', '英語', '社會', '自然']
            cls_pts = [averages.get(s, {}).get('class_points', 0.0) for s in subj_list]
            sch_pts = [averages.get(s, {}).get('school_points', 0.0) for s in subj_list]
            fig_rad = create_mock_radar_chart(subj_list, None, cls_pts, sch_pts)
            st.plotly_chart(fig_rad, use_container_width=True)

        with col_c2:
            st.markdown("**📊 各科三等級比例分布 (精熟 A / 基礎 B / 待加強 C)**")
            fig_tiers = create_subject_tiers_chart(benchmarks.get("subject_tiers", {}))
            st.plotly_chart(fig_tiers, use_container_width=True)

        st.markdown("---")
        st.markdown("**🏆 全班 vs 全校 五科標示組合分布**")
        fig_combos = create_cohort_combos_chart(benchmarks.get("level_combos", {}))
        st.plotly_chart(fig_combos, use_container_width=True)

    # --- TAB 2: Class Master Table ---
    with tab_m2:
        st.subheader("📋 全班模擬考成績總表")
        master_rows = []
        for s in students:
            master_rows.append({
                '座號': s['seat_num'],
                '姓名': s['name'],
                '學號': s.get('student_id', ''),
                '總積分': s['total_points'],
                '標示組合': s['level_combo'],
                '班排': s['rankings']['class_rank'],
                '校排': s['rankings']['school_rank'],
                '區排': s['rankings']['district_rank'],
                '國文標示': s['subjects']['國文']['sub_level'],
                '國文積分': s['subjects']['國文']['points'],
                '數學標示': s['subjects']['數學']['sub_level'],
                '數學積分': s['subjects']['數學']['points'],
                '英語標示': s['subjects']['英語']['sub_level'],
                '英語積分': s['subjects']['英語']['points'],
                '社會標示': s['subjects']['社會']['sub_level'],
                '社會積分': s['subjects']['社會']['points'],
                '自然標示': s['subjects']['自然']['sub_level'],
                '自然積分': s['subjects']['自然']['points'],
            })

        df_master = pd.DataFrame(master_rows).sort_values(by=['班排', '座號'])
        st.dataframe(df_master, use_container_width=True, hide_index=True)

        csv_data = df_master.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 下載全班模擬考成績總表 (CSV)",
            data=csv_data,
            file_name=f"{metadata.get('exam_name', '模擬考')}_全班成績總表.csv",
            mime="text/csv"
        )

    # --- TAB 3: Student Inspector ---
    with tab_m3:
        st.subheader("🔍 個別學生模擬考深度落點診斷")
        st.markdown("教師可在此點選任意學生，完整檢視其雷達圖、錯題明細、知識點分析與晉級突破點：")

        student_names = [f"{s['seat_str']}號 {s['name']} (總積分: {s['total_points']:g}分, 班排: {s['rankings']['class_rank']})" for s in sorted(students, key=lambda x: x['seat_num'])]
        chosen_stu_label = st.selectbox("選擇學生 (Select Student)", student_names, key="teacher_inspect_stu")

        chosen_seat = int(chosen_stu_label.split("號")[0])
        inspect_stu = next((s for s in students if s['seat_num'] == chosen_seat), None)

        if inspect_stu:
            from views.mock_dashboard import _render_student_overview, _render_student_diagnostics
            _render_student_overview(inspect_stu, benchmarks, cohort)
            st.markdown("---")
            _render_student_diagnostics(inspect_stu, benchmarks)

    # --- TAB 4: Item Diagnostics ---
    with tab_m4:
        st.subheader("🎯 班級試題弱項與教學複習指引")
        st.markdown("""
        本分頁自動比對**全班各題答對率**與**全校平均答對率**。
        當本班答對率低於全校達 **5% 以上** 時，系統將標記為「班級共同弱項題」，提供導師與任課教師安排課堂重點複習。
        """)

        weak_dict = benchmarks.get("class_weak_questions", {})
        if not weak_dict:
            # Re-evaluate live if needed
            subj_questions = exam_bundle.get("subject_questions", {})
            for subj, qlist in subj_questions.items():
                w_list = []
                for q in qlist:
                    c_rate = q.get('class_correct_rate', 0.0)
                    s_rate = q.get('school_correct_rate', 0.0)
                    if s_rate > 0 and (c_rate - s_rate) <= -5.0:
                        w_list.append({
                            'q_num': q['q_num'],
                            'domain': q['domain'],
                            'topic': q['topic'],
                            'goal': q['goal'],
                            'class_correct_rate': c_rate,
                            'school_correct_rate': s_rate,
                            'diff': round(c_rate - s_rate, 1)
                        })
                if w_list:
                    weak_dict[subj] = w_list

        if not weak_dict:
            st.success("🎉 本班在所有科目的各試題作答率皆高於或接近全校平均，無顯著落後之共同弱項題！")
        else:
            for subj, q_items in weak_dict.items():
                st.markdown(f"#### 📌 {subj} 共同弱項題（共 {len(q_items)} 題落後校平均 5% 以上）")
                df_w = pd.DataFrame([
                    {
                        '題號': f"第 {q['q_num']} 題",
                        '學習領域': q.get('domain', '-'),
                        '單元知識點': q.get('topic', '-'),
                        '評量目標': q.get('goal', '-'),
                        '本班答對率': f"{q['class_correct_rate']:.1f}%",
                        '全校答對率': f"{q['school_correct_rate']:.1f}%",
                        '差距 (vs 校平均)': f"{q['diff']:+.1f}%"
                    } for q in q_items
                ])
                st.dataframe(df_w, use_container_width=True, hide_index=True)
