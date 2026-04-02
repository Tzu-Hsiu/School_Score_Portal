import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from reports.html_generator import generate_html_reports

def render(df, col_info, available_exams, exclude_stats, is_virtual, student_data, student_name):
    if is_virtual:
        st.success("歡迎進入 🏫 班級總覽模式 (Class Overview Mode)！")
    else:
        st.success(f"歡迎, {student_name} 的家長！")
        
    st.subheader("📌 選擇想查看的考試 (Select Exam)")
    selected_exam = st.selectbox("Exam", available_exams, label_visibility="collapsed")
    exam_all_cols = col_info[col_info['Exam_Label'] == selected_exam]
    
    if exam_all_cols.empty:
        st.warning("此考試尚未有成績資料 (No data available).")
        return

    # --- 學生個人的 HTML 專屬成績單下載區塊 ---
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
    
    with tab1:
        st.markdown("### 🏆 本次考試表現 (Exam Summary)")
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

            # 依照 "排名越小越好" 進行 Top 百分比計算
            c_pct_str = f"(Top {(c_rank / c_total) * 100:.1f}%)" if pd.notna(c_rank) and c_total > 0 else ""
            s_pct_str = f"(Top {(s_rank / 520) * 100:.1f}%)" if pd.notna(s_rank) else ""

            kpi_cols[0].metric(
                "總分 (Total)", 
                f"{tot_score:g}" if pd.notna(tot_score) else "-", 
                delta=f"{tot_delta:g} 分" if tot_delta is not None else None
            )
            kpi_cols[1].metric(
                "平均 (Average)", 
                f"{avg_score:g}" if pd.notna(avg_score) else "-", 
                delta=f"{avg_delta:g} 分" if avg_delta is not None else None
            )
            
            with kpi_cols[2]:
                st.metric(
                    "班級排名 (Class Rank)", 
                    f"{int(c_rank)} / {c_total}" if pd.notna(c_rank) else "-", 
                    delta=f"{int(crank_delta)} 名" if crank_delta is not None else None
                )
                if c_pct_str:
                    st.markdown(f"<div style='color: #7f8c8d; font-size: 0.9em; margin-top: -10px;'>{c_pct_str}</div>", unsafe_allow_html=True)
            
            with kpi_cols[3]:
                st.metric(
                    "校排 (School Rank)", 
                    f"{int(s_rank)} / 520" if pd.notna(s_rank) else "-", 
                    delta=f"{int(srank_delta)} 名" if srank_delta is not None else None
                )
                if s_pct_str:
                    st.markdown(f"<div style='color: #7f8c8d; font-size: 0.9em; margin-top: -10px;'>{s_pct_str}</div>", unsafe_allow_html=True)
        
        st.markdown("---")

        exam_subj_cols = exam_all_cols[~exam_all_cols['Subject'].isin(exclude_stats)]
        stats_list = []
        bins, labels = [-1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100], ['0-10', '11-20', '21-30', '31-40', '41-50', '51-60', '61-70', '71-80', '81-90', '91-100']
        dist_dict = {}
        
        box_x, box_y, stu_x, stu_y = [], [], [], []
        
        for index, row in exam_subj_cols.iterrows():
            subj = row['Subject']          
            col_name = row['Original_Col'] 
            class_scores = df[col_name].dropna()
            
            box_x.extend([subj] * len(class_scores))
            box_y.extend(class_scores.tolist())
            dist_dict[subj] = pd.cut(class_scores, bins=bins, labels=labels).value_counts().reindex(labels, fill_value=0)
            mean_val, std_dev, adj_mean = class_scores.mean(), class_scores.std(), class_scores[class_scores > 0].mean()
            
            stat_dict = {
                '科目 (Subject)': subj, '班級平均 (Class Avg)': round(mean_val, 1), '排除0分平均 (Adj Avg)': round(adj_mean, 1) if pd.notna(adj_mean) else np.nan,
                '班級最高 (Max)': class_scores.max(), '班級最低 (Min)': class_scores.min(), '中位數 (Median)': round(class_scores.median(), 1), '標準差 (SD)': round(std_dev, 1) if pd.notna(std_dev) else 0.0
            }
            
            if not is_virtual:
                student_score = student_data[col_name].iloc[0]
                if pd.notna(student_score):
                    stu_x.append(subj)
                    stu_y.append(student_score)
                    stat_dict['學生分數 (Score)'] = student_score
                    stat_dict['Z分數 (Z-Score)'] = round((student_score - mean_val) / std_dev, 2) if std_dev and std_dev > 0 else 0
                    stat_dict['百分等級 (PR)'] = round((class_scores <= student_score).mean() * 100, 1)
            stats_list.append(stat_dict)
        
        stats_df = pd.DataFrame(stats_list)
        
        if not stats_df.empty:
            has_student_scores = '學生分數 (Score)' in stats_df.columns and stats_df['學生分數 (Score)'].notna().any()
            col_chart1, col_chart2 = st.columns([3, 2])
            with col_chart1:
                show_class_only = is_virtual or not has_student_scores
                st.write("**📊 班級各科平均表現**" if show_class_only else "**📊 成績對比圖 (Grouped Bar)**")
                if show_class_only:
                    fig_bar = px.bar(stats_df, x='科目 (Subject)', y='班級平均 (Class Avg)', text_auto='.1f', color_discrete_sequence=['#636EFA'])
                else:
                    melted_df = stats_df.melt(id_vars='科目 (Subject)', value_vars=['學生分數 (Score)', '班級平均 (Class Avg)'], var_name='類別 (Type)', value_name='分數 (Score)')
                    fig_bar = px.bar(melted_df, x='科目 (Subject)', y='分數 (Score)', color='類別 (Type)', barmode='group', text_auto='.1f')
                fig_bar.update_layout(margin=dict(l=0, r=0, t=30, b=0)) 
                st.plotly_chart(fig_bar, use_container_width=True)
                
            with col_chart2:
                st.write("**🕸️ 班級能力雷達圖**" if show_class_only else "**🕸️ 能力雷達圖 (Radar Chart)**")
                fig_radar_web = go.Figure()
                if show_class_only:
                    fig_radar_web.add_trace(go.Scatterpolar(r=stats_df['班級平均 (Class Avg)'], theta=stats_df['科目 (Subject)'], fill='toself', name='班級平均', line_color='#636EFA'))
                else:
                    fig_radar_web.add_trace(go.Scatterpolar(r=stats_df['學生分數 (Score)'], theta=stats_df['科目 (Subject)'], fill='toself', name='學生分數', line_color='#FF4B4B'))
                    fig_radar_web.add_trace(go.Scatterpolar(r=stats_df['班級平均 (Class Avg)'], theta=stats_df['科目 (Subject)'], fill='toself', name='班級平均', line_color='#636EFA'))
                
                fig_radar_web.update_layout(
                    polar=dict(
                        bgcolor='rgba(0,0,0,0)', 
                        radialaxis=dict(
                            visible=True, 
                            range=[0, 100],
                            gridcolor='rgba(128, 128, 128, 0.3)', 
                            tickfont=dict(color='#888888', size=11) 
                        ),
                        angularaxis=dict(
                            gridcolor='rgba(128, 128, 128, 0.3)',
                            tickfont=dict(color='#888888', size=13)
                        )
                    ),
                    margin=dict(l=40, r=40, t=30, b=30), 
                    legend=dict(orientation="v", y=1, x=1.02)
                )
                st.plotly_chart(fig_radar_web, use_container_width=True)

            st.markdown("---")
            st.write("**📦 全班成績分布與個人表現對比 (Box Plot)**" if not is_virtual else "**📦 全班各科成績分布 (Box Plot)**")
            fig_box_web = go.Figure()
            fig_box_web.add_trace(go.Box(x=box_x, y=box_y, name='班級分布 (Class Dist.)', boxpoints='outliers'))
            
            if not is_virtual and stu_x:
                fig_box_web.add_trace(go.Scatter(
                    x=stu_x, y=stu_y, mode='markers+lines+text', name='個人分數 (Student Score)',
                    text=[f"{v:g}" for v in stu_y], textposition='top center',
                    marker=dict(color='#FF4B4B', size=10, symbol='diamond'),
                    line=dict(color='#FF4B4B', width=2, dash='dot'), textfont=dict(size=13, family='Arial Black') 
                ))
            
            fig_box_web.update_layout(yaxis=dict(title="分數", range=[0, 105]), margin=dict(l=40, r=40, t=30, b=20))
            st.plotly_chart(fig_box_web, use_container_width=True)

            st.markdown("---")
            st.write("**👥 班級各科成績區間分布人數 (Score Distribution)**")
            if dist_dict:
                dist_df = pd.DataFrame(dist_dict).T
                st.dataframe(dist_df.style.background_gradient(cmap='Blues', axis=1), use_container_width=True)
                melted_dist = dist_df.reset_index().melt(id_vars='index', var_name='成績區間 (Range)', value_name='人數 (Count)')
                melted_dist.rename(columns={'index': '科目 (Subject)'}, inplace=True)
                
                fig_dist_web = px.bar(melted_dist[melted_dist['人數 (Count)'] > 0], x='科目 (Subject)', y='人數 (Count)', color='成績區間 (Range)', 
                                  title="各科目分數區間分布圖 (Grouped Bar)", text_auto=True, color_discrete_sequence=px.colors.sequential.Teal)
                fig_dist_web.update_traces(textposition='outside', cliponaxis=False) 
                fig_dist_web.update_layout(barmode='group', margin=dict(l=0, r=0, t=40, b=0)) 
                st.plotly_chart(fig_dist_web, use_container_width=True)

    with tab2:
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
                st.dataframe(stats_df[['科目 (Subject)', '班級平均 (Class Avg)', '排除0分平均 (Adj Avg)', '班級最高 (Max)', '班級最低 (Min)', '中位數 (Median)', '標準差 (SD)']], use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("📈 歷年表現趨勢圖 (Historical Performance Trend)")
        
        # 1. Simply get all available subjects/metrics
        all_trackable = col_info['Subject'].unique().tolist()
        
        if is_virtual:
            st.markdown("請選擇要查看的指標，系統將繪製歷年 **班級平均** 趨勢。")
        else:
            st.markdown("請選擇要查看的指標，系統將自動同時繪製 **個人表現** 與 **班級平均** 進行對比。")
            
        # 2. ONE simple dropdown menu
        selected_metric = st.selectbox("選擇追蹤指標 (Select Metric)", all_trackable)
        
        trend_data = []
        
        # 3. Loop through exams and automatically grab BOTH data points
        for ex in available_exams:
            ex_cols = col_info[col_info['Exam_Label'] == ex]
            c_name_array = ex_cols[ex_cols['Subject'] == selected_metric]['Original_Col'].values
            
            if len(c_name_array) > 0:
                col = c_name_array[0]
                
                # Fetch Class Average
                if col in df.columns:
                    col_vals = df[col].dropna()
                    class_avg = col_vals.mean() if not col_vals.empty else np.nan
                else:
                    class_avg = np.nan
                    
                # Fetch Student Score
                if not is_virtual and col in student_data.columns:
                    student_score = student_data[col].iloc[0]
                else:
                    student_score = np.nan
                
                # Append data for plotting
                if is_virtual:
                    if pd.notna(class_avg):
                        trend_data.append({"Exam": ex, "Type": "班級平均 (Class Avg)", "Value": class_avg})
                else:
                    if pd.notna(student_score):
                        trend_data.append({"Exam": ex, "Type": "個人表現 (Student)", "Value": student_score})
                    
                    # Only show class average if it's NOT a ranking metric
                    if pd.notna(class_avg) and selected_metric not in ['班排', '校排']:
                        trend_data.append({"Exam": ex, "Type": "班級平均 (Class Avg)", "Value": class_avg})

        # 4. Draw the Plot
        if trend_data:
            trend_df = pd.DataFrame(trend_data)
            
            # Lock in consistent colors
            color_map = {
                "個人表現 (Student)": "#FF4B4B", # Red
                "班級平均 (Class Avg)": "#636EFA" # Blue
            }
            
            fig_trend = px.line(
                trend_df, x="Exam", y="Value", color="Type", markers=True,
                title=f"{selected_metric} - 歷年趨勢", color_discrete_map=color_map
            )
            
            # Format the numbers and hover text
            fig_trend.update_traces(
                mode='lines+markers+text',
                texttemplate='%{y:.1f}',
                textposition='top center',
                hovertemplate='考試: %{x}<br>%{fullData.name}: %{y:.1f}<extra></extra>'
            )
            
            # Clean up the layout and move legend to the top right
            fig_trend.update_layout(
                xaxis_title="考試 (Exam)", yaxis_title="分數 / 排名 (Score / Rank)", 
                margin=dict(l=0, r=0, t=40, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None)
            )
            
            # Auto-reverse Y-axis for Rankings (so 1st place is at the top)
            if selected_metric in ['班排', '校排']:
                 fig_trend.update_yaxes(autorange="reversed")
                 
            # Make the Class Average line dashed so it's easy to tell apart
            for trace in fig_trend.data:
                if '班級平均' in trace.name:
                    trace.line.dash = 'dash'
                    
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("尚無足夠的歷史資料可供呈現趨勢。")
