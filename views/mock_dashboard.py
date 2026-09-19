"""
views/mock_dashboard.py
------------------------
Student and Parent Mock Exam Dashboard (模擬考成績與深度分析頁面).
Displays comprehensive CAP (國中教育會考) mock exam results, radar comparisons,
score distribution percentiles, promotion gap analysis, missed question diagnostics,
and statistically sound comparisons with regular exams.
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from core.mock_data_loader import (
    get_available_mock_exams,
    load_mock_exam,
    get_student_mock_data,
    compare_mock_with_regular
)
from core.mock_charts import (
    create_mock_radar_chart,
    create_mock_points_distribution_chart,
    create_mock_subject_bars
)


def render(
    regular_df: pd.DataFrame,
    col_info: pd.DataFrame,
    exclude_stats: List[str],
    is_virtual: bool,
    student_data: pd.DataFrame,
    student_name: str
):
    """Renders the Mock Exam Dashboard."""
    available_mocks = get_available_mock_exams()
    if not available_mocks:
        st.warning("⚠️ 系統目前尚未匯入任何模擬考資料。(No Mock Exam Data Found)")
        st.info("請管理員使用 `python import_mock_exam.py --data-dir <目錄路徑>` 匯入模擬考資料。")
        return

    # Scoped responsive styles for mock exam views
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

    # 1. Exam selector
    exam_labels = [f"{ex['exam_label']} ({ex['test_date']})" for ex in available_mocks]
    label_to_id = {f"{ex['exam_label']} ({ex['test_date']})": ex['exam_id'] for ex in available_mocks}

    col_sel1, col_sel2 = st.columns([3, 1])
    with col_sel1:
        selected_label = st.selectbox("📌 選擇模擬考 (Select Mock Exam)", exam_labels)
    selected_id = label_to_id[selected_label]

    exam_bundle = load_mock_exam(selected_id)
    if not exam_bundle:
        st.error("無法載入該模擬考資料。")
        return

    metadata = exam_bundle.get("metadata", {})
    benchmarks = exam_bundle.get("benchmarks", {})
    cohort = metadata.get("cohort", {})

    # 2. Student identification & Access Control
    student_mock = None
    if not is_virtual:
        auth_student_id = student_data['StudentID'].iloc[0] if not student_data.empty and 'StudentID' in student_data.columns else None
        student_mock = get_student_mock_data(
            exam_bundle,
            student_id=auth_student_id,
            student_name=student_name
        )

        if not student_mock:
            st.warning(f"在本次模擬考名冊中未查找到您的成績資料（學生：{student_name}）。若有疑問請洽導師。")
            return

    # 3. Main Dashboard Navigation Tabs
    if is_virtual:
        st.info("🏫 目前處於【模擬考班級總覽模式】。下方顯示全班整體常模與分布數據。")
        _render_virtual_mock_overview(exam_bundle)
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 總體落點與成績 (Overall)",
        "🔍 弱項診斷與知識點 (Diagnostics)",
        "⚖️ 模擬考與段考綜合對比 (Comparison)",
        "📈 歷次模擬考趨勢 (Trends)"
    ])

    with tab1:
        _render_student_overview(student_mock, benchmarks, cohort)

    with tab2:
        _render_student_diagnostics(student_mock, benchmarks)

    with tab3:
        _render_regular_vs_mock_comparison(
            exam_bundle, student_mock, regular_df, student_data, col_info, exclude_stats
        )

    with tab4:
        _render_historical_mock_trends(available_mocks, student_mock)


def _render_student_overview(
    student_mock: Dict[str, Any],
    benchmarks: Dict[str, Any],
    cohort: Dict[str, Any]
):
    """Tab 1: Overall KPIs, Subject Table, Radar and Distribution Charts."""
    st.markdown("### 🏆 本次模擬考總合成績 (Overall Summary)")

    # Top KPI Cards (Responsive 2x2 Grid)
    tot_pts = student_mock.get("total_points", 0.0)
    combo = student_mock.get("level_combo", "-")
    ranks = student_mock.get("rankings", {})
    c_rank = ranks.get("class_rank")
    s_rank = ranks.get("school_rank")
    d_rank = ranks.get("district_rank")

    c_total = cohort.get("class_students", 27)
    s_total = cohort.get("school_students", 516)
    d_total = cohort.get("district_students", 58502)

    c_pct_str = f"前 {(c_rank / c_total) * 100:.1f}%" if c_rank and c_total else ""
    s_pct_str = f"前 {(s_rank / s_total) * 100:.1f}% (PR {100 - (s_rank / s_total) * 100:.1f})" if s_rank and s_total else ""
    d_pct_str = f"全區前 {(d_rank / d_total) * 100:.1f}%" if d_rank and d_total else ""

    # Row 1: Core Performance Scores
    k1, k2 = st.columns(2)
    k1.metric("五科總積分", f"{tot_pts:g} 分", help="基北區五科計分，每科最高 7 分，滿分 35 分（不含作文）")
    k2.metric("標示組合", combo, help="各科能力等級標示組合（例：5A, 4A1B, 3A2B）")

    # Row 2: Cohort Standings
    k3, k4 = st.columns(2)
    k3.metric("班級排名", f"第 {c_rank} 名 / {c_total}人" if c_rank else "-", delta=c_pct_str or None, delta_color="off")
    k4.metric("全校排名", f"第 {s_rank} 名 / {s_total}人" if s_rank else "-", delta=s_pct_str or None, delta_color="off")

    if d_rank:
        st.info(f"📍 **基北區落點參考：** 全區第 **{d_rank:,}** 名 / {d_total:,} 人（{d_pct_str}）")

    st.markdown("---")

    # Subject Performance Table with concise headers
    st.markdown("### 📋 各科成績與落點明細 (Subject Breakdown)")
    subj_list = ['國文', '數學', '英語', '社會', '自然']
    table_rows = []

    for s in subj_list:
        s_info = student_mock.get("subjects", {}).get(s, {})
        level_raw = s_info.get("level_raw", "-")
        tier = s_info.get("tier", "-")
        sub_level = s_info.get("sub_level", "-")
        pts = s_info.get("points", 0.0)
        c_avg = s_info.get("class_avg_points", 0.0)
        s_avg = s_info.get("school_avg_points", 0.0)
        diff_cls = s_info.get("diff_from_class", 0.0)
        diff_sch = s_info.get("diff_from_school", 0.0)
        gap = s_info.get("promotion_gap", "-")

        # Concise raw detail
        detail_score = ""
        if s in ['國文', '社會', '自然']:
            detail_score = f"{int(s_info.get('items_correct', 0))} 題"
        elif s == '數學':
            detail_score = f"選 {int(s_info.get('choice_items', 0))} 題 / 非選 {s_info.get('nonchoice_score', 0):g} 分"
        elif s == '英語':
            detail_score = f"閱 {int(s_info.get('reading_items', 0))} 題 / 聽 {int(s_info.get('listening_items', 0))} 題"

        table_rows.append({
            '科目': s,
            '作答得分/題數': detail_score,
            '能力標示': level_raw,
            '個人積分': f"{pts:g}",
            '班平均': f"{c_avg:.2f}",
            'vs 班平均': f"{diff_cls:+.2f}",
            '校平均': f"{s_avg:.2f}",
            'vs 校平均': f"{diff_sch:+.2f}",
            '晉級下一標示差距': gap if gap else "已達最高標示"
        })

    df_table = pd.DataFrame(table_rows)

    def style_diff(val):
        if not val or not isinstance(val, str): return ''
        if val.startswith('+'): return 'color: #27ae60; font-weight: bold;'
        if val.startswith('-'): return 'color: #e74c3c; font-weight: bold;'
        return ''

    def style_level(val):
        if not val or not isinstance(val, str): return ''
        if '精熟' in val or 'A' in val: return 'background-color: rgba(46, 204, 113, 0.15); font-weight: bold;'
        if '待加強' in val or 'C' in val: return 'background-color: rgba(231, 76, 60, 0.15); font-weight: bold;'
        return 'background-color: rgba(243, 156, 18, 0.15);'

    styled_df = df_table.style\
        .map(style_diff, subset=['vs 班平均', 'vs 校平均'])\
        .map(style_level, subset=['能力標示'])

    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Visualizations: Radar Chart & Score Distribution
    c_chart1, c_chart2 = st.columns([1, 1])

    with c_chart1:
        st.markdown("**🕸️ 五科能力雷達圖 (Radar Chart)**")
        st.caption("呈現個人與班級、全校平均在 7 級分制下的均衡度。")
        radar_stu = [student_mock["subjects"][s]["points"] for s in subj_list]
        radar_cls = [student_mock["subjects"][s]["class_avg_points"] for s in subj_list]
        radar_sch = [student_mock["subjects"][s]["school_avg_points"] for s in subj_list]
        fig_radar = create_mock_radar_chart(subj_list, radar_stu, radar_cls, radar_sch)
        st.plotly_chart(fig_radar, use_container_width=True)

    with c_chart2:
        st.markdown("**📊 科目積分對比長條圖 (Subject Points Comparison)**")
        st.caption("直觀比較個人各科積分與班級、校平均的落點高度。")
        subj_details = [
            {
                'subject': s,
                'points': student_mock["subjects"][s]["points"],
                'class_avg_points': student_mock["subjects"][s]["class_avg_points"],
                'school_avg_points': student_mock["subjects"][s]["school_avg_points"],
                'diff_from_class': student_mock["subjects"][s]["diff_from_class"],
                'diff_from_school': student_mock["subjects"][s]["diff_from_school"],
            } for s in subj_list
        ]
        fig_bars = create_mock_subject_bars(subj_details, metric='points')
        st.plotly_chart(fig_bars, use_container_width=True)

    st.markdown("---")

    # Score Distribution Curve
    points_dist = benchmarks.get("points_distribution", [])
    if points_dist:
        st.markdown("**🎯 五科總積分全校 / 全區累積百分比曲線 (Percentile Position)**")
        st.caption("曲線代表各積分門檻在全校與全區的累積前 %（數值越低代表落點越靠前）。")
        fig_dist = create_mock_points_distribution_chart(points_dist, student_points=tot_pts)
        st.plotly_chart(fig_dist, use_container_width=True)


def _render_student_diagnostics(student_mock: Dict[str, Any], benchmarks: Dict[str, Any]):
    """Tab 2: Actionable Strengths/Weaknesses, Promotion Gaps, and Item-by-Item Breakdown."""
    st.markdown("### 💡 學習表現與晉級診斷 (Learning Diagnostics)")

    diag = student_mock.get("diagnosis", {})
    strengths = diag.get("relative_strengths", [])
    opportunities = diag.get("promotion_opportunities", [])
    priorities = diag.get("priority_review", [])

    d1, d2, d3 = st.columns(3)
    with d1:
        st.success("🌟 **相對表現較佳科目**")
        if strengths:
            for s in strengths:
                pts = student_mock["subjects"][s]["points"]
                lvl = student_mock["subjects"][s]["sub_level"]
                st.markdown(f"- **{s}**: {lvl} ({pts:g} 分)")
        else:
            st.markdown("- 各科表現相對均衡。")

    with d2:
        st.info("🚀 **最佳晉級突破機會**")
        if opportunities:
            for op in opportunities:
                st.markdown(f"- **{op}**")
            st.caption("💡 這些科目只需再多對 1~2 題或提高非選分數，就能立即晉升下一標示等級，投資報酬率最高！")
        else:
            st.markdown("- 目前各科已在穩定區間。")

    with d3:
        st.warning("⚠️ **建議優先加強科目**")
        if priorities:
            for p in priorities:
                pts = student_mock["subjects"][p]["points"]
                lvl = student_mock["subjects"][p]["sub_level"]
                st.markdown(f"- **{p}**: {lvl} ({pts:g} 分)")
        else:
            st.markdown("- 無明顯落後班級平均之科目。")

    st.markdown("---")

    # Missed Questions Tracking
    st.markdown("### 📑 錯題知識點與作答追蹤 (Question-by-Question Breakdown)")
    st.markdown("選擇想深入檢視的科目，系統將列出您在本次模擬考答錯或未得分的題目、知識點與評量目標：")

    chosen_subj = st.selectbox("選擇科目 (Select Subject)", ['國文', '數學', '英語', '社會', '自然'], key="diag_subj_select")
    subj_data = student_mock.get("subjects", {}).get(chosen_subj, {})
    missed_items = subj_data.get("incorrect_items", [])

    if not missed_items:
        st.balloons()
        st.success(f"🎉 太厲害了！本次模擬考在 **{chosen_subj}** 科目全部答對，無任何錯題記錄！")
    else:
        st.markdown(f"**本次 {chosen_subj} 共錯 {len(missed_items)} 題，錯題明細如下：**")
        q_rows = []
        for item in missed_items:
            sec_str = f"[{item.get('section')}] " if item.get('section') else ""
            c_rate = item.get('class_correct_rate', 0.0)
            s_rate = item.get('school_correct_rate', 0.0)

            diff_str = f"{c_rate - s_rate:+.1f}%" if s_rate > 0 else "-"

            q_rows.append({
                '題號': f"{sec_str}第 {item.get('q_num')} 題",
                '領域/學習內容': item.get('domain', '-'),
                '知識點主題': item.get('topic', '-'),
                '評量目標': item.get('goal', '-'),
                '您的選答': item.get('student_choice', '-'),
                '正確答案': item.get('correct_answer', '-'),
                '班級答對率': f"{c_rate:.1f}%" if c_rate > 0 else "-",
                '全校答對率': f"{s_rate:.1f}%" if s_rate > 0 else "-"
            })

        df_q = pd.DataFrame(q_rows)
        st.dataframe(df_q, use_container_width=True, hide_index=True)


def _render_regular_vs_mock_comparison(
    exam_bundle: Dict[str, Any],
    student_mock: Dict[str, Any],
    regular_df: pd.DataFrame,
    student_regular_data: pd.DataFrame,
    col_info: pd.DataFrame,
    exclude_stats: List[str]
):
    """Tab 3: Statistical comparison between Regular Exams and Mock Exam."""
    st.markdown("### ⚖️ 平常段考 vs 模擬考 綜合對比分析")

    st.markdown("""
    > [!NOTE]
    > **為何不能直接用原始分數比大小？**
    > * **平常段考（定期評量）：** 滿分 100 分，評量範圍為學校單一階段進度（約 2~3 個單元），著重當前單元的精熟度。
    > * **教育會考模擬考：** 採用教育部會考 3 等級 7 標示（A++ 到 C），評量範圍為多冊大範圍綜合評量（如第 1~2 冊），著重長期記憶與跨單元素養整合。
    > * **客觀比較方法：** 採用「相對全班百分比 (Percentile Rank)」與「標準化分數 (Z-score)」進行公平對比。
    """)

    comp = compare_mock_with_regular(
        exam_bundle, student_mock, regular_df, student_regular_data, col_info, exclude_stats
    )

    if not comp.get('has_data'):
        st.info("尚無足夠的定期評量資料可供進行交叉對比。")
        return

    latest_exam = comp.get('latest_regular_exam')
    r_cpct = comp.get('regular_class_pct')
    m_cpct = comp.get('mock_class_pct')
    r_spct = comp.get('regular_school_pct')
    m_spct = comp.get('mock_school_pct')

    st.markdown(f"**對比基準：最近一次段考【{latest_exam}】 vs 本次模擬考**")

    # Row 1: Class rank comparison (responsive 2x2)
    m1, m2 = st.columns(2)
    m1.metric(f"{latest_exam} 班排", f"Top {r_cpct:.1f}%" if pd.notna(r_cpct) else "-")
    m2.metric("本次模擬考 班排", f"Top {m_cpct:.1f}%" if pd.notna(m_cpct) else "-",
              delta=f"{r_cpct - m_cpct:+.1f}% (排名提升)" if (pd.notna(r_cpct) and pd.notna(m_cpct) and (r_cpct - m_cpct) > 0) else None)

    # Row 2: School rank comparison
    m3, m4 = st.columns(2)
    m3.metric(f"{latest_exam} 校排", f"Top {r_spct:.1f}%" if pd.notna(r_spct) else "-")
    m4.metric("本次模擬考 校排", f"Top {m_spct:.1f}%" if pd.notna(m_spct) else "-",
              delta=f"{r_spct - m_spct:+.1f}% (排名提升)" if (pd.notna(r_spct) and pd.notna(m_spct) and (r_spct - m_spct) > 0) else None)

    st.markdown("---")

    # Subject comparison table
    st.markdown("#### 📚 各科目大範圍適應度分析 (Subject Consistency)")
    subj_comp = comp.get('subject_comparison', [])
    if subj_comp:
        rows = []
        for sc in subj_comp:
            reg_score_str = f"{sc['regular_score']:g} 分" if pd.notna(sc['regular_score']) else "-"
            reg_z_str = f"Z={sc['regular_z']:+.2f}" if pd.notna(sc['regular_z']) else "-"
            mock_level_str = f"{sc['mock_level']} ({sc['mock_points']:g}分)" if sc['mock_points'] is not None else "-"
            diff_cls_str = f"{sc['mock_diff_class']:+.2f} 分"

            rows.append({
                '科目': sc['subject'],
                f'{latest_exam} 平常段考': f"{reg_score_str} ({reg_z_str})",
                '本次模擬考會考標示': mock_level_str,
                '模擬考領先/落後班平均': diff_cls_str,
                '表現類型與學習特質': sc['status']
            })

        df_sc = pd.DataFrame(rows)

        def style_status(val):
            if val == '平穩優勢': return 'color: #27ae60; font-weight: bold;'
            if val == '模擬考突出': return 'color: #2980b9; font-weight: bold;'
            if val == '段考優於模考': return 'color: #e67e22;'
            if val == '需共同加強': return 'color: #e74c3c; font-weight: bold;'
            return ''

        styled_sc = df_sc.style.map(style_status, subset=['表現類型與學習特質'])
        st.dataframe(styled_sc, use_container_width=True, hide_index=True)

        st.caption("""
        📌 **學習特質說明：**
        - **平穩優勢：** 無論段考或模擬考大範圍皆名列前茅，實力非常穩固。
        - **模擬考突出：** 平常段考普通，但跨冊綜合素養與解題靈活性高，大考潛力強。
        - **段考優於模考：** 平常認真準備進度表現極佳，但面對大範圍題型時容易遺忘先前冊數，建議加強定期跨單元回溯複習。
        - **需共同加強：** 需回歸核心基礎概念，優先掌握 B 等級基本試題。
        """)


def _render_historical_mock_trends(available_mocks: List[Dict[str, Any]], student_mock: Dict[str, Any]):
    """Tab 4: Multi-round Mock Exam Trend Tracker (Mock 1 -> Mock 2 -> Mock 3 -> Mock 4)."""
    st.markdown("### 📈 歷次模擬考成績趨勢 (Historical Mock Exam Trends)")

    if len(available_mocks) <= 1:
        st.info("ℹ️ 目前系統中已有【第一次模擬考】資料。當後續匯入【第二次模擬考】、【第三次模擬考】、【第四次模擬考】時，此處將自動繪製全五科跨次進退步曲線與會考積分推估軌跡。")
        st.markdown("""
        **未來將呈現之追蹤指標：**
        * 第一次模考（1~2冊） ➔ 第二次模考（1~3冊） ➔ 第三次模考（1~4冊） ➔ 第四次模考（1~5冊）
        * 各科能力等級演變（如 B+ ➔ B++ ➔ A）
        * 總積分成長趨勢
        * 全校與全區排名百分比推進軌跡
        """)
        return

    # If multiple mocks exist
    trend_rows = []
    auth_sid = student_mock.get("student_id")
    stu_name = student_mock.get("name")

    for ex in available_mocks:
        ex_bundle = load_mock_exam(ex['exam_id'])
        if ex_bundle:
            s_data = get_student_mock_data(ex_bundle, student_id=auth_sid, student_name=stu_name)
            if s_data:
                trend_rows.append({
                    'Exam': ex['exam_label'],
                    'Total_Points': s_data.get('total_points', 0.0),
                    'Combo': s_data.get('level_combo', '-'),
                    'Class_Rank': s_data.get('rankings', {}).get('class_rank'),
                    'School_Rank': s_data.get('rankings', {}).get('school_rank'),
                    '國文': s_data.get('subjects', {}).get('國文', {}).get('sub_level', '-'),
                    '英語': s_data.get('subjects', {}).get('英語', {}).get('sub_level', '-'),
                    '數學': s_data.get('subjects', {}).get('數學', {}).get('sub_level', '-'),
                    '社會': s_data.get('subjects', {}).get('社會', {}).get('sub_level', '-'),
                    '自然': s_data.get('subjects', {}).get('自然', {}).get('sub_level', '-'),
                })

    if trend_rows:
        df_tr = pd.DataFrame(trend_rows)
        import plotly.express as px
        fig_tr = px.line(df_tr, x='Exam', y='Total_Points', markers=True, title="歷次模擬考總積分變化軌跡")
        fig_tr.update_layout(
            font=dict(family="sans-serif", size=13),
            margin=dict(l=35, r=35, t=50, b=40),
            yaxis_title="五科總積分 (Points)",
            xaxis_title="模擬考試次"
        )
        st.plotly_chart(fig_tr, use_container_width=True)

        st.markdown("#### 📋 歷次各科能力標示演變 (Subject Grade Evolution)")
        df_display = pd.DataFrame([
            {
                '模擬考試次': r['Exam'],
                '總積分': f"{r['Total_Points']:g} 分",
                '標示組合': r['Combo'],
                '班排': f"第 {r['Class_Rank']} 名" if r['Class_Rank'] else "-",
                '校排': f"第 {r['School_Rank']} 名" if r['School_Rank'] else "-",
                '國文': r['國文'],
                '英語': r['英語'],
                '數學': r['數學'],
                '社會': r['社會'],
                '自然': r['自然'],
            } for r in trend_rows
        ])
        st.dataframe(df_display, use_container_width=True, hide_index=True)


def _render_virtual_mock_overview(exam_bundle: Dict[str, Any]):
    """Renders class overview mode (when logged in as demo or viewing cohort stats)."""
    benchmarks = exam_bundle.get("benchmarks", {})
    cohort = exam_bundle.get("metadata", {}).get("cohort", {})

    st.markdown("### 🏫 班級模擬考常模與表現指標 (Class Overview)")

    averages = benchmarks.get("averages", {})
    tot_avg = averages.get("五科總積分", {})
    # Row 1: Score comparisons
    v1, v2 = st.columns(2)
    v1.metric("班級五科總積分平均", f"{tot_avg.get('class_mean', 0):.2f} 分",
              delta=f"{tot_avg.get('class_mean', 0) - tot_avg.get('school_mean', 0):+.2f} 分 (vs 校平均)")
    v2.metric("全校五科總積分平均", f"{tot_avg.get('school_mean', 0):.2f} 分")

    # Row 2: Rank & Participants
    v3, v4 = st.columns(2)
    v3.metric("本班在全校排名", f"第 {tot_avg.get('class_rank_in_school', '-')} 名 / 共 19 班")
    v4.metric("全班受測人數", f"{cohort.get('class_students', 27)} 人")

    st.markdown("---")

    # Radar & Bars
    subj_list = ['國文', '數學', '英語', '社會', '自然']
    cls_pts = [averages.get(s, {}).get('class_points', 0.0) for s in subj_list]
    sch_pts = [averages.get(s, {}).get('school_points', 0.0) for s in subj_list]

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🕸️ 班級平均 vs 全校平均 能力雷達圖**")
        fig_rad = create_mock_radar_chart(subj_list, None, cls_pts, sch_pts)
        st.plotly_chart(fig_rad, use_container_width=True)

    with c2:
        st.markdown("**📊 各科能力等級分布 (A/B/C 三層級)**")
        from core.mock_charts import create_subject_tiers_chart
        fig_tiers = create_subject_tiers_chart(benchmarks.get("subject_tiers", {}))
        st.plotly_chart(fig_tiers, use_container_width=True)

    st.markdown("---")
    # Combo Distribution
    st.markdown("**🏆 全班 vs 全校 五科標示組合分布**")
    from core.mock_charts import create_cohort_combos_chart
    fig_combos = create_cohort_combos_chart(benchmarks.get("level_combos", {}))
    st.plotly_chart(fig_combos, use_container_width=True)
