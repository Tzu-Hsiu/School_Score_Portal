import streamlit as st
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Student Score Portal", layout="wide")
st.title("📊 學生學習深度分析系統 (Advanced Student Analytics)")

# --- 1. Connect to Google Sheets ---
@st.cache_data(ttl=600)
def load_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # NEW CODE: Tell Streamlit to read from the secure cloud vault
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    
    client = gspread.authorize(creds)
    sheet = client.open("School_Master_Score").sheet1 
    data = sheet.get_all_records()
    return pd.DataFrame(data).replace('', np.nan)

try:
    df = load_data()
except Exception as e:
    st.error(f"無法連接到資料庫 (Database connection failed): {e}")
    st.stop()

# --- Helper Function: Parse Columns ---
def parse_columns(columns):
    parsed_data = []
    pattern = r"(?P<year>\w+)_(?P<sem>\w+)_(?P<type>[EQ])_(?P<num>[\w\-]+)_+\{(?P<subject>.*?)\}_+\{(?P<detail>.*?)\}"
    for col in columns:
        match = re.match(pattern, str(col))
        if match:
            exam_label = f"{match.group('year')}-{match.group('sem')} 段考{match.group('num')}"
            parsed_data.append({
                "Original_Col": col,
                "Year": match.group("year"),
                "Semester": match.group("sem"),
                "Exam_Type": match.group("type"),
                "Number": match.group("num"),
                "Subject": match.group("subject"),
                "Exam_Label": exam_label
            })
    return pd.DataFrame(parsed_data)

col_info = parse_columns(df.columns)
if not col_info.empty:
    col_info.sort_values(by=['Year', 'Semester', 'Number'], inplace=True)
available_exams = col_info['Exam_Label'].unique().tolist()
exclude_stats = ['總分', '平均', '班排', '校排']

# --- 2. Login Interface ---
st.markdown("請輸入學號與專屬密碼來查詢成績 (Please enter Student ID and PIN)")
df['StudentID'] = df['StudentID'].astype(str)
df['Pin'] = df['Pin'].astype(str)

col1, col2 = st.columns(2)
with col1:
    user_id = st.text_input("學號 / 帳號 (ID)")
with col2:
    user_pin = st.text_input("密碼 (PIN)", type="password")

login_button = st.button("登入查詢 (Login)")

if login_button or ('logged_in' in st.session_state and st.session_state.logged_in):
    st.session_state.logged_in = True 
    
    is_virtual_account = (user_id == '777' and user_pin == '777')
    
    if is_virtual_account:
        st.success("歡迎進入 🏫 班級總覽模式 (Class Overview Mode)！")
        student_data = pd.DataFrame() 
    else:
        student_data = df[(df['StudentID'] == user_id) & (df['Pin'] == user_pin)]
        if student_data.empty:
            st.error("學號或密碼錯誤，請重新確認。(Invalid ID or PIN.)")
            st.session_state.logged_in = False
            st.stop()
        else:
            student_name = student_data.iloc[0]['Name']
            st.success(f"歡迎, {student_name} 的家長！")
        
    tab1, tab2, tab3 = st.tabs(["📊 學習總覽 (Overview)", "🔬 深度數據分析 (Deep Analytics)", "📈 歷年趨勢 (Historical Trend)"])
    
    # -------------------------------------------------------------------
    # TAB 1 & 2: SPECIFIC EXAM ANALYSIS
    # -------------------------------------------------------------------
    with tab1:
        st.subheader("選擇想查看的考試 (Select Exam)")
        selected_exam = st.selectbox("Exam", available_exams, label_visibility="collapsed")
        exam_all_cols = col_info[col_info['Exam_Label'] == selected_exam]
        
        if exam_all_cols.empty:
            st.warning("此考試尚未有成績資料 (No data available).")
        else:
            # --- KPI Dashboard ---
            st.markdown("### 🏆 本次考試表現 (Exam Summary)")
            kpi_cols = st.columns(4)
            
            def get_class_metric(subject_name):
                try:
                    col_name = exam_all_cols[exam_all_cols['Subject'] == subject_name]['Original_Col'].values[0]
                    return pd.to_numeric(df[col_name], errors='coerce').dropna()
                except:
                    return pd.Series(dtype=float)
            
            tot_scores = get_class_metric('總分')
            avg_scores = get_class_metric('平均')
            
            if is_virtual_account:
                kpi_cols[0].metric("班級平均總分 (Class Avg Total)", f"{tot_scores.mean():.1f}" if not tot_scores.empty else "-")
                kpi_cols[1].metric("班級最高總分 (Max Total Score)", f"{tot_scores.max():g}" if not tot_scores.empty else "-")
                kpi_cols[2].metric("班級總平均 (Class Average)", f"{avg_scores.mean():.1f}" if not avg_scores.empty else "-")
                kpi_cols[3].metric("參與考試人數 (Students Tested)", f"{len(tot_scores)}" if not tot_scores.empty else "-")
            else:
                def get_metric(subject_name):
                    try:
                        col_name = exam_all_cols[exam_all_cols['Subject'] == subject_name]['Original_Col'].values[0]
                        val = pd.to_numeric(student_data[col_name].iloc[0], errors='coerce')
                        total_count = pd.to_numeric(df[col_name], errors='coerce').count()
                        return val, total_count
                    except:
                        return np.nan, 0

                tot_score, _ = get_metric('總分')
                avg_score, _ = get_metric('平均')
                c_rank, c_total = get_metric('班排')
                s_rank, _ = get_metric('校排') 
                s_total = 520 
                
                kpi_cols[0].metric("總分 (Total Score)", f"{tot_score:g}" if pd.notna(tot_score) else "-")
                kpi_cols[1].metric("平均 (Average)", f"{avg_score:g}" if pd.notna(avg_score) else "-")
                c_rank_str = f"{int(c_rank)} / {c_total}" if pd.notna(c_rank) else "-"
                kpi_cols[2].metric("班級排名 (Class Rank)", c_rank_str, f"(Top {(c_rank/c_total)*100:.1f}%)" if pd.notna(c_rank) and c_total>0 else "", delta_color="off")
                s_rank_str = f"{int(s_rank)} / {s_total}" if pd.notna(s_rank) else "-"
                kpi_cols[3].metric("校排 (School Rank)", s_rank_str, f"(Top {(s_rank/s_total)*100:.1f}%)" if pd.notna(s_rank) and s_total>0 else "", delta_color="off")
            
            st.markdown("---")

            # --- Subject Analytics & Score Distribution ---
            exam_subj_cols = exam_all_cols[~exam_all_cols['Subject'].isin(exclude_stats)]
            stats_list = []
            
            bins = [-1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
            labels = ['0-10', '11-20', '21-30', '31-40', '41-50', '51-60', '61-70', '71-80', '81-90', '91-100']
            dist_dict = {}
            
            for index, row in exam_subj_cols.iterrows():
                subj = row['Subject']
                col_name = row['Original_Col']
                class_scores = pd.to_numeric(df[col_name], errors='coerce').dropna()
                
                if class_scores.empty: continue
                
                dist_dict[subj] = pd.cut(class_scores, bins=bins, labels=labels).value_counts().reindex(labels, fill_value=0)
                
                mean_val = class_scores.mean()
                std_dev = class_scores.std()
                adj_mean = class_scores[class_scores > 0].mean()
                
                stat_dict = {
                    '科目 (Subject)': subj,
                    '班級平均 (Class Avg)': round(mean_val, 1),
                    '排除0分平均 (Adj Avg)': round(adj_mean, 1) if pd.notna(adj_mean) else np.nan,
                    '班級最高 (Max)': class_scores.max(),
                    '班級最低 (Min)': class_scores.min(),
                    '中位數 (Median)': round(class_scores.median(), 1),
                    '標準差 (SD)': round(std_dev, 1)
                }
                
                if not is_virtual_account:
                    student_score = pd.to_numeric(student_data[col_name].iloc[0], errors='coerce')
                    if pd.notna(student_score):
                        z_score = (student_score - mean_val) / std_dev if std_dev > 0 else 0
                        pr = (class_scores <= student_score).mean() * 100
                        stat_dict['學生分數 (Score)'] = student_score
                        stat_dict['Z分數 (Z-Score)'] = round(z_score, 2)
                        stat_dict['百分等級 (PR)'] = round(pr, 1)
                
                stats_list.append(stat_dict)
            
            stats_df = pd.DataFrame(stats_list)
            
            if not stats_df.empty:
                col_chart1, col_chart2 = st.columns([3, 2])
                
                with col_chart1:
                    st.write("**📊 班級各科平均表現**" if is_virtual_account else "**📊 成績對比圖 (Grouped Bar Chart)**")
                    if is_virtual_account:
                        fig_bar = px.bar(stats_df, x='科目 (Subject)', y='班級平均 (Class Avg)', text_auto='.1f', color_discrete_sequence=['#636EFA'])
                        fig_bar.update_layout(margin=dict(l=0, r=0, t=30, b=0))
                    else:
                        melted_df = stats_df.melt(id_vars='科目 (Subject)', value_vars=['學生分數 (Score)', '班級平均 (Class Avg)'], var_name='類別 (Type)', value_name='分數 (Score)')
                        fig_bar = px.bar(melted_df, x='科目 (Subject)', y='分數 (Score)', color='類別 (Type)', barmode='group', text_auto='.1f')
                        fig_bar.update_layout(legend_title=None, margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig_bar, use_container_width=True)
                    
                with col_chart2:
                    st.write("**🕸️ 班級能力雷達圖**" if is_virtual_account else "**🕸️ 能力雷達圖 (Radar Chart)**")
                    fig_radar = go.Figure()
                    if is_virtual_account:
                        fig_radar.add_trace(go.Scatterpolar(r=stats_df['班級平均 (Class Avg)'], theta=stats_df['科目 (Subject)'], fill='toself', name='班級平均'))
                    else:
                        fig_radar.add_trace(go.Scatterpolar(r=stats_df['學生分數 (Score)'], theta=stats_df['科目 (Subject)'], fill='toself', name='學生分數'))
                        fig_radar.add_trace(go.Scatterpolar(r=stats_df['班級平均 (Class Avg)'], theta=stats_df['科目 (Subject)'], fill='toself', name='班級平均'))
                    
                    fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), margin=dict(l=40, r=40, t=30, b=30), legend=dict(orientation="h", y=-0.2))
                    st.plotly_chart(fig_radar, use_container_width=True)

                st.markdown("---")
                st.write("**👥 班級各科成績區間分布人數 (Score Distribution)**")
                if dist_dict:
                    dist_df = pd.DataFrame(dist_dict).T
                    styled_dist = dist_df.style.background_gradient(cmap='Blues', axis=1)
                    st.dataframe(styled_dist, use_container_width=True)

                with tab2:
                    st.subheader(f"{selected_exam} - 深度數據分析 (Deep Statistical Breakdown)")
                    st.markdown("* **排除0分平均:** 扣除缺考(0分)同學後的實際班級平均，更能反映真實難度。")
                    if not is_virtual_account:
                        st.markdown("""
                        * **Z分數 (Z-Score):** 大於 0 代表高於平均，大於 1 代表在班上屬於前段班。
                        * **百分等級 (PR):** PR85 代表該生成績贏過班上 85% 的同學。
                        """)
                        styled_df = stats_df.style.applymap(
                            lambda x: 'color: green' if x > 0 else ('color: red' if x < 0 else ''), subset=['Z分數 (Z-Score)']
                        )
                        st.dataframe(styled_df, use_container_width=True, hide_index=True)
                    else:
                        cols_order = ['科目 (Subject)', '班級平均 (Class Avg)', '排除0分平均 (Adj Avg)', '班級最高 (Max)', '班級最低 (Min)', '中位數 (Median)', '標準差 (SD)']
                        st.dataframe(stats_df[cols_order], use_container_width=True, hide_index=True)

    # -------------------------------------------------------------------
    # TAB 3: HISTORICAL TREND
    # -------------------------------------------------------------------
    with tab3:
        st.subheader("歷年表現趨勢圖 (Historical Performance Trend)")
        all_trackable = col_info['Subject'].unique().tolist()
        
        if is_virtual_account:
            base_options = [s for s in all_trackable if s != '班排']
            track_options = []
            for opt in base_options:
                track_options.extend([
                    opt,
                    f"{opt} (排除後三名/Adj)",
                    f"{opt} (前30%/Top 30%)",
                    f"{opt} (中間40%/Mid 40%)",
                    f"{opt} (後30%/Bottom 30%)"
                ])
        else:
            track_options = all_trackable
            
        selected_track = st.selectbox("選擇追蹤項目 (Select Item to Track)", track_options)
        
        # Parse the modifier if it exists
        modifier = ""
        if "(" in selected_track:
            modifier = selected_track.split(" (")[1].replace(")", "")
            actual_subject = selected_track.split(" (")[0]
        else:
            actual_subject = selected_track
        
        trend_data = []
        subj_cols = col_info[col_info['Subject'] == actual_subject]
        
        for index, row in subj_cols.iterrows():
            col_name = row['Original_Col']
            exam_label = row['Exam_Label']
            class_scores = pd.to_numeric(df[col_name], errors='coerce').dropna()
            
            if class_scores.empty: continue
            
            # --- Advanced Filtering Logic (Virtual Account) ---
            target_scores = class_scores
            
            if is_virtual_account and len(class_scores) > 0 and modifier:
                # If tracking ranks (校排), smaller numbers are "better" (Ascending = True)
                # If tracking scores (總分), larger numbers are "better" (Ascending = False)
                is_rank = (actual_subject == '校排')
                sorted_scores = class_scores.sort_values(ascending=is_rank)
                
                n = len(sorted_scores)
                top_count = max(1, int(n * 0.3)) # Ensures we at least grab 1 student
                
                if modifier == "排除後三名/Adj" and n > 3:
                    target_scores = sorted_scores.iloc[:-3] # Drop worst 3
                elif modifier == "前30%/Top 30%":
                    target_scores = sorted_scores.iloc[:top_count]
                elif modifier == "中間40%/Mid 40%":
                    target_scores = sorted_scores.iloc[top_count:-top_count]
                elif modifier == "後30%/Bottom 30%":
                    target_scores = sorted_scores.iloc[-top_count:]

            class_avg = round(target_scores.mean(), 1) if not target_scores.empty else np.nan
            
            if is_virtual_account:
                trend_data.append({
                    '考試 (Exam)': exam_label,
                    f'班級平均 ({modifier if modifier else "Class Average"})': class_avg
                })
            else:
                student_score = pd.to_numeric(student_data[col_name].iloc[0], errors='coerce')
                if pd.notna(student_score):
                    trend_data.append({
                        '考試 (Exam)': exam_label,
                        '學生表現 (Student)': student_score,
                        # Class Rank average is meaningless, but School Rank average is useful!
                        '班級平均 (Class Average)': class_avg if actual_subject != '班排' else np.nan
                    })
        
        if trend_data:
            trend_df = pd.DataFrame(trend_data)
            
            if is_virtual_account:
                y_col = f'班級平均 ({modifier if modifier else "Class Average"})'
                fig_trend = px.line(trend_df, x='考試 (Exam)', y=y_col, markers=True, text=y_col)
                if actual_subject == '校排':
                    fig_trend.update_yaxes(autorange="reversed") 
                fig_trend.update_traces(textposition="bottom right")
            else:
                if actual_subject == '班排':
                    # Only plot student for Class Rank
                    fig_trend = px.line(trend_df, x='考試 (Exam)', y='學生表現 (Student)', markers=True, text='學生表現 (Student)')
                    fig_trend.update_yaxes(autorange="reversed")
                    fig_trend.update_traces(textposition="bottom right")
                elif actual_subject == '校排':
                    # Plot BOTH student and class average for School Rank
                    melted_trend = trend_df.melt(id_vars='考試 (Exam)', value_vars=['學生表現 (Student)', '班級平均 (Class Average)'], var_name='Type', value_name='Rank')
                    fig_trend = px.line(melted_trend, x='考試 (Exam)', y='Rank', color='Type', markers=True)
                    fig_trend.update_yaxes(autorange="reversed")
                else:
                    melted_trend = trend_df.melt(id_vars='考試 (Exam)', value_vars=['學生表現 (Student)', '班級平均 (Class Average)'], var_name='Type', value_name='Score')
                    fig_trend = px.line(melted_trend, x='考試 (Exam)', y='Score', color='Type', markers=True)
            
            st.plotly_chart(fig_trend, use_container_width=True)
            st.dataframe(trend_df.set_index('考試 (Exam)'), use_container_width=True)
        else:
            st.info("尚無足夠的歷史資料可供繪圖 (Not enough historical data).")