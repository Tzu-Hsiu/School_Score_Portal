import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.constants import SCORE_BIN_LABELS

def create_radar_chart(subjects, student_scores, class_averages, for_print=False):
    fig = go.Figure()
    student_color = '#2c3e50' if for_print else '#FF4B4B'
    avg_color = 'gray' if for_print else '#636EFA'

    if for_print:
        fig.add_trace(go.Scatterpolar(r=class_averages, theta=subjects, fill='toself', name='班級平均', line_color=avg_color))
        if student_scores:
            fig.add_trace(go.Scatterpolar(r=student_scores, theta=subjects, fill='toself', name='個人分數', line_color=student_color))
    else:
        if student_scores:
            fig.add_trace(go.Scatterpolar(r=student_scores, theta=subjects, fill='toself', name='學生分數', line_color=student_color))
        fig.add_trace(go.Scatterpolar(r=class_averages, theta=subjects, fill='toself', name='班級平均', line_color=avg_color))
    
    font_dict = dict(color='black') if for_print else dict()
    bg_color = 'rgba(0,0,0,0)'
    
    layout_args = dict(
        polar=dict(
            bgcolor=bg_color,
            radialaxis=dict(visible=True, range=[0, 100], gridcolor='rgba(128, 128, 128, 0.3)'),
            angularaxis=dict(gridcolor='rgba(128, 128, 128, 0.3)')
        ),
        margin=dict(l=40, r=40, t=40 if for_print else 30, b=20 if for_print else 30),
        legend=dict(orientation="v", y=1, x=1.02)
    )
    if for_print:
        layout_args['title'] = dict(text="能力雷達圖 (Radar Chart)", font=font_dict)
        layout_args['paper_bgcolor'] = bg_color
        layout_args['plot_bgcolor'] = bg_color
        layout_args['legend']['font'] = font_dict
        
    fig.update_layout(**layout_args)
    return fig

def create_box_plot(box_x, box_y, student_subjects=None, student_scores=None, for_print=False):
    fig = go.Figure()
    box_color = '#e0e0e0' if for_print else None
    line_color = 'black' if for_print else None
    
    fig.add_trace(go.Box(
        x=box_x, y=box_y, name='班級分布 (Class Dist.)', boxpoints='outliers',
        marker_color=box_color, line_color=line_color, showlegend=for_print or (student_subjects is not None)
    ))
    
    if student_subjects and student_scores:
        marker_color = '#2c3e50' if for_print else '#FF4B4B'
        text_font = dict(color='black', size=13, family='Arial Black') if for_print else dict(size=13, family='Arial Black')
        fig.add_trace(go.Scatter(
            x=student_subjects, y=student_scores, mode='markers+lines+text', name='個人分數 (Student Score)',
            text=[f"{v:g}" for v in student_scores], textposition='top center',
            marker=dict(color=marker_color, size=10, symbol='diamond'),
            line=dict(color=marker_color, width=2, dash='dot'), textfont=text_font, showlegend=True
        ))
    
    font_dict = dict(color='black') if for_print else dict()
    bg_color = 'rgba(0,0,0,0)'

    layout_args = dict(
        yaxis=dict(title="分數", range=[0, 105]),
        margin=dict(l=40, r=40, t=40 if for_print else 30, b=20)
    )
    
    if for_print:
        layout_args['title'] = dict(text="全班成績分布與個人表現對比 (箱形圖)", font=font_dict)
        layout_args['yaxis']['tickfont'] = font_dict
        layout_args['xaxis'] = dict(tickfont=font_dict)
        layout_args['paper_bgcolor'] = bg_color
        layout_args['plot_bgcolor'] = bg_color
        layout_args['legend'] = dict(orientation="v", y=1, x=1.02, font=font_dict)
        
    fig.update_layout(**layout_args)
    return fig

def create_grouped_bar_chart(stats_df, is_virtual, for_print=False):
    fig = go.Figure()
    if is_virtual and not for_print:
        # Just class average
        fig = px.bar(stats_df, x='科目 (Subject)', y='班級平均 (Class Avg)', text_auto='.1f', color_discrete_sequence=['#636EFA'])
        fig.update_layout(margin=dict(l=0, r=0, t=30, b=0))
        return fig
        
    subjects = stats_df['科目 (Subject)'].tolist()
    class_avgs = stats_df['班級平均 (Class Avg)'].tolist()
    student_scores = stats_df['學生分數 (Score)'].tolist() if '學生分數 (Score)' in stats_df.columns else []

    if for_print:
        fig.add_trace(go.Bar(
            name='學生分數', x=subjects, y=student_scores, 
            marker_color='#2c3e50', text=[f"{v:g}" for v in student_scores], textposition='auto',
            textfont=dict(color='white')
        ))
        fig.add_trace(go.Bar(
            name='班級平均', x=subjects, y=class_avgs, 
            marker_color='#e0e0e0', text=[f"{v:.1f}" for v in class_avgs], textposition='auto',
            textfont=dict(color='black')
        ))
        
        font_dict = dict(color='black')
        bg_color = 'rgba(0,0,0,0)'
        fig.update_layout(
            barmode='group',
            title=dict(text="個人與班級平均對比 (Bar Chart)", font=font_dict),
            yaxis=dict(title="分數", range=[0, 105], tickfont=font_dict),
            xaxis=dict(tickfont=font_dict),
            margin=dict(l=40, r=40, t=40, b=20), paper_bgcolor=bg_color, plot_bgcolor=bg_color,
            legend=dict(orientation="v", y=1, x=1.02, font=font_dict)
        )
    else:
        melted_df = stats_df.melt(id_vars='科目 (Subject)', value_vars=['學生分數 (Score)', '班級平均 (Class Avg)'], var_name='類別 (Type)', value_name='分數 (Score)')
        fig = px.bar(melted_df, x='科目 (Subject)', y='分數 (Score)', color='類別 (Type)', barmode='group', text_auto='.1f')
        fig.update_layout(margin=dict(l=0, r=0, t=30, b=0))

    return fig

def create_distribution_chart(dist_dict, subjects, for_print=False):
    # dist_dict format: {subject: [count1, count2, ...]}
    # SCORE_BIN_LABELS: length 10
    
    if for_print:
        fig = go.Figure()
        colors = ['#ffffff', '#f8f9fa', '#f1f3f5', '#e9ecef', '#dee2e6', 
                  '#ced4da', '#adb5bd', '#999999', '#888888', '#777777']
        active_labels_idx = [i for i, label in enumerate(SCORE_BIN_LABELS) if any(dist_dict[subj][i] > 0 for subj in subjects if subj in dist_dict)]
              
        for idx in active_labels_idx:
            label = SCORE_BIN_LABELS[idx]
            y_vals = [dist_dict[subj][idx] if subj in dist_dict else 0 for subj in subjects]
            text_vals = [str(v) if v > 0 else "" for v in y_vals]
            
            fig.add_trace(go.Bar(
                name=label, x=subjects, y=y_vals, 
                text=text_vals, textposition='outside', cliponaxis=False,             
                textfont=dict(color='black', size=13, family='Arial Black'),
                marker=dict(color=colors[idx], line=dict(color='black', width=0.8))
            ))
            
        fig.update_layout(
            barmode='group',                  
            title=dict(text="全班各科成績區間分布人數", font=dict(color='black')), 
            margin=dict(l=40, r=40, t=40, b=20), 
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation="v", y=1, x=1.02, font=dict(color='black')),
            yaxis=dict(showgrid=True, gridcolor='#dddddd', tickfont=dict(color='black')),
            xaxis=dict(tickfont=dict(color='black'))
        )
        return fig
    else:
        dist_df = pd.DataFrame(dist_dict, index=SCORE_BIN_LABELS).T
        melted_dist = dist_df.reset_index().melt(id_vars='index', var_name='成績區間 (Range)', value_name='人數 (Count)')
        melted_dist.rename(columns={'index': '科目 (Subject)'}, inplace=True)
        
        fig = px.bar(melted_dist[melted_dist['人數 (Count)'] > 0], x='科目 (Subject)', y='人數 (Count)', color='成績區間 (Range)', 
                          title="各科目分數區間分布圖 (Grouped Bar)", text_auto=True, color_discrete_sequence=px.colors.sequential.Teal)
        fig.update_traces(textposition='outside', cliponaxis=False) 
        fig.update_layout(barmode='group', margin=dict(l=0, r=0, t=40, b=0))
        return fig
