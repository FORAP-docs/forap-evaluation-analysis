from __future__ import annotations

import math
import textwrap

import pandas as pd
import plotly.graph_objects as go


SCORE_COLORS = {
    1: "#c85a0a",
    2: "#f6c6a5",
    3: "#d0d0d0",
    4: "#adc3e6",
    5: "#315a9b",
}
SCALE_LABELS = {
    "agreement": {
        1: "Strongly Disagree",
        2: "Disagree",
        3: "Neutral",
        4: "Agree",
        5: "Strongly Agree",
    },
    "usefulness": {
        1: "Not useful",
        2: "Slightly useful",
        3: "Moderately useful",
        4: "Very useful",
        5: "Extremely useful",
    },
    "effectiveness": {
        1: "Not effective",
        2: "Slightly effective",
        3: "Moderately effective",
        4: "Very effective",
        5: "Extremely effective",
    },
}

EXPERIENCE_ACTIVITIES = {
    "pjbl_taught": "Teaching",
    "pjbl_researched": "Research",
    "pjbl_designed": "Design",
    "pjbl_adopted": "Adoption",
    "pjbl_assessed": "Assessment",
}
EXPERIENCE_EXPORT_CONFIG = {
    "displaylogo": False,
    "toImageButtonOptions": {
        "format": "png", "filename": "pjbl_experience",
        "width": 850, "height": 420, "scale": 3,
    },
}


def pjbl_experience_figure(frame: pd.DataFrame) -> go.Figure:
    """Preserve all four levels, with combined percentages on each side."""
    labels = list(EXPERIENCE_ACTIVITIES.values())
    counts = pd.DataFrame(
        [pd.to_numeric(frame[key], errors="coerce").value_counts()
         for key in EXPERIENCE_ACTIVITIES],
        index=labels,
    ).reindex(columns=range(4), fill_value=0).fillna(0)
    totals = counts.sum(axis=1)
    percentages = counts.div(totals.replace(0, float("nan")), axis=0).fillna(0) * 100
    lower = percentages[0] + percentages[1]
    higher = percentages[2] + percentages[3]
    bases = [-lower, -percentages[1], higher * 0, percentages[2]]
    figure = go.Figure()
    for score, (name, color) in enumerate(zip(
        ["None", "Limited", "Moderate", "Extensive"],
        [SCORE_COLORS[i] for i in (1, 2, 4, 5)],
    )):
        figure.add_bar(
            y=labels, x=percentages[score].tolist(), base=bases[score].tolist(),
            name=name, orientation="h",
            marker=dict(color=color, line=dict(color="white", width=1)),
            customdata=[[int(counts.loc[label, score]), int(totals[label])]
                        for label in labels],
            hovertemplate=(f"%{{y}}<br>{name}: %{{x:.1f}}% "
                           "(%{customdata[0]} of %{customdata[1]} responses)<extra></extra>"),
        )
    for label in labels:
        if not totals[label]:
            figure.add_annotation(x=0, y=label, text="No responses", showarrow=False)
            continue
        for value, position, anchor, shift, color in (
            (lower[label], -lower[label], "right", -6, SCORE_COLORS[1]),
            (higher[label], higher[label], "left", 6, SCORE_COLORS[5]),
        ):
            figure.add_annotation(
                x=float(position), y=label, text=f"{value:.0f}%", showarrow=False,
                xanchor=anchor, xshift=shift, font=dict(size=19, color=color),
            )
    for text, anchor, shift, color in (
        ("None / Limited", "right", -8, SCORE_COLORS[1]),
        ("Moderate / Extensive", "left", 8, SCORE_COLORS[5]),
    ):
        figure.add_annotation(
            x=0, y=1.045, yref="paper", text=text, showarrow=False,
            xanchor=anchor, xshift=shift, font=dict(size=16, color=color),
        )
    left_limit = max(20, math.ceil(float(lower.max()) / 10) * 10 + 15)
    right_limit = max(20, math.ceil(float(higher.max()) / 10) * 10 + 15)
    ticks = [value for value in range(-100, 101, 20)
             if -left_limit <= value <= right_limit]
    figure.add_vline(x=0, line_width=2, line_dash="dot", line_color="#161616")
    figure.update_layout(
        template="none", barmode="overlay", height=420, bargap=0.34,
        font=dict(family="Arial", size=19, color="#161616"),
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=125, r=12, t=86, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.17,
                    xanchor="center", x=0.5, font=dict(size=18),
                    itemclick=False, itemdoubleclick=False),
    )
    figure.update_xaxes(
        range=[-left_limit, right_limit], tickvals=ticks,
        ticktext=[f"{abs(value)}%" for value in ticks],
        tickfont=dict(size=15), showgrid=False, zeroline=False,
        showline=True, linecolor="#161616", ticks="outside", fixedrange=True,
    )
    figure.update_yaxes(autorange="reversed", showgrid=False, fixedrange=True)
    return figure


def divergent_likert_figure(dist: pd.DataFrame, construct: str, scale: str) -> go.Figure:
    """Build an asymmetric divergent Likert chart with the midpoint split at zero."""
    items = list(dict.fromkeys(dist["item"]))
    display_items = ["<br>".join(textwrap.wrap(item, width=42)) for item in items]
    percentages = (
        dist.pivot(index="item", columns="score", values="percent")
        .reindex(index=items, columns=range(1, 6), fill_value=0)
        .fillna(0)
    )
    counts = (
        dist.pivot(index="item", columns="score", values="count")
        .reindex(index=items, columns=range(1, 6), fill_value=0)
        .fillna(0)
    )
    labels = SCALE_LABELS.get(scale, {score: str(score) for score in range(1, 6)})
    neutral_half = percentages[3] / 2
    segments = (
        (1, percentages[1], -(percentages[1] + percentages[2] + neutral_half), True, percentages[1]),
        (2, percentages[2], -(percentages[2] + neutral_half), True, percentages[2]),
        (3, neutral_half, -neutral_half, True, percentages[3]),
        (3, neutral_half, pd.Series(0.0, index=items), False, percentages[3]),
        (4, percentages[4], neutral_half, True, percentages[4]),
        (5, percentages[5], neutral_half + percentages[4], True, percentages[5]),
    )

    figure = go.Figure()
    for score, width, base, show_legend, total_percentage in segments:
        customdata = [
            [float(counts.loc[item, score]), float(total_percentage.loc[item])]
            for item in items
        ]
        figure.add_bar(
            y=display_items,
            x=width,
            base=base,
            name=labels[score],
            legendgroup=str(score),
            showlegend=show_legend,
            orientation="h",
            marker=dict(color=SCORE_COLORS[score], line=dict(color="white", width=2)),
            text=[f"{value:.0f}%" if value > 0 else "" for value in width],
            textposition="auto",
            insidetextfont=dict(color="white" if score in {1, 5} else "#262626"),
            outsidetextfont=dict(color="#262626"),
            customdata=customdata,
            hovertemplate=(
                f"%{{y}}<br>{labels[score]}: %{{customdata[1]:.1f}}% "
                "(%{customdata[0]:.0f} responses)<extra></extra>"
            ),
        )

    left_extent = float((percentages[1] + percentages[2] + neutral_half).max())
    right_extent = float((percentages[4] + percentages[5] + neutral_half).max())
    left_limit = min(100, max(10, math.ceil((left_extent + 2) / 10) * 10))
    right_limit = min(100, max(10, math.ceil((right_extent + 2) / 10) * 10))
    tick_values = list(range(-left_limit, right_limit + 1, 10))

    figure.add_vline(x=0, line_width=3, line_dash="dot", line_color="#161616")
    if labels.get(3) == "Neutral":
        figure.add_annotation(
            x=0,
            y=1.045,
            xref="x",
            yref="paper",
            text="Unfavorable ratings ←",
            showarrow=False,
            xanchor="right",
            xshift=-8,
            font=dict(size=12, color="#9f4607"),
        )
        figure.add_annotation(
            x=0,
            y=1.045,
            xref="x",
            yref="paper",
            text="→ Favorable ratings",
            showarrow=False,
            xanchor="left",
            xshift=8,
            font=dict(size=12, color="#315a9b"),
        )
    figure.update_layout(
        title=dict(text=f"{construct} ratings", x=0.5, xanchor="center", y=0.98, yanchor="top"),
        barmode="overlay",
        xaxis_title=None,
        yaxis_title="",
        height=max(390, len(items) * 62 + 125),
        legend=dict(orientation="h", yanchor="bottom", y=1.14, xanchor="center", x=0.5),
        plot_bgcolor="white",
        paper_bgcolor="white",
        bargap=0.28,
        margin=dict(l=12, r=18, t=135, b=48),
        uniformtext=dict(minsize=10, mode="hide"),
    )
    figure.update_xaxes(
        range=[-left_limit, right_limit],
        tickvals=tick_values,
        ticktext=[f"{abs(value)}%" for value in tick_values],
        showgrid=False,
        zeroline=False,
        showline=True,
        linecolor="#161616",
        ticks="outside",
    )
    figure.update_yaxes(autorange="reversed", showgrid=False)
    return figure
