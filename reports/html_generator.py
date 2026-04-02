import pandas as pd
import numpy as np
import json
import plotly.express as px
import plotly.graph_objects as go
import plotly.utils

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
                legend=dict(orientation="v", y=1, x=1.02, font=dict(color='black')),
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
        crank_top_html = f"<div class='kpi-top-pct'>(Top {(curr_crank_val / c_total_html) * 100:.1f}%)</div>" if pd.notna(curr_crank_val) and c_total_html > 0 else ""

        srank_base = f"{curr_srank_val:g} / 520" if pd.notna(curr_srank_val) else '-'
        srank_top_html = f"<div class='kpi-top-pct'>(Top {(curr_srank_val / 520) * 100:.1f}%)</div>" if pd.notna(curr_srank_val) else ""
        
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
        
        # HTML Radar Chart
        if "雷達圖 (Radar Chart)" in chart_options and radar_subj:
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(r=radar_avg, theta=radar_subj, fill='toself', name='班級平均', line_color='gray'))
            fig_radar.add_trace(go.Scatterpolar(r=radar_stu, theta=radar_subj, fill='toself', name='個人分數', line_color='#2c3e50'))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                title=dict(text="能力雷達圖 (Radar Chart)", font=dict(color='black')),
                margin=dict(l=40, r=40, t=40, b=20),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                legend=dict(orientation="v", y=1, x=1.02, font=dict(color='black')) 
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
                legend=dict(orientation="v", y=1, x=1.02, font=dict(color='black')) 
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
                legend=dict(orientation="v", y=1, x=1.02, font=dict(color='black')) 
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
