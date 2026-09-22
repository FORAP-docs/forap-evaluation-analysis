import pandas as pd

from forap_analysis.charts import divergent_likert_figure, pjbl_experience_figure, EXPERIENCE_ACTIVITIES


def test_experience_chart_preserves_counts_and_combines_side_labels():
    distributions = [[0, 0, 10, 17], [3, 4, 14, 6], [2, 1, 13, 11],
                     [7, 10, 7, 3], [0, 1, 15, 11]]
    frame = pd.DataFrame({
        key: [score for score, count in enumerate(counts) for _ in range(count)]
        for key, counts in zip(EXPERIENCE_ACTIVITIES, distributions)
    })
    figure = pjbl_experience_figure(frame)
    assert [trace.name for trace in figure.data] == ["None", "Limited", "Moderate", "Extensive"]
    assert [a.text for a in figure.layout.annotations[:10]] == [
        "0%", "100%", "26%", "74%", "11%", "89%", "63%", "37%", "4%", "96%",
    ]
    for row, counts in enumerate(distributions):
        assert [trace.customdata[row][0] for trace in figure.data] == counts
        assert abs(sum(trace.x[row] for trace in figure.data) - 100) < 1e-9
        assert abs(figure.data[1].base[row] + figure.data[1].x[row]) < 1e-9
        assert figure.data[2].base[row] == 0
    assert all(trace.text is None for trace in figure.data)


def test_experience_chart_excludes_missing_and_invalid_values():
    frame = pd.DataFrame({key: [0, 3, None, 9] for key in EXPERIENCE_ACTIVITIES})
    frame["pjbl_adopted"] = None
    figure = pjbl_experience_figure(frame)
    assert list(figure.data[0].customdata[0]) == [1, 2]
    assert figure.data[0].x[0] == 50
    assert figure.data[3].x[0] == 50
    assert any(a.y == "Adoption" and a.text == "No responses" for a in figure.layout.annotations)


def test_divergent_chart_matches_reference_layout():
    dist = pd.DataFrame(
        [
            {"key": "item", "item": "Example item", "score": score, "count": count, "percent": percent}
            for score, count, percent in [
                (1, 0, 0.0),
                (2, 1, 10.0),
                (3, 1, 10.0),
                (4, 6, 60.0),
                (5, 2, 20.0),
            ]
        ]
    )
    figure = divergent_likert_figure(dist, "Clarity", "agreement")
    assert len(figure.data) == 6
    assert figure.data[0].name == "Strongly Disagree"
    assert figure.data[2].name == "Neutral"
    assert figure.data[2].showlegend is True
    assert figure.data[3].showlegend is False
    assert list(figure.data[2].x) == [5.0]
    assert list(figure.data[3].x) == [5.0]
    assert list(figure.layout.xaxis.range) == [-20, 90]
    assert figure.layout.yaxis.autorange == "reversed"
    assert figure.layout.shapes[0].line.dash == "dot"
    assert figure.layout.shapes[0].line.width == 3
    assert [annotation.text for annotation in figure.layout.annotations] == [
        "Unfavorable ratings ←",
        "→ Favorable ratings",
    ]
    assert all(annotation.x == 0 for annotation in figure.layout.annotations)
    assert all(annotation.y > 1 for annotation in figure.layout.annotations)
    assert figure.layout.legend.y > figure.layout.annotations[0].y
    assert figure.layout.margin.b < figure.layout.margin.t


def test_legend_uses_scale_specific_wording():
    dist = pd.DataFrame(
        [
            {"key": "item", "item": "Example item", "score": score, "count": 1, "percent": 20.0}
            for score in range(1, 6)
        ]
    )
    figure = divergent_likert_figure(dist, "Student support", "usefulness")
    visible_names = [trace.name for trace in figure.data if trace.showlegend]
    assert visible_names == [
        "Not useful",
        "Slightly useful",
        "Moderately useful",
        "Very useful",
        "Extremely useful",
    ]
    assert list(figure.layout.annotations) == []


def test_effectiveness_scale_does_not_use_favorable_side_labels():
    dist = pd.DataFrame(
        [
            {"key": "item", "item": "Example item", "score": score, "count": 1, "percent": 20.0}
            for score in range(1, 6)
        ]
    )
    figure = divergent_likert_figure(dist, "Project attributes", "effectiveness")
    assert list(figure.layout.annotations) == []
