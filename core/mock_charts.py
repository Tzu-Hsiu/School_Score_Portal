"""
core/mock_charts.py
--------------------
Interactive Plotly visualizations designed specifically for Taiwan CAP Mock Exams
(國中教育會考模擬考), including radar charts, score distribution curves,
teacher cohort distributions, and regular vs mock exam comparisons.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Dict, Any, Optional


def create_mock_radar_chart(
    subjects: List[str],
    student_points: Optional[List[float]],
    class_avg_points: List[float],
    school_avg_points: Optional[List[float]] = None
) -> go.Figure:
    """
    Radar chart comparing student points vs class average vs school average
    on the 7-point scale (A++=7 ... C=1).
    """
    fig = go.Figure()

    # School average (Teal)
    if school_avg_points and len(school_avg_points) == len(subjects):
        fig.add_trace(go.Scatterpolar(
            r=school_avg_points,
            theta=subjects,
            name='校平均 (School Avg)',
            line=dict(color='#00CC96', width=2, dash='dash'),
            fill='none'
        ))

    # Class average (Blue)
    fig.add_trace(go.Scatterpolar(
        r=class_avg_points,
        theta=subjects,
        name='班級平均 (Class Avg)',
        line=dict(color='#636EFA', width=2),
        fill='toself',
        fillcolor='rgba(99, 110, 250, 0.15)'
    ))

    # Student points (Coral / Red)
    if student_points and len(student_points) == len(subjects):
        fig.add_trace(go.Scatterpolar(
            r=student_points,
            theta=subjects,
            name='個人積分 (Student)',
            line=dict(color='#FF4B4B', width=3),
            fill='toself',
            fillcolor='rgba(255, 75, 75, 0.25)',
            marker=dict(size=8, symbol='circle')
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 7.5],
                tickvals=[1, 2, 3, 4, 5, 6, 7],
                ticktext=['1 (C)', '2 (B)', '3 (B+)', '4 (B++)', '5 (A)', '6 (A+)', '7 (A++)'],
                gridcolor='rgba(128, 128, 128, 0.25)'
            ),
            angularaxis=dict(gridcolor='rgba(128, 128, 128, 0.25)')
        ),
        margin=dict(l=45, r=45, t=45, b=35),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.08,
            xanchor="center",
            x=0.5,
            font=dict(size=11)
        )
    )
    return fig


def create_mock_points_distribution_chart(
    points_dist: List[Dict[str, Any]],
    student_points: Optional[float] = None
) -> go.Figure:
    """
    Interactive curve of total points distribution (0 to 35) showing
    Class, School, and District cumulative percentages with the student's exact standing.
    """
    fig = go.Figure()
    if not points_dist:
        return fig

    df_dist = pd.DataFrame(points_dist).sort_values(by='points')

    # District Cumulative Top %
    if 'district_top_pct' in df_dist.columns:
        fig.add_trace(go.Scatter(
            x=df_dist['points'],
            y=df_dist['district_top_pct'],
            mode='lines',
            name='全區前 %',
            line=dict(color='#FFA15A', width=2, dash='dot')
        ))

    # School Cumulative Top %
    if 'school_top_pct' in df_dist.columns:
        fig.add_trace(go.Scatter(
            x=df_dist['points'],
            y=df_dist['school_top_pct'],
            mode='lines+markers',
            name='全校前 %',
            line=dict(color='#00CC96', width=2.5)
        ))

    # Class Cumulative Top %
    if 'class_top_pct' in df_dist.columns:
        fig.add_trace(go.Scatter(
            x=df_dist['points'],
            y=df_dist['class_top_pct'],
            mode='lines+markers',
            name='班級前 %',
            line=dict(color='#636EFA', width=3)
        ))

    # Highlight student point
    if student_points is not None:
        match_row = df_dist[df_dist['points'] == student_points]
        sch_pct = match_row['school_top_pct'].values[0] if not match_row.empty else None

        annotation_text = f"落點: {student_points:g} 分"
        if sch_pct is not None:
            annotation_text += f"<br>全校前 {sch_pct:.1f}%"

        fig.add_vline(
            x=student_points,
            line_width=2,
            line_dash="dash",
            line_color="#FF4B4B",
            annotation_text=annotation_text,
            annotation_position="top left",
            annotation_font=dict(color="#FF4B4B", size=11)
        )

    fig.update_layout(
        title=dict(text="五科總積分累積百分比落點曲線", x=0, xanchor="left", font=dict(size=14)),
        xaxis_title="五科總積分 (Points)",
        yaxis_title="累積前 % (越低越頂尖)",
        margin=dict(l=40, r=40, t=45, b=65),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.22,
            xanchor="center",
            x=0.5,
            font=dict(size=11)
        )
    )
    return fig


def create_mock_subject_bars(
    subject_details: List[Dict[str, Any]],
    metric: str = 'points'  # 'points' or 'diff_from_class'
) -> go.Figure:
    """Grouped bar chart comparing student performance across subjects."""
    fig = go.Figure()
    subjects = [d['subject'] for d in subject_details]

    if metric == 'points':
        stu_pts = [d.get('points', 0) for d in subject_details]
        cls_pts = [d.get('class_avg_points', 0) for d in subject_details]
        sch_pts = [d.get('school_avg_points', 0) for d in subject_details]

        fig.add_trace(go.Bar(
            name='學生積分', x=subjects, y=stu_pts,
            marker_color='#FF4B4B', text=[f"{v:g}" for v in stu_pts], textposition='auto'
        ))
        fig.add_trace(go.Bar(
            name='班級平均', x=subjects, y=cls_pts,
            marker_color='#636EFA', text=[f"{v:.1f}" for v in cls_pts], textposition='auto'
        ))
        fig.add_trace(go.Bar(
            name='全校平均', x=subjects, y=sch_pts,
            marker_color='#00CC96', text=[f"{v:.1f}" for v in sch_pts], textposition='auto'
        ))
        fig.update_layout(
            barmode='group',
            yaxis=dict(title="積分", range=[0, 7.5]),
            margin=dict(l=25, r=25, t=30, b=55)
        )
    else:
        diff_cls = [d.get('diff_from_class', 0) for d in subject_details]
        diff_sch = [d.get('diff_from_school', 0) for d in subject_details]

        fig.add_trace(go.Bar(
            name='領先/落後班平均', x=subjects, y=diff_cls,
            marker_color=['#2ecc71' if v >= 0 else '#e74c3c' for v in diff_cls],
            text=[f"{v:+.2f}" for v in diff_cls], textposition='auto'
        ))
        fig.add_trace(go.Bar(
            name='領先/落後校平均', x=subjects, y=diff_sch,
            marker_color=['#27ae60' if v >= 0 else '#c0392b' for v in diff_sch],
            text=[f"{v:+.2f}" for v in diff_sch], textposition='auto'
        ))
        fig.update_layout(
            barmode='group',
            yaxis=dict(title="差距 (積分)"),
            margin=dict(l=25, r=25, t=30, b=55)
        )

    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.20,
            xanchor="center",
            x=0.5,
            font=dict(size=11)
        )
    )
    return fig


def create_cohort_combos_chart(level_combos: Dict[str, Dict[str, int]]) -> go.Figure:
    """Visualizes 5A, 4A1B, 3A2B ... level combo distributions across Class, School, District."""
    if not level_combos:
        return go.Figure()

    valid_combos = [k for k, v in level_combos.items() if v.get('school', 0) > 0 or v.get('class', 0) > 0]
    top_combos = valid_combos[:10]

    cls_pcts = []
    sch_pcts = []
    dst_pcts = []

    for c in top_combos:
        c_info = level_combos[c]
        cls_pcts.append(round((c_info.get('class', 0) / 27) * 100, 1))
        sch_pcts.append(round((c_info.get('school', 0) / 516) * 100, 1))
        dst_pcts.append(round((c_info.get('district', 0) / 58502) * 100, 1))

    fig = go.Figure()
    fig.add_trace(go.Bar(name='本班 %', x=top_combos, y=cls_pcts, marker_color='#636EFA', text=[f"{v}%" for v in cls_pcts], textposition='auto'))
    fig.add_trace(go.Bar(name='全校 %', x=top_combos, y=sch_pcts, marker_color='#00CC96', text=[f"{v}%" for v in sch_pcts], textposition='auto'))
    fig.add_trace(go.Bar(name='全區 %', x=top_combos, y=dst_pcts, marker_color='#FFA15A', text=[f"{v}%" for v in dst_pcts], textposition='auto'))

    fig.update_layout(
        title=dict(text="五科標示組合分布比例 (全班 vs 全校 vs 全區)", x=0, xanchor="left", font=dict(size=14)),
        barmode='group',
        yaxis=dict(title="佔比 (%)"),
        xaxis=dict(tickangle=-25),
        margin=dict(l=25, r=25, t=40, b=65),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.25,
            xanchor="center",
            x=0.5,
            font=dict(size=11)
        )
    )
    return fig


def create_subject_tiers_chart(subject_tiers: Dict[str, Dict[str, Dict[str, int]]]) -> go.Figure:
    """Stacked bar chart showing 精熟 / 基礎 / 待加強 distribution per subject."""
    if not subject_tiers:
        return go.Figure()

    subjects = list(subject_tiers.keys())
    tier_a = []
    tier_b = []
    tier_c = []

    for s in subjects:
        c_counts = subject_tiers[s].get('class', {})
        tot = sum(c_counts.values()) or 27
        tier_a.append(round((c_counts.get('精熟', 0) / tot) * 100, 1))
        tier_b.append(round((c_counts.get('基礎', 0) / tot) * 100, 1))
        tier_c.append(round((c_counts.get('待加強', 0) / tot) * 100, 1))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='精熟 (A)', x=subjects, y=tier_a,
        marker_color='#2ecc71', text=[f"{v}%" for v in tier_a], textposition='auto'
    ))
    fig.add_trace(go.Bar(
        name='基礎 (B)', x=subjects, y=tier_b,
        marker_color='#f39c12', text=[f"{v}%" for v in tier_b], textposition='auto'
    ))
    fig.add_trace(go.Bar(
        name='待加強 (C)', x=subjects, y=tier_c,
        marker_color='#e74c3c', text=[f"{v}%" for v in tier_c], textposition='auto'
    ))

    fig.update_layout(
        title=dict(text="班級各科三等級比例分布", x=0, xanchor="left", font=dict(size=14)),
        barmode='stack',
        yaxis=dict(title="百分比 (%)", range=[0, 100]),
        margin=dict(l=25, r=25, t=40, b=55),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.20,
            xanchor="center",
            x=0.5,
            font=dict(size=11)
        )
    )
    return fig
