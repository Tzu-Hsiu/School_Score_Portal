import streamlit as st
import pandas as pd
import numpy as np
from core.charts import create_radar_chart, create_box_plot, create_grouped_bar_chart, create_distribution_chart
from core.constants import DEFAULT_SCHOOL_TOTAL_STUDENTS, SCORE_BINS, SCORE_BIN_LABELS
from reports.html_generator import generate_html_reports

def render(df, col_info, available_exams, exclude_stats, is_virtual, student_data, student_name):
    if is_virtual:
        st.success("歡迎進入 🏫 班級總覽模式 (Class Overview Mode)！")
    else:
        st.success(f"歡迎, {student_name} 的家長！")
        
    st.subheader("📌 選擇想查看的考試 (Select Exam)")
    selected_exam = _render_exam_selector(available_exams)
    exam_all_cols = col_info[col_info['Exam_Label'] == selected_exam]
    
    if exam_all_cols.empty:
        st.warning("此考試尚未有成績資料 (No data available).")
        return

    if not is_virtual:
        with st.expander("🖨️ 下載個人專屬成績單 (Download Personal Report)"):
            st.markdown("選擇想附上的圖表，系統將為您生成專屬成績單，下載後雙擊即可用瀏覽器開啟或列印！")
            dl_chart_options = st.multiselect(
                "選擇要在成績單上顯示的圖表 (Chart Options)", 
                ["箱形圖 (Box Plot)", "長條對比圖 (Bar Chart)", "分布長條圖 (Distribution Chart)", "雷達圖 (Radar Chart)"], 
                default=["雷達圖 (Radar Chart)", "長條對比圖 (Bar Chart)", "箱形圖 (Box Plot)"],
                key="student_chart_download"
            )
            html_report = generate_html_reports(selected_exam, student_data, df, col_info, exclude_stats, dl_chart_options)
            st.download_button(
                label="📥 點擊下載成績報告 (HTML)", 
                data=html_report, 
                file_name=f"{selected_exam}_個人成績單_{student_name}.html", 
                mime="text/html"
            )

    tab1, tab2, tab3 = st.tabs(["📊 學習總覽 (Overview)", "🔬 深度數據分析 (Deep Analytics)", "📈 歷年趨勢 (Historical Trend)"])
    
    stats_df, box_x, box_y, stu_x, stu_y, dist_dict = _compute_exam_stats(df, exam_all_cols, exclude_stats, student_data, is_virtual)
    
    with tab1:
        st.markdown("### 🏆 本次考試表現 (Exam Summary)")
        _render_kpi_cards(df, col_info, available_exams, selected_exam, exam_all_cols, student_data, is_virtual)
        st.markdown("---")
        _render_overview_charts(stats_df, box_x, box_y, stu_x, stu_y, dist_dict, is_virtual)

    with tab2:
        _render_deep_analytics(stats_df, is_virtual, selected_exam)

    with tab3:
        _render_historical_trend(df, col_info, available_exams, student_data, is_virtual)


def _render_exam_selector(available_exams):
    return st.selectbox("Exam", available_exams, label_visibility="collapsed")


def _compute_exam_stats(df, exam_all_cols, exclude_stats, student_data, is_virtual):
    exam_subj_cols = exam_all_cols[~exam_all_cols['Subject'].isin(exclude_stats)]
    stats_list = []
    dist_dict = {}
    box_x, box_y, stu_x, stu_y = [], [], [], []
    
    for _, row in exam_subj_cols.iterrows():
        subj = row['Subject']          
        col_name = row['Original_Col'] 
        class_scores = df[col_name].dropna()
        
        if class_scores.empty:
            continue
            
        box_x.extend([subj] * len(class_scores))
        box_y.extend(class_scores.tolist())
        dist_dict[subj] = pd.cut(class_scores, bins=SCORE_BINS, labels=SCORE_BIN_LABELS).value_counts().reindex(SCORE_BIN_LABELS, fill_value=0).tolist()
        
        mean_val = class_scores.mean()
        std_dev = class_scores.std()
        adj_scores = class_scores[class_scores > 0]
        adj_mean = adj_scores.mean() if not adj_scores.empty else np.nan
        
        stat_dict = {
            '科目 (Subject)': subj, '班級平均 (Class Avg)': round(mean_val, 1), 
            '排除0分平均 (Adj Avg)': round(adj_mean, 1) if pd.notna(adj_mean) else np.nan,
            '班級最高 (Max)': class_scores.max(), '班級最低 (Min)': class_scores.min(), 
            '中位數 (Median)': round(class_scores.median(), 1), 
            '標準差 (SD)': round(std_dev, 1) if pd.notna(std_dev) else 0.0
        }
        
        if is_virtual:
            n_students = len(class_scores)
            sorted_scores = class_scores.sort_values(ascending=False).values
            top_30_idx = max(1, int(n_students * 0.3))
            bottom_30_idx = max(1, int(n_students * 0.3))
            
            top_30_avg = sorted_scores[:top_30_idx].mean() if top_30_idx > 0 else np.nan
            bottom_30_avg = sorted_scores[-bottom_30_idx:].mean() if bottom_30_idx > 0 else np.nan
            mid_40_avg = sorted_scores[top_30_idx:-bottom_30_idx].mean() if (n_students - top_30_idx - bottom_30_idx) > 0 else np.nan
            
            stat_dict['前 30% 平均 (Top 30%)'] = round(top_30_avg, 1) if pd.notna(top_30_avg) else np.nan
            stat_dict['中 40% 平均 (Mid 40%)'] = round(mid_40_avg, 1) if pd.notna(mid_40_avg) else np.nan
            stat_dict['後 30% 平均 (Bot 30%)'] = round(bottom_30_avg, 1) if pd.notna(bottom_30_avg) else np.nan
        
        
        if not is_virtual and not student_data.empty:
            student_score = student_data[col_name].iloc[0]
            if pd.notna(student_score):
                stu_x.append(subj)
                stu_y.append(student_score)
                stat_dict['學生分數 (Score)'] = student_score
                stat_dict['Z分數 (Z-Score)'] = round((student_score - mean_val) / std_dev, 2) if std_dev and std_dev > 0 else 0
                stat_dict['百分等級 (PR)'] = round((class_scores <= student_score).mean() * 100, 1)
        stats_list.append(stat_dict)
    
    return pd.DataFrame(stats_list), box_x, box_y, stu_x, stu_y, dist_dict


def _render_kpi_cards(df, col_info, available_exams, selected_exam, exam_all_cols, student_data, is_virtual):
    kpi_cols = st.columns(4)
    try:
        curr_idx = available_exams.index(selected_exam)
        prev_exam_label = available_exams[curr_idx - 1] if curr_idx > 0 else None
    except ValueError:
        prev_exam_label = None
        
    prev_exam_cols = pd.DataFrame()
    if prev_exam_label:
        prev_exam_cols = col_info[col_info['Exam_Label'] == prev_exam_label]
    
    def get_class_metric(subject_name):
        try: return df[exam_all_cols[exam_all_cols['Subject'] == subject_name]['Original_Col'].values[0]].dropna()
        except IndexError: return pd.Series(dtype=float)
    
    tot_scores, avg_scores = get_class_metric('總分'), get_class_metric('平均')
    
    if is_virtual:
        kpi_cols[0].metric("班級平均總分", f"{tot_scores.mean():.1f}" if not tot_scores.empty else "-")
        kpi_cols[1].metric("班級最高總分", f"{tot_scores.max():g}" if not tot_scores.empty else "-")
        kpi_cols[2].metric("班級總平均", f"{avg_scores.mean():.1f}" if not avg_scores.empty else "-")
        kpi_cols[3].metric("考試人數", f"{len(tot_scores)}" if not tot_scores.empty else "-")
    else:
        def get_metric_with_prev(subject_name):
            curr_val, prev_val, count = np.nan, np.nan, 0
            try:
                c_name = exam_all_cols[exam_all_cols['Subject'] == subject_name]['Original_Col'].values[0]
                curr_val = student_data[c_name].iloc[0]
                count = df[c_name].count()
            except IndexError: pass
            if prev_exam_label and not prev_exam_cols.empty:
                try:
                    p_name = prev_exam_cols[prev_exam_cols['Subject'] == subject_name]['Original_Col'].values[0]
                    prev_val = student_data[p_name].iloc[0]
                except IndexError: pass
            return curr_val, prev_val, count

        tot_score, p_tot, _ = get_metric_with_prev('總分')
        avg_score, p_avg, _ = get_metric_with_prev('平均')
        c_rank, p_crank, c_total = get_metric_with_prev('班排')
        s_rank, p_srank, _ = get_metric_with_prev('校排') 
        
        tot_delta = tot_score - p_tot if pd.notna(tot_score) and pd.notna(p_tot) else None
        avg_delta = avg_score - p_avg if pd.notna(avg_score) and pd.notna(p_avg) else None
        crank_delta = p_crank - c_rank if pd.notna(c_rank) and pd.notna(p_crank) else None
        srank_delta = p_srank - s_rank if pd.notna(s_rank) and pd.notna(p_srank) else None

        school_total = st.secrets.get("school", {}).get("total_students", DEFAULT_SCHOOL_TOTAL_STUDENTS)

        c_pct_str = f"(Top {(c_rank / c_total) * 100:.1f}%)" if pd.notna(c_rank) and c_total > 0 else ""
        s_pct_str = f"(Top {(s_rank / school_total) * 100:.1f}%)" if pd.notna(s_rank) else ""

        kpi_cols[0].metric("總分 (Total)", f"{tot_score:g}" if pd.notna(tot_score) else "-", delta=f"{tot_delta:g} 分" if tot_delta is not None else None)
        kpi_cols[1].metric("平均 (Average)", f"{avg_score:g}" if pd.notna(avg_score) else "-", delta=f"{avg_delta:g} 分" if avg_delta is not None else None)
        
        with kpi_cols[2]:
            st.metric("班級排名 (Class Rank)", f"{int(c_rank)} / {c_total}" if pd.notna(c_rank) else "-", delta=f"{int(crank_delta)} 名" if crank_delta is not None else None)
            if c_pct_str:
                st.markdown(f"<div style='color: #7f8c8d; font-size: 0.9em; margin-top: -10px;'>{c_pct_str}</div>", unsafe_allow_html=True)
        
        with kpi_cols[3]:
            st.metric("校排 (School Rank)", f"{int(s_rank)} / {school_total}" if pd.notna(s_rank) else "-", delta=f"{int(srank_delta)} 名" if srank_delta is not None else None)
            if s_pct_str:
                st.markdown(f"<div style='color: #7f8c8d; font-size: 0.9em; margin-top: -10px;'>{s_pct_str}</div>", unsafe_allow_html=True)


def _render_overview_charts(stats_df, box_x, box_y, stu_x, stu_y, dist_dict, is_virtual):
    if stats_df.empty:
        return
        
    has_student_scores = '學生分數 (Score)' in stats_df.columns and stats_df['學生分數 (Score)'].notna().any()
    show_class_only = is_virtual or not has_student_scores
    
    col_chart1, col_chart2 = st.columns([3, 2])
    with col_chart1:
        st.write("**📊 班級各科平均表現**" if show_class_only else "**📊 成績對比圖 (Grouped Bar)**")
        fig_bar = create_grouped_bar_chart(stats_df, is_virtual)
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with col_chart2:
        st.write("**🕸️ 班級能力雷達圖**" if show_class_only else "**🕸️ 能力雷達圖 (Radar Chart)**")
        subjects = stats_df['科目 (Subject)'].tolist()
        class_avgs = stats_df['班級平均 (Class Avg)'].tolist()
        student_scores = stats_df['學生分數 (Score)'].tolist() if '學生分數 (Score)' in stats_df.columns else None
        fig_radar = create_radar_chart(subjects, student_scores, class_avgs)
        st.plotly_chart(fig_radar, use_container_width=True)

    st.markdown("---")
    st.write("**📦 全班成績分布與個人表現對比 (Box Plot)**" if not is_virtual else "**📦 全班各科成績分布 (Box Plot)**")
    
    student_scores_box = stu_y if not is_virtual and stu_x else None
    student_subjects_box = stu_x if not is_virtual and stu_x else None
    fig_box = create_box_plot(box_x, box_y, student_subjects_box, student_scores_box)
    st.plotly_chart(fig_box, use_container_width=True)

    st.markdown("---")
    st.write("**👥 班級各科成績區間分布人數 (Score Distribution)**")
    if dist_dict:
        dist_df = pd.DataFrame(dist_dict, index=SCORE_BIN_LABELS)
        st.dataframe(dist_df, use_container_width=True)
        
        fig_dist = create_distribution_chart(dist_dict, list(dist_dict.keys()))
        st.plotly_chart(fig_dist, use_container_width=True)


def _render_deep_analytics(stats_df, is_virtual, selected_exam):
    st.subheader(f"{selected_exam} - 深度數據分析 (Deep Statistical Breakdown)")
    st.markdown("* **排除0分平均:** 扣除缺考(0分)同學後的實際班級平均，更能反映真實難度。")
    if not stats_df.empty:
        has_student_metrics = (
            not is_virtual
            and '學生分數 (Score)' in stats_df.columns
            and stats_df['學生分數 (Score)'].notna().any()
        )
        if has_student_metrics:
            st.markdown("* **Z分數 (Z-Score):** 大於 0 代表高於平均，大於 1 代表在班上屬於前段班。\n* **百分等級 (PR):** PR85 代表該生成績贏過班上 85% 的同學。")
            def highlight_z(x):
                if pd.isna(x): return ''
                try:
                    f = float(x)
                    if f > 0: return 'color: green'
                    if f < 0: return 'color: red'
                except: pass
                return ''
            st.dataframe(stats_df.style.map(highlight_z, subset=['Z分數 (Z-Score)']), use_container_width=True, hide_index=True)
        else:
            if is_virtual:
                cols_to_show = ['科目 (Subject)', '班級平均 (Class Avg)', '排除0分平均 (Adj Avg)', '前 30% 平均 (Top 30%)', '中 40% 平均 (Mid 40%)', '後 30% 平均 (Bot 30%)', '班級最高 (Max)', '班級最低 (Min)', '中位數 (Median)', '標準差 (SD)']
                st.dataframe(stats_df[cols_to_show], use_container_width=True, hide_index=True)
            else:
                st.dataframe(stats_df[['科目 (Subject)', '班級平均 (Class Avg)', '排除0分平均 (Adj Avg)', '班級最高 (Max)', '班級最低 (Min)', '中位數 (Median)', '標準差 (SD)']], use_container_width=True, hide_index=True)


def _render_historical_trend(df, col_info, available_exams, student_data, is_virtual):
    st.subheader("📈 歷年表現趨勢圖 (Historical Performance Trend)")
    all_trackable = col_info['Subject'].unique().tolist()
    
    if is_virtual:
        st.markdown("請選擇要查看的指標，系統將繪製歷年 **班級平均** 趨勢。")
    else:
        st.markdown("請選擇要查看的指標，系統將自動同時繪製 **個人表現** 與 **班級平均** 進行對比。")
        
    selected_metric = st.selectbox("選擇追蹤指標 (Select Metric)", all_trackable)
    trend_data = []
    
    for ex in available_exams:
        ex_cols = col_info[col_info['Exam_Label'] == ex]
        c_name_array = ex_cols[ex_cols['Subject'] == selected_metric]['Original_Col'].values
        
        if len(c_name_array) > 0:
            col = c_name_array[0]
            
            if col in df.columns:
                col_vals = df[col].dropna()
                class_avg = col_vals.mean() if not col_vals.empty else np.nan
                
                if is_virtual and not col_vals.empty:
                    n_students = len(col_vals)
                    sorted_scores = col_vals.sort_values(ascending=False).values
                    top_30_idx = max(1, int(n_students * 0.3))
                    bottom_30_idx = max(1, int(n_students * 0.3))
                    
                    top_30_avg = sorted_scores[:top_30_idx].mean() if top_30_idx > 0 else np.nan
                    bottom_30_avg = sorted_scores[-bottom_30_idx:].mean() if bottom_30_idx > 0 else np.nan
                    mid_40_avg = sorted_scores[top_30_idx:-bottom_30_idx].mean() if (n_students - top_30_idx - bottom_30_idx) > 0 else np.nan
                else:
                    top_30_avg, mid_40_avg, bottom_30_avg = np.nan, np.nan, np.nan
            else:
                class_avg = np.nan
                top_30_avg, mid_40_avg, bottom_30_avg = np.nan, np.nan, np.nan
                
            if not is_virtual and col in student_data.columns:
                student_score = student_data[col].iloc[0]
            else:
                student_score = np.nan
            
            if is_virtual:
                if pd.notna(class_avg):
                    trend_data.append({"Exam": ex, "Type": "班級平均 (Class Avg)", "Value": class_avg})
                if pd.notna(top_30_avg):
                    trend_data.append({"Exam": ex, "Type": "前 30% 平均 (Top 30%)", "Value": top_30_avg})
                if pd.notna(mid_40_avg):
                    trend_data.append({"Exam": ex, "Type": "中 40% 平均 (Mid 40%)", "Value": mid_40_avg})
                if pd.notna(bottom_30_avg):
                    trend_data.append({"Exam": ex, "Type": "後 30% 平均 (Bot 30%)", "Value": bottom_30_avg})
            else:
                if pd.notna(student_score):
                    trend_data.append({"Exam": ex, "Type": "個人表現 (Student)", "Value": student_score})
                if pd.notna(class_avg) and selected_metric not in ['班排', '校排']:
                    trend_data.append({"Exam": ex, "Type": "班級平均 (Class Avg)", "Value": class_avg})

    if trend_data:
        import plotly.express as px
        trend_df = pd.DataFrame(trend_data)
        
        if is_virtual:
            color_map = {
                "班級平均 (Class Avg)": "#636EFA", # Blue
                "前 30% 平均 (Top 30%)": "#00CC96", # Green
                "中 40% 平均 (Mid 40%)": "#FFA15A", # Orange
                "後 30% 平均 (Bot 30%)": "#EF553B"  # Red
            }
        else:
            color_map = {"個人表現 (Student)": "#FF4B4B", "班級平均 (Class Avg)": "#636EFA"}
        fig_trend = px.line(
            trend_df, x="Exam", y="Value", color="Type", markers=True,
            title=f"{selected_metric} - 歷年趨勢", color_discrete_map=color_map
        )
        fig_trend.update_traces(
            mode='lines+markers+text', texttemplate='%{y:.1f}', textposition='top center',
            hovertemplate='考試: %{x}<br>%{fullData.name}: %{y:.1f}<extra></extra>'
        )
        fig_trend.update_layout(
            xaxis_title="考試 (Exam)", yaxis_title="分數 / 排名 (Score / Rank)", 
            margin=dict(l=0, r=0, t=40, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None)
        )
        if selected_metric in ['班排', '校排']:
             fig_trend.update_yaxes(autorange="reversed")
        for trace in fig_trend.data:
            if '班級平均' in trace.name:
                trace.line.dash = 'dash'
                
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("尚無足夠的歷史資料可供呈現趨勢。")
