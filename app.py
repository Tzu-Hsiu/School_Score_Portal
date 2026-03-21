import streamlit as st
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import plotly.express as px
import plotly.graph_objects as go
import json
import plotly.utils

# Ensure pandas doesn't throw warnings for future downcasting behavior
pd.set_option('future.no_silent_downcasting', True)

st.set_page_config(page_title="Student Score Portal", layout="wide")
st.title("📊 學生學習深度分析系統 (Advanced Student Analytics)")

# --- 1. Connect to Google Sheets ---
@st.cache_data(ttl=600)
def load_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        gcp_creds = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_creds, scope)
    except KeyError:
        st.error("找不到 `gcp_service_account` 憑證！請確認你的 `.streamlit/secrets.toml` 檔案設定正確。")
        st.stop()
    except Exception as e:
        st.error(f"讀取 Secrets 時發生錯誤 (Error reading secrets): {e}")
        st.stop()
        
    try:
        client = gspread.authorize(creds)
        sheet = client.open("School_Master_Score").sheet1 
        data = sheet.get_all_records()
        return pd.DataFrame(data).replace('', np.nan)
    except Exception as e:
        st.error(f"Google Sheets 連線失敗 (Google API Error): {e}")
        st.stop()

df = load_data()

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

# --- OPTIMIZATION: Convert all exam columns to numeric upfront ---
exam_cols = col_info['Original_Col'].tolist()
for col in exam_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

df['StudentID'] = df['StudentID'].astype(str)
df['Pin'] = df['Pin'].astype(str)

# --- Generator for Personal HTML Transcripts ---
def generate_html_reports(exam_label, df_source_student, df_source_class, col_info_source, ex_stats, chart_options):
    e_cols = col_info_source[col_info_source['Exam_Label'] == exam_label]
    s_cols = e_cols[~e_cols['Subject'].isin(ex_stats)]
    
    # 1. Determine Previous Exam for Progress Tracking
    all_exams = col_info_source['Exam_Label'].unique().tolist()
    try:
        current_idx = all_exams.index(exam_label)
        prev_exam_label = all_exams[current_idx - 1] if current_idx > 0 else None
    except ValueError:
        prev_exam_label = None

    prev_e_cols = pd.DataFrame()
    if prev_exam_label:
        prev_e_cols = col_info_source[col_info_source['Exam_Label'] == prev_exam_label]
    
    # 2. Pre-calculate class stats
    c_stats = {}
    bins = [-1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    dist_labels = ['0-10', '11-20', '21-30', '31-40', '41-50', '51-60', '61-70', '71-80', '81-90', '91-100']
    dist_dict = {}
    
    box_x, box_y = [], []
    
    for _, row in s_cols.iterrows():
        c_name = row['Original_Col']
        subj = row['Subject']
        scores = df_source_class[c_name].dropna()
        c_stats[c_name] = {
            'Subject': subj,
            'Mean': scores.mean() if not scores.empty else 0,
            'Adj_Mean': scores[scores > 0].mean() if not scores[scores > 0].empty else np.nan, 
            'Std': scores.std() if not scores.empty else 0,
            'Scores': scores
        }
        if not scores.empty:
            dist_dict[subj] = pd.cut(scores, bins=bins, labels=dist_labels).value_counts().reindex(dist_labels, fill_value=0).tolist()
            box_x.extend([subj] * len(scores))
            box_y.extend(scores.tolist())
            
    # 3. HTML Score Distribution Grouped Bar Chart
    dist_chart_json = None
    if "分布長條圖 (Distribution Chart)" in chart_options:
        fig_dist = go.Figure()
        colors = ['#ffffff', '#f8f9fa', '#f1f3f5', '#e9ecef', '#dee2e6', 
                  '#ced4da', '#adb5bd', '#999999', '#888888', '#777777']
        active_labels_idx = [i for i, label in enumerate(dist_labels) if any(dist_dict[subj][i] > 0 for subj in s_cols['Subject'] if subj in dist_dict)]
              
        for idx in active_labels_idx:
            label = dist_labels[idx]
            y_vals = [dist_dict[subj][idx] if subj in dist_dict else 0 for subj in s_cols['Subject']]
            text_vals = [str(v) if v > 0 else "" for v in y_vals]
            
            fig_dist.add_trace(go.Bar(
                name=label, x=s_cols['Subject'].tolist(), y=y_vals, 
                text=text_vals, textposition='outside', cliponaxis=False,             
                textfont=dict(color='black', size=13, family='Arial Black'),
                marker=dict(color=colors[idx], line=dict(color='black', width=0.8))
            ))
            
            fig_dist.update_layout(
                barmode='group',                  
                title=dict(text="全班各科成績區間分布人數", font=dict(color='black')), 
                margin=dict(l=40, r=40, t=40, b=20), 
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                legend=dict(orientation="v", y=1, x=1.02, font=dict(color='black')), # Moved to Side
                yaxis=dict(showgrid=True, gridcolor='#dddddd', tickfont=dict(color='black')),
                xaxis=dict(tickfont=dict(color='black'))
            )
        dist_chart_json = json.dumps(fig_dist, cls=plotly.utils.PlotlyJSONEncoder)

    exam_col_names = e_cols['Original_Col'].tolist()
    valid_students = df_source_student.dropna(subset=exam_col_names, how='all')
    
    html_parts = [
        "<html><head><meta charset='utf-8'>",
        "<title>個人成績分析報告</title>",
        "<script src='https://cdn.plot.ly/plotly-2.24.1.min.js'></script>",
        "<style>",
        "body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; background-color: #f4f4f9; }",
        ".page { page-break-after: always; background: white; margin: 0 auto 20px auto; max-width: 1000px; padding: 40px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }",
        "@media print { body { background-color: white; } .page { margin: 0; padding: 20px; box-shadow: none; max-width: 100%; border: none; } }",
        ".header { text-align: center; margin-bottom: 20px; border-bottom: 3px solid #2c3e50; padding-bottom: 10px; }",
        ".header h2 { margin: 0; color: #2c3e50; font-size: 26px; }",
        ".header h3 { margin: 10px 0 0 0; color: #7f8c8d; font-size: 18px; }",
        "table { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px; }",
        "th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }",
        "th { background-color: #34495e; color: white; font-weight: bold; }",
        "tr:nth-child(even) { background-color: #f9f9f9; }",
        ".kpi-container { display: flex; justify-content: space-around; margin-bottom: 20px; background: #ecf0f1; padding: 15px; border-radius: 10px; }",
        ".kpi { text-align: center; }",
        ".kpi-title { font-size: 14px; color: #7f8c8d; font-weight: bold; margin-bottom: 5px; }",
        ".kpi-val { font-size: 24px; font-weight: bold; color: #2980b9; margin-bottom: 5px; }",
        ".kpi-prog { font-size: 14px; font-weight: bold; margin-bottom: 4px; }",
        ".kpi-top-pct { font-size: 14px; color: #7f8c8d; }",
        ".charts-wrapper { display: flex; flex-direction: column; gap: 30px; margin-top: 30px; }",
        ".chart-row { display: flex; flex-direction: row; align-items: center; justify-content: space-between; gap: 20px; padding: 20px; background: #fafafa; border-radius: 8px; page-break-inside: avoid; border: 1px solid #eee; }",
        ".chart-desc { flex: 1; font-size: 14px; color: #444; line-height: 1.6; }",
        ".chart-desc h4 { color: #2980b9; margin-top: 0; margin-bottom: 10px; font-size: 18px; border-bottom: 2px solid #2980b9; padding-bottom: 5px; display: inline-block; }",
        ".chart-item { flex: 2; height: 350px; min-width: 0; }",
        "@media print { .chart-row { flex-direction: row; } .chart-item { width: 65%; } .chart-desc { width: 30%; } }",
        "</style></head><body>"
    ]
    
    def get_prog_html(curr, prev, is_rank=False):
        if pd.isna(curr) or pd.isna(prev): return ""
        diff = round(prev - curr if is_rank else curr - prev, 2)
        unit = "名" if is_rank else "分"
        if diff > 0: return f"<div class='kpi-prog' style='color: green;'>▲ {diff:g} {unit}</div>"
        elif diff < 0: return f"<div class='kpi-prog' style='color: red;'>▼ {abs(diff):g} {unit}</div>"
        else: return f"<div class='kpi-prog' style='color: gray;'>-</div>"
    
    for idx, student in valid_students.iterrows():
        stu_name = student['Name']
        stu_id = student['StudentID']
        
        tot_col = e_cols[e_cols['Subject'] == '總分']['Original_Col']
        avg_col = e_cols[e_cols['Subject'] == '平均']['Original_Col']
        crank_col = e_cols[e_cols['Subject'] == '班排']['Original_Col']
        srank_col = e_cols[e_cols['Subject'] == '校排']['Original_Col']
        
        curr_tot_val = student[tot_col.values[0]] if not tot_col.empty else np.nan
        curr_avg_val = student[avg_col.values[0]] if not avg_col.empty else np.nan
        curr_crank_val = student[crank_col.values[0]] if not crank_col.empty else np.nan
        curr_srank_val = student[srank_col.values[0]] if not srank_col.empty else np.nan
        
        c_total_html = len(df_source_class[crank_col.values[0]].dropna()) if not crank_col.empty else 0

        tot = f"{curr_tot_val:g}" if pd.notna(curr_tot_val) else '-'
        avg = f"{curr_avg_val:g}" if pd.notna(curr_avg_val) else '-'
        
        crank_base = f"{curr_crank_val:g} / {c_total_html}" if pd.notna(curr_crank_val) and c_total_html > 0 else '-'
        crank_top_html = f"<div class='kpi-top-pct'>(Top {curr_crank_val / c_total_html * 100:.1f}%)</div>" if pd.notna(curr_crank_val) and c_total_html > 0 else ""

        srank_base = f"{curr_srank_val:g} / 520" if pd.notna(curr_srank_val) else '-'
        srank_top_html = f"<div class='kpi-top-pct'>(Top {curr_srank_val / 520 * 100:.1f}%)</div>" if pd.notna(curr_srank_val) else ""
        
        tot_prog_html, avg_prog_html, crank_prog_html, srank_prog_html = "", "", "", ""
        
        if prev_exam_label and not prev_e_cols.empty:
            p_tot_col = prev_e_cols[prev_e_cols['Subject'] == '總分']['Original_Col']
            p_avg_col = prev_e_cols[prev_e_cols['Subject'] == '平均']['Original_Col']
            p_crank_col = prev_e_cols[prev_e_cols['Subject'] == '班排']['Original_Col']
            p_srank_col = prev_e_cols[prev_e_cols['Subject'] == '校排']['Original_Col']
            
            tot_prog_html = get_prog_html(curr_tot_val, student[p_tot_col.values[0]] if not p_tot_col.empty else np.nan, False)
            avg_prog_html = get_prog_html(curr_avg_val, student[p_avg_col.values[0]] if not p_avg_col.empty else np.nan, False)
            crank_prog_html = get_prog_html(curr_crank_val, student[p_crank_col.values[0]] if not p_crank_col.empty else np.nan, True)
            srank_prog_html = get_prog_html(curr_srank_val, student[p_srank_col.values[0]] if not p_srank_col.empty else np.nan, True)

        html_parts.append("<div class='page'>")
        html_parts.append(f"<div class='header'><h2>{exam_label} - 個人成績分析報告</h2><h3>{stu_name} (學號: {stu_id})</h3></div>")
        
        html_parts.append(f"""
        <div class='kpi-container'>
            <div class='kpi'><div class='kpi-title'>總分</div><div class='kpi-val'>{tot}</div>{tot_prog_html}</div>
            <div class='kpi'><div class='kpi-title'>平均</div><div class='kpi-val'>{avg}</div>{avg_prog_html}</div>
            <div class='kpi'><div class='kpi-title'>班級排名</div><div class='kpi-val'>{crank_base}</div>{crank_prog_html}{crank_top_html}</div>
            <div class='kpi'><div class='kpi-title'>校排</div><div class='kpi-val'>{srank_base}</div>{srank_prog_html}{srank_top_html}</div>
        </div>
        """)
        
        progression_headers = f"<th>前次分數<br>({prev_exam_label.split(' ')[-1]})</th><th>進退步</th>" if prev_exam_label else ""
        html_parts.append(f"<table><tr><th>科目</th><th>分數</th><th>班級平均</th><th>排除0分平均</th>{progression_headers}<th>Z分數</th><th>PR值</th></tr>")
        
        radar_subj, radar_stu, radar_avg = [], [], []
        
        for _, row in s_cols.iterrows():
            c_name = row['Original_Col']
            subj = row['Subject']
            score = student[c_name]
            
            if pd.notna(score):
                mean = c_stats[c_name]['Mean']
                adj_mean = c_stats[c_name]['Adj_Mean'] 
                std = c_stats[c_name]['Std']
                all_scores = c_stats[c_name]['Scores']
                
                z_score = (score - mean) / std if std > 0 else 0
                pr = (all_scores <= score).mean() * 100
                z_color = "color: green;" if z_score > 0 else ("color: red;" if z_score < 0 else "")
                
                adj_mean_str = f"{adj_mean:.1f}" if pd.notna(adj_mean) else "-"
                
                progression_html = ""
                if prev_exam_label:
                    prev_score_str, diff_str, diff_style = "-", "-", ""
                    if not prev_e_cols[prev_e_cols['Subject'] == subj].empty:
                        p_name = prev_e_cols[prev_e_cols['Subject'] == subj]['Original_Col'].values[0]
                        p_score = student[p_name]
                        if pd.notna(p_score):
                            prev_score_str = f"{p_score:g}"
                            diff = score - p_score
                            if diff > 0:
                                diff_str, diff_style = f"+{diff:g}", "color: green; font-weight: bold;"
                            elif diff < 0:
                                diff_str, diff_style = f"{diff:g}", "color: red; font-weight: bold;"
                            else:
                                diff_str, diff_style = "0", "color: gray;"
                    progression_html = f"<td>{prev_score_str}</td><td style='{diff_style}'>{diff_str}</td>"

                html_parts.append(f"<tr><td>{subj}</td><td>{score:g}</td><td>{mean:.1f}</td><td>{adj_mean_str}</td>{progression_html}<td style='{z_color}'>{z_score:.2f}</td><td>{pr:.1f}</td></tr>")
                
                radar_subj.append(subj)
                radar_stu.append(score)
                radar_avg.append(mean)
        
        html_parts.append("</table>")
        html_parts.append("<div class='charts-wrapper'>")
        
        # HTML Radar Chart (Keep legend at bottom)
        if "雷達圖 (Radar Chart)" in chart_options and radar_subj:
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(r=radar_avg, theta=radar_subj, fill='toself', name='班級平均', line_color='gray'))
            fig_radar.add_trace(go.Scatterpolar(r=radar_stu, theta=radar_subj, fill='toself', name='個人分數', line_color='#2c3e50'))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                title=dict(text="能力雷達圖 (Radar Chart)", font=dict(color='black')),
                margin=dict(l=40, r=40, t=40, b=20),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                legend=dict(orientation="v", y=1, x=1.02, font=dict(color='black')) # <--- Legend moved to the side
            )
            radar_json = json.dumps(fig_radar, cls=plotly.utils.PlotlyJSONEncoder)
            radar_id = f"radar_{stu_id}_{idx}"
            html_parts.append("<div class='chart-row'>")
            html_parts.append("""
                <div class='chart-desc'>
                    <h4>雷達圖分析</h4>
                    <p>雷達圖能直觀呈現您在各科目的均衡度。</p>
                    <p><b>灰色區域</b>代表班級的平均表現，而<b>深色實線</b>則是您的個人成績。</p>
                    <p>當深色線條超出灰色區域時，代表您在該科目表現優於班級平均，是您的優勢科目！若凹陷於灰色區域內，則可作為未來加強的參考。</p>
                </div>
            """)
            html_parts.append(f"<div id='{radar_id}' class='chart-item'></div>")
            html_parts.append("</div>")
            html_parts.append(f"<script>var radarData_{idx} = {radar_json}; Plotly.newPlot('{radar_id}', radarData_{idx}.data, radarData_{idx}.layout, {{displayModeBar: false}});</script>")
            
        # HTML Box Plot
        if "箱形圖 (Box Plot)" in chart_options and radar_subj:
            fig_box = go.Figure()
            fig_box.add_trace(go.Box(
                x=box_x, y=box_y, name='班級分布 (Class Dist.)',
                marker_color='#e0e0e0', line_color='black', boxpoints='outliers', showlegend=True
            ))
            fig_box.add_trace(go.Scatter(
                x=radar_subj, y=radar_stu, mode='markers+lines+text', name='個人分數 (Student Score)',
                text=[f"{v:g}" for v in radar_stu], textposition='top center',
                marker=dict(color='#2c3e50', size=10, symbol='diamond'), line=dict(color='#2c3e50', width=2, dash='dot'),
                textfont=dict(color='black', size=13, family='Arial Black'), showlegend=True
            ))
            fig_box.update_layout(
                title=dict(text="全班成績分布與個人表現對比 (箱形圖)", font=dict(color='black')),
                yaxis=dict(title="分數", range=[0, 105], tickfont=dict(color='black')),
                xaxis=dict(tickfont=dict(color='black')),
                margin=dict(l=40, r=40, t=40, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                legend=dict(orientation="v", y=1, x=1.02, font=dict(color='black')) # Moved to Side
            )
            box_json = json.dumps(fig_box, cls=plotly.utils.PlotlyJSONEncoder)
            box_id = f"box_{stu_id}_{idx}"
            html_parts.append("<div class='chart-row'>")
            html_parts.append("""
                <div class='chart-desc'>
                    <h4>箱形圖落點</h4>
                    <p>箱形圖詳細展示了全班分數的分布區間。</p>
                    <p>圖中的箱體包含了班上中間 50% 學生的成績，箱體中間的線是中位數，上下延伸的線代表最高與最低分。</p>
                    <p><b>深色菱形標記</b>代表您的實際得分。這能讓您清楚知道自己的分數在全班整體分布中所處的相對高低位置。</p>
                </div>
            """)
            html_parts.append(f"<div id='{box_id}' class='chart-item'></div>")
            html_parts.append("</div>")
            html_parts.append(f"<script>var boxData_{idx} = {box_json}; Plotly.newPlot('{box_id}', boxData_{idx}.data, boxData_{idx}.layout, {{displayModeBar: false}});</script>")

        # HTML Bar Chart
        if "長條對比圖 (Bar Chart)" in chart_options and radar_subj:
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                name='學生分數', x=radar_subj, y=radar_stu, 
                marker_color='#2c3e50', text=[f"{v:g}" for v in radar_stu], textposition='auto',
                textfont=dict(color='white')
            ))
            fig_bar.add_trace(go.Bar(
                name='班級平均', x=radar_subj, y=radar_avg, 
                marker_color='#e0e0e0', text=[f"{v:.1f}" for v in radar_avg], textposition='auto',
                textfont=dict(color='black')
            ))
            fig_bar.update_layout(
                barmode='group',
                title=dict(text="個人與班級平均對比 (Bar Chart)", font=dict(color='black')),
                yaxis=dict(title="分數", range=[0, 105], tickfont=dict(color='black')),
                xaxis=dict(tickfont=dict(color='black')),
                margin=dict(l=40, r=40, t=40, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                legend=dict(orientation="v", y=1, x=1.02, font=dict(color='black')) # Moved to Side
            )
            bar_json = json.dumps(fig_bar, cls=plotly.utils.PlotlyJSONEncoder)
            bar_id = f"bar_{stu_id}_{idx}"
            html_parts.append("<div class='chart-row'>")
            html_parts.append("""
                <div class='chart-desc'>
                    <h4>長條對比圖</h4>
                    <p>以最直觀的方式並排比較您的各科表現。</p>
                    <p><b>深色長條</b>代表您的個人得分，<b>淺色長條</b>則是班級平均分。</p>
                    <p>您可以藉由柱狀的高度落差，快速掌握哪些科目的學習成效顯著，哪些科目可能需要調整學習策略。</p>
                </div>
            """)
            html_parts.append(f"<div id='{bar_id}' class='chart-item'></div>")
            html_parts.append("</div>")
            html_parts.append(f"<script>var barData_{idx} = {bar_json}; Plotly.newPlot('{bar_id}', barData_{idx}.data, barData_{idx}.layout, {{displayModeBar: false}});</script>")
        
        # HTML Distribution Chart
        if "分布長條圖 (Distribution Chart)" in chart_options and dist_chart_json:
            dist_id = f"dist_{stu_id}_{idx}"
            html_parts.append("<div class='chart-row'>")
            html_parts.append("""
                <div class='chart-desc'>
                    <h4>成績區間分布</h4>
                    <p>此圖表呈現了全班同學在各科目的成績集中趨勢。</p>
                    <p>不同顏色的區塊代表不同的 10 分級距 (例如：81-90分、91-100分)，柱狀上的數字代表落在該區間的人數。</p>
                    <p>對照您的得分，您可以評估該科目的考題難易度以及您在班上群體中的競爭力。</p>
                </div>
            """)
            html_parts.append(f"<div id='{dist_id}' class='chart-item'></div>")
            html_parts.append("</div>")
            html_parts.append(f"<script>var distData_{idx} = {dist_chart_json}; Plotly.newPlot('{dist_id}', distData_{idx}.data, distData_{idx}.layout, {{displayModeBar: false}});</script>")

        html_parts.append("</div></div>") 
        
    html_parts.append("</body></html>")
    return "".join(html_parts)

# --- Session State Initialization ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.is_virtual_account = False
    st.session_state.is_teacher = False
    st.session_state.student_data = pd.DataFrame()
    st.session_state.student_name = ""

# --- 2. Login Interface ---
st.markdown("請輸入學號與專屬密碼來查詢成績 (Please enter Student ID and PIN)")
default_id = st.query_params.get("id", "")

col1, col2 = st.columns(2)
with col1:
    user_id = st.text_input("學號 / 帳號 (ID)", value=default_id)
with col2:
    user_pin = st.text_input("密碼 (PIN)", type="password")

login_button = st.button("登入查詢 (Login)")

try: TEACHER_SECURE_PIN = str(st.secrets["teacher"]["pin"])
except: TEACHER_SECURE_PIN = None

try: VIRTUAL_SECURE_PIN = str(st.secrets["virtual"]["pin"])
except: VIRTUAL_SECURE_PIN = '777'

if login_button:
    is_virtual = (user_id == '777' and user_pin == VIRTUAL_SECURE_PIN)
    is_teacher = (user_id == '77777' and user_pin == TEACHER_SECURE_PIN and TEACHER_SECURE_PIN is not None)
    
    if is_teacher:
        st.session_state.logged_in, st.session_state.is_teacher, st.session_state.is_virtual_account = True, True, False
        st.session_state.student_data, st.session_state.student_name = df, "教師管理員"
    elif is_virtual:
        st.session_state.logged_in, st.session_state.is_teacher, st.session_state.is_virtual_account = True, False, True
        st.session_state.student_data, st.session_state.student_name = pd.DataFrame(), "班級總覽"
    else:
        s_data = df[(df['StudentID'] == user_id) & (df['Pin'] == user_pin)]
        if s_data.empty:
            st.error("學號或密碼錯誤，請重新確認。(Invalid ID or PIN.)")
            st.session_state.logged_in = False
        else:
            st.session_state.logged_in, st.session_state.is_teacher, st.session_state.is_virtual_account = True, False, False
            st.session_state.student_data, st.session_state.student_name = s_data, s_data.iloc[0]['Name']

# --- Main Application Logic ---
def render_dashboard():
    is_virtual = st.session_state.is_virtual_account
    is_teacher = st.session_state.is_teacher
    student_data = st.session_state.student_data
    
    # ==========================================
    # 👨‍🏫 TEACHER ADMIN PANEL
    # ==========================================
    if is_teacher:
        st.success("👨‍🏫 歡迎進入教師管理後台 (Teacher Admin Panel)！")
        
        # Split Teacher Mode into Tabs
        tab_t1, tab_t2, tab_t3 = st.tabs(["📊 成績總表與進退步 (Exam & Progress)", "🖨️ 批量產生報告 (Bulk Print)", "📥 原始資料匯出 (Raw Data)"])
        
        with tab_t1:
            st.subheader("🖨️ 產生特定考試的成績總表 (Generate Exam Transcripts)")
            selected_exam_teacher = st.selectbox("選擇考試 (Select Exam)", available_exams, key="teacher_exam_select")
            exam_specific_cols = col_info[col_info['Exam_Label'] == selected_exam_teacher]
            
            if not exam_specific_cols.empty:
                # Find previous exam
                try:
                    curr_idx = available_exams.index(selected_exam_teacher)
                    prev_exam_label = available_exams[curr_idx - 1] if curr_idx > 0 else None
                except ValueError:
                    prev_exam_label = None

                col_names_original = exam_specific_cols['Original_Col'].tolist()
                transcript_df = df[['StudentID', 'Name'] + col_names_original].dropna(subset=col_names_original, how='all').copy()
                rename_dict = {row['Original_Col']: row['Subject'] for idx, row in exam_specific_cols.iterrows()}
                transcript_df = transcript_df.rename(columns=rename_dict)
                
                # Progress Logic
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
                                    # For rank, negative diff means progressed (e.g. 5th to 2nd = +3 progress)
                                    diff = mapped_prev - curr_scores
                                else:
                                    diff = curr_scores - mapped_prev
                                
                                col_idx = transcript_df.columns.get_loc(subj)
                                transcript_df.insert(col_idx + 1, diff_col_name, diff)
                                diff_cols.append(diff_col_name)

                # Style Function to color progress
                def highlight_diff(val):
                    if pd.isna(val): return ''
                    if val > 0: return 'color: green; font-weight: bold;'
                    elif val < 0: return 'color: red; font-weight: bold;'
                    return 'color: gray;'
                
                # Apply style to difference columns
                styled_df = transcript_df.style.map(highlight_diff, subset=diff_cols) if diff_cols else transcript_df
                
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

        return

    # ==========================================
    # 🎓 STUDENT / PUBLIC DASHBOARD
    # ==========================================
    if is_virtual:
        st.success("歡迎進入 🏫 班級總覽模式 (Class Overview Mode)！")
    else:
        st.success(f"歡迎, {st.session_state.student_name} 的家長！")
        
    st.subheader("📌 選擇想查看的考試 (Select Exam)")
    selected_exam = st.selectbox("Exam", available_exams, label_visibility="collapsed")
    exam_all_cols = col_info[col_info['Exam_Label'] == selected_exam]
    
    if exam_all_cols.empty:
        st.warning("此考試尚未有成績資料 (No data available).")
        return

    # --- 學生個人的 HTML 專屬成績單下載區塊 ---
    if not is_virtual and not is_teacher:
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
                file_name=f"{selected_exam}_個人成績單_{st.session_state.student_name}.html", 
                mime="text/html"
            )

    tab1, tab2, tab3 = st.tabs(["📊 學習總覽 (Overview)", "🔬 深度數據分析 (Deep Analytics)", "📈 歷年趨勢 (Historical Trend)"])
    
    with tab1:
        st.markdown("### 🏆 本次考試表現 (Exam Summary)")
        kpi_cols = st.columns(4)
        
        # 尋找前一次考試 (計算進退步用)
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

            # Prepare Top % strings for appending UNDER the delta
            c_pct_str = f"(Top {(c_rank / c_total * 100):.1f}%)" if pd.notna(c_rank) and c_total > 0 else ""
            s_pct_str = f"(Top {(s_rank / 520 * 100):.1f}%)" if pd.notna(s_rank) else ""

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
            
            # Use contextual rendering to insert the Top % text BELOW the progress delta
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
            subj = row['Subject']          # Grab the subject
            col_name = row['Original_Col'] # Grab the column name
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
            col_chart1, col_chart2 = st.columns([3, 2])
            with col_chart1:
                st.write("**📊 班級各科平均表現**" if is_virtual else "**📊 成績對比圖 (Grouped Bar)**")
                if is_virtual:
                    fig_bar = px.bar(stats_df, x='科目 (Subject)', y='班級平均 (Class Avg)', text_auto='.1f', color_discrete_sequence=['#636EFA'])
                else:
                    melted_df = stats_df.melt(id_vars='科目 (Subject)', value_vars=['學生分數 (Score)', '班級平均 (Class Avg)'], var_name='類別 (Type)', value_name='分數 (Score)')
                    fig_bar = px.bar(melted_df, x='科目 (Subject)', y='分數 (Score)', color='類別 (Type)', barmode='group', text_auto='.1f')
                fig_bar.update_layout(margin=dict(l=0, r=0, t=30, b=0)) # Let standard Plotly vertical legend take over
                st.plotly_chart(fig_bar, use_container_width=True)
                
            with col_chart2:
                st.write("**🕸️ 班級能力雷達圖**" if is_virtual else "**🕸️ 能力雷達圖 (Radar Chart)**")
                fig_radar_web = go.Figure()
                if is_virtual:
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
                    legend=dict(orientation="v", y=1, x=1.02) # <--- Legend moved to the side
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
            
            fig_box_web.update_layout(yaxis=dict(title="分數", range=[0, 105]), margin=dict(l=40, r=40, t=30, b=20)) # Removed horizontal legend override
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
                fig_dist_web.update_layout(barmode='group', margin=dict(l=0, r=0, t=40, b=0)) # Standard right-side Plotly legend will apply naturally
                st.plotly_chart(fig_dist_web, use_container_width=True)

    with tab2:
        st.subheader(f"{selected_exam} - 深度數據分析 (Deep Statistical Breakdown)")
        st.markdown("* **排除0分平均:** 扣除缺考(0分)同學後的實際班級平均，更能反映真實難度。")
        if not stats_df.empty:
            if not is_virtual:
                st.markdown("* **Z分數 (Z-Score):** 大於 0 代表高於平均，大於 1 代表在班上屬於前段班。\n* **百分等級 (PR):** PR85 代表該生成績贏過班上 85% 的同學。")
                st.dataframe(stats_df.style.applymap(lambda x: 'color: green' if x > 0 else ('color: red' if x < 0 else ''), subset=['Z分數 (Z-Score)']), use_container_width=True, hide_index=True)
            else:
                st.dataframe(stats_df[['科目 (Subject)', '班級平均 (Class Avg)', '排除0分平均 (Adj Avg)', '班級最高 (Max)', '班級最低 (Min)', '中位數 (Median)', '標準差 (SD)']], use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("歷年表現趨勢圖 (Historical Performance Trend)")
        all_trackable = col_info['Subject'].unique().tolist()
        
        if is_virtual:
            track_options = []
            for opt in [s for s in all_trackable if s != '班排']:
                track_options.extend([opt, f"{opt} (排除後三名/Adj)", f"{opt} (前30%/Top 30%)", f"{opt} (中間40%/Mid 40%)", f"{opt} (後30%/Bottom 30%)"])
        else:
            track_options = all_trackable
            
        selected_track = st.selectbox("選擇追蹤項目 (Select Item to Track)", track_options)
        modifier, actual_subject = (selected_track.split(" (")[1].replace(")", ""), selected_track.split(" (")[0]) if "(" in selected_track else ("", selected_track)
        
        trend_data = []
        for index, row in col_info[col_info['Subject'] == actual_subject].iterrows():
            col_name, exam_label = row['Original_Col'], row['Exam_Label']
            class_scores = df[col_name].dropna()
            if class_scores.empty: continue
            
            target_scores = class_scores
            if is_virtual and len(class_scores) > 0 and modifier:
                sorted_scores = class_scores.sort_values(ascending=(actual_subject == '校排'))
                n, top_count = len(sorted_scores), max(1, int(len(sorted_scores) * 0.3))
                if modifier == "排除後三名/Adj" and n > 3: target_scores = sorted_scores.iloc[:-3]
                elif modifier == "前30%/Top 30%": target_scores = sorted_scores.iloc[:top_count]
                elif modifier == "中間40%/Mid 40%": target_scores = sorted_scores.iloc[top_count:-top_count]
                elif modifier == "後30%/Bottom 30%": target_scores = sorted_scores.iloc[-top_count:]

            class_avg = round(target_scores.mean(), 1) if not target_scores.empty else np.nan
            
            if is_virtual:
                trend_data.append({'考試 (Exam)': exam_label, f'班級平均 ({modifier if modifier else "Class Average"})': class_avg})
            else:
                student_score = student_data[col_name].iloc[0]
                if pd.notna(student_score):
                    trend_data.append({'考試 (Exam)': exam_label, '學生表現 (Student)': student_score, '班級平均 (Class Average)': class_avg if actual_subject != '班排' else np.nan})
        
        if trend_data:
            trend_df = pd.DataFrame(trend_data)
            if is_virtual:
                y_col = f'班級平均 ({modifier if modifier else "Class Average"})'
                fig_trend = px.line(trend_df, x='考試 (Exam)', y=y_col, markers=True, text=y_col)
                if actual_subject == '校排': fig_trend.update_yaxes(autorange="reversed") 
                fig_trend.update_traces(textposition="bottom right")
            else:
                if actual_subject == '班排':
                    fig_trend = px.line(trend_df, x='考試 (Exam)', y='學生表現 (Student)', markers=True, text='學生表現 (Student)')
                    fig_trend.update_yaxes(autorange="reversed")
                elif actual_subject == '校排':
                    fig_trend = px.line(trend_df.melt(id_vars='考試 (Exam)', value_vars=['學生表現 (Student)', '班級平均 (Class Average)'], var_name='Type', value_name='Rank'), x='考試 (Exam)', y='Rank', color='Type', markers=True)
                    fig_trend.update_yaxes(autorange="reversed")
                else:
                    fig_trend = px.line(trend_df.melt(id_vars='考試 (Exam)', value_vars=['學生表現 (Student)', '班級平均 (Class Average)'], var_name='Type', value_name='Score'), x='考試 (Exam)', y='Score', color='Type', markers=True)
            st.plotly_chart(fig_trend, use_container_width=True)
            st.dataframe(trend_df.set_index('考試 (Exam)'), use_container_width=True)
        else:
            st.info("尚無足夠的歷史資料可供繪圖 (Not enough historical data).")

if st.session_state.logged_in:
    render_dashboard()