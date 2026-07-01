import pandas as pd
import numpy as np
import json
import plotly.utils
from jinja2 import Environment, FileSystemLoader
from core.charts import create_radar_chart, create_box_plot, create_grouped_bar_chart, create_distribution_chart
from core.constants import DEFAULT_SCHOOL_TOTAL_STUDENTS, SCORE_BINS, SCORE_BIN_LABELS
import streamlit as st

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
    dist_dict = {}
    
    box_x, box_y = [], []
    subjects_list = []
    
    for _, row in s_cols.iterrows():
        c_name = row['Original_Col']
        subj = row['Subject']
        scores = df_source_class[c_name].dropna()
        subjects_list.append(subj)
        
        c_stats[c_name] = {
            'Subject': subj,
            'Mean': scores.mean() if not scores.empty else 0,
            'Adj_Mean': scores[scores > 0].mean() if not scores[scores > 0].empty else np.nan, 
            'Std': scores.std() if not scores.empty else 0,
            'Scores': scores
        }
        if not scores.empty:
            dist_dict[subj] = pd.cut(scores, bins=SCORE_BINS, labels=SCORE_BIN_LABELS).value_counts().reindex(SCORE_BIN_LABELS, fill_value=0).tolist()
            box_x.extend([subj] * len(scores))
            box_y.extend(scores.tolist())
            
    # 3. HTML Score Distribution Grouped Bar Chart
    dist_chart_json = None
    if "分布長條圖 (Distribution Chart)" in chart_options and dist_dict:
        fig_dist = create_distribution_chart(dist_dict, subjects_list, for_print=True)
        dist_chart_json = json.dumps(fig_dist, cls=plotly.utils.PlotlyJSONEncoder)

    exam_col_names = e_cols['Original_Col'].tolist()
    valid_students = df_source_student.dropna(subset=exam_col_names, how='all')
    
    school_total = st.secrets.get("school", {}).get("total_students", DEFAULT_SCHOOL_TOTAL_STUDENTS)

    def get_prog_html(curr, prev, is_rank=False):
        if pd.isna(curr) or pd.isna(prev): return ""
        diff = round(prev - curr if is_rank else curr - prev, 2)
        unit = "名" if is_rank else "分"
        if diff > 0: return f"<div class='kpi-prog' style='color: green;'>▲ {diff:g} {unit}</div>"
        elif diff < 0: return f"<div class='kpi-prog' style='color: red;'>▼ {abs(diff):g} {unit}</div>"
        else: return f"<div class='kpi-prog' style='color: gray;'>-</div>"
    
    students_data = []

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
        crank_top_html = f"<div class='kpi-top-pct'>(Top {(curr_crank_val / c_total_html) * 100:.1f}%)</div>" if pd.notna(curr_crank_val) and c_total_html > 0 else ""

        srank_base = f"{curr_srank_val:g} / {school_total}" if pd.notna(curr_srank_val) else '-'
        srank_top_html = f"<div class='kpi-top-pct'>(Top {(curr_srank_val / school_total) * 100:.1f}%)</div>" if pd.notna(curr_srank_val) else ""
        
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

        kpis = [
            {'title': '總分', 'value': tot, 'progress_html': tot_prog_html},
            {'title': '平均', 'value': avg, 'progress_html': avg_prog_html},
            {'title': '班級排名', 'value': crank_base, 'progress_html': crank_prog_html + crank_top_html},
            {'title': '校排', 'value': srank_base, 'progress_html': srank_prog_html + srank_top_html}
        ]
        
        radar_subj, radar_stu, radar_avg = [], [], []
        score_rows = []
        
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

                score_rows.append({
                    'subject': subj,
                    'score': f"{score:g}",
                    'mean': f"{mean:.1f}",
                    'adj_mean': adj_mean_str,
                    'progression_html': progression_html,
                    'z_color': z_color,
                    'z_score': f"{z_score:.2f}",
                    'pr': f"{pr:.1f}"
                })
                
                radar_subj.append(subj)
                radar_stu.append(score)
                radar_avg.append(mean)
        
        charts = []
        
        # HTML Radar Chart
        if "雷達圖 (Radar Chart)" in chart_options and radar_subj:
            fig_radar = create_radar_chart(radar_subj, radar_stu, radar_avg, for_print=True)
            radar_json = json.dumps(fig_radar, cls=plotly.utils.PlotlyJSONEncoder)
            radar_id = f"radar_{stu_id}_{idx}"
            charts.append({
                'id': radar_id,
                'json': radar_json,
                'description': '''
                    <h4>雷達圖分析</h4>
                    <p>雷達圖能直觀呈現您在各科目的均衡度。</p>
                    <p><b>灰色區域</b>代表班級的平均表現，而<b>深色實線</b>則是您的個人成績。</p>
                    <p>當深色線條超出灰色區域時，代表您在該科目表現優於班級平均，是您的優勢科目！若凹陷於灰色區域內，則可作為未來加強的參考。</p>
                '''
            })
            
        # HTML Box Plot
        if "箱形圖 (Box Plot)" in chart_options and radar_subj:
            fig_box = create_box_plot(box_x, box_y, radar_subj, radar_stu, for_print=True)
            box_json = json.dumps(fig_box, cls=plotly.utils.PlotlyJSONEncoder)
            box_id = f"box_{stu_id}_{idx}"
            charts.append({
                'id': box_id,
                'json': box_json,
                'description': '''
                    <h4>箱形圖落點</h4>
                    <p>箱形圖詳細展示了全班分數的分布區間。</p>
                    <p>圖中的箱體包含了班上中間 50% 學生的成績，箱體中間的線是中位數，上下延伸的線代表最高與最低分。</p>
                    <p><b>深色菱形標記</b>代表您的實際得分。這能讓您清楚知道自己的分數在全班整體分布中所處的相對高低位置。</p>
                '''
            })

        # HTML Bar Chart
        if "長條對比圖 (Bar Chart)" in chart_options and radar_subj:
            # To use grouped bar chart, we need a stats_df structure, but we can reconstruct it
            # since create_grouped_bar_chart needs stats_df.
            stats_list = []
            for s, st_sc, av in zip(radar_subj, radar_stu, radar_avg):
                stats_list.append({'科目 (Subject)': s, '學生分數 (Score)': st_sc, '班級平均 (Class Avg)': av})
            
            fig_bar = create_grouped_bar_chart(pd.DataFrame(stats_list), is_virtual=False, for_print=True)
            bar_json = json.dumps(fig_bar, cls=plotly.utils.PlotlyJSONEncoder)
            bar_id = f"bar_{stu_id}_{idx}"
            charts.append({
                'id': bar_id,
                'json': bar_json,
                'description': '''
                    <h4>長條對比圖</h4>
                    <p>以最直觀的方式並排比較您的各科表現。</p>
                    <p><b>深色長條</b>代表您的個人得分，<b>淺色長條</b>則是班級平均分。</p>
                    <p>您可以藉由柱狀的高度落差，快速掌握哪些科目的學習成效顯著，哪些科目可能需要調整學習策略。</p>
                '''
            })
        
        # HTML Distribution Chart
        if "分布長條圖 (Distribution Chart)" in chart_options and dist_chart_json:
            dist_id = f"dist_{stu_id}_{idx}"
            charts.append({
                'id': dist_id,
                'json': dist_chart_json,
                'description': '''
                    <h4>成績區間分布</h4>
                    <p>此圖表呈現了全班同學在各科目的成績集中趨勢。</p>
                    <p>不同顏色的區塊代表不同的 10 分級距 (例如：81-90分、91-100分)，柱狀上的數字代表落在該區間的人數。</p>
                    <p>對照您的得分，您可以評估該科目的考題難易度以及您在班上群體中的競爭力。</p>
                '''
            })

        students_data.append({
            'name': stu_name,
            'id': stu_id,
            'kpis': kpis,
            'score_rows': score_rows,
            'charts': charts
        })
        
    env = Environment(loader=FileSystemLoader('reports/templates'))
    template = env.get_template('report_card.html')
    return template.render(
        exam_label=exam_label,
        prev_exam_label=prev_exam_label,
        students=students_data
    )
