import streamlit as st
import pandas as pd
import numpy as np
from reports.html_generator import generate_html_reports

def render(df, col_info, available_exams, exclude_stats):
    st.success("👨‍🏫 歡迎進入教師管理後台 (Teacher Admin Panel)！")
    
    # Split Teacher Mode into Tabs
    tab_t1, tab_t2, tab_t3 = st.tabs(["📊 成績總表與進退步 (Exam & Progress)", "🖨️ 批量產生報告 (Bulk Print)", "📥 原始資料匯出 (Raw Data)"])
    
    with tab_t1:
        st.subheader("🖨️ 產生特定考試的成績總表 (Generate Exam Transcripts)")
        selected_exam_teacher = st.selectbox("選擇考試 (Select Exam)", available_exams, key="teacher_exam_select")
        exam_specific_cols = col_info[col_info['Exam_Label'] == selected_exam_teacher]
        
        if not exam_specific_cols.empty:
            try:
                curr_idx = available_exams.index(selected_exam_teacher)
                prev_exam_label = available_exams[curr_idx - 1] if curr_idx > 0 else None
            except ValueError:
                prev_exam_label = None

            col_names_original = exam_specific_cols['Original_Col'].tolist()
            transcript_df = df[['StudentID', 'Name'] + col_names_original].dropna(subset=col_names_original, how='all').copy()
            rename_dict = {row['Original_Col']: row['Subject'] for idx, row in exam_specific_cols.iterrows()}
            transcript_df = transcript_df.rename(columns=rename_dict)
            
            diff_cols = []
            if prev_exam_label:
                prev_exam_cols = col_info[col_info['Exam_Label'] == prev_exam_label]
                if not prev_exam_cols.empty:
                    prev_map = {row['Subject']: row['Original_Col'] for idx, row in prev_exam_cols.iterrows()}
                    
                    for subj in ['總分', '平均', '班排']:
                        if subj in transcript_df.columns and subj in prev_map:
                            prev_col = prev_map[subj]
                            prev_scores = df.set_index('StudentID')[prev_col]
                            curr_scores = transcript_df[subj]
                            mapped_prev = transcript_df['StudentID'].map(prev_scores)
                            
                            diff_col_name = f'{subj} 進退步'
                            if subj == '班排': 
                                diff = mapped_prev - curr_scores
                            else:
                                diff = curr_scores - mapped_prev
                            
                            col_idx = transcript_df.columns.get_loc(subj)
                            transcript_df.insert(col_idx + 1, diff_col_name, diff)
                            diff_cols.append(diff_col_name)

            def highlight_diff(val):
                if pd.isna(val): return ''
                if val > 0: return 'color: green; font-weight: bold;'
                elif val < 0: return 'color: red; font-weight: bold;'
                return 'color: gray;'
            
            # Format to avoid too many decimal places on CSV export
            for col in transcript_df.select_dtypes(include=[np.number]).columns:
                transcript_df[col] = transcript_df[col].round(1)
            
            styled_df = transcript_df.style
            if diff_cols:
                styled_df = styled_df.map(highlight_diff, subset=diff_cols)
            
            def safe_fmt(v):
                if pd.isna(v): return ""
                return f"{float(v):g}" 
            
            styled_df = styled_df.format(safe_fmt, subset=transcript_df.select_dtypes(include=[np.number]).columns)
            
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            csv_exam = transcript_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(label=f"下載 {selected_exam_teacher} 總成績單", data=csv_exam, file_name=f"{selected_exam_teacher}_transcripts.csv", mime="text/csv")
    
    with tab_t2:
        st.subheader("🖨️ 批量產生個人專屬成績單 (Bulk Individual Print-Outs)")
        st.markdown("選擇考試及想附上的圖表，系統將為全班生成獨立的成績單。下載後用瀏覽器開啟列印即可。")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            selected_exam_html = st.selectbox("選擇要列印的考試", available_exams, key="teacher_exam_html")
        with col_t2:
            chart_options = st.multiselect(
                "選擇要在成績單上顯示的圖表 (Chart Options)", 
                ["箱形圖 (Box Plot)", "長條對比圖 (Bar Chart)", "分布長條圖 (Distribution Chart)", "雷達圖 (Radar Chart)"], 
                default=["箱形圖 (Box Plot)", "分布長條圖 (Distribution Chart)"]
            )
            
        if st.button("✨ 產生全班個人報告 (Generate Personal Reports)"):
            exam_check = col_info[col_info['Exam_Label'] == selected_exam_html]
            if not exam_check.empty:
                with st.spinner("正在為全班學生繪製分析報告..."):
                    html_content = generate_html_reports(selected_exam_html, df, df, col_info, exclude_stats, chart_options)
                    st.download_button(
                        label=f"📥 下載 {selected_exam_html} 全班成績單 (HTML)",
                        data=html_content, file_name=f"{selected_exam_html}_Personal_Reports.html", mime="text/html"
                    )
            else:
                st.warning("此考試尚未有成績資料。")
                
    with tab_t3:
        st.subheader("📥 匯出全校/全班原始成績總表 (Download Master Data)")
        csv_all = df.to_csv(index=False).encode('utf-8-sig') 
        st.download_button(label="下載完整成績單 (CSV)", data=csv_all, file_name="master_students_data.csv", mime="text/csv")
