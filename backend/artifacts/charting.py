from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from artifacts.models import ChartBlock


def _display_labels(
    labels: tuple[str, ...],
) -> list[str]:
    return [
        label if len(label) <= 28 else f"{label[:25]}..."
        for label in labels
    ]


def render_chart_image(
    chart: ChartBlock,
    output_path: Path,
    *,
    dpi: int = 180,
) -> Path:
    if not chart.labels:
        raise ValueError(
            "Chart must contain at least one label."
        )

    if not chart.series:
        raise ValueError(
            "Chart must contain at least one data series."
        )

    for series in chart.series:
        if len(series.values) != len(chart.labels):
            raise ValueError(
                "Every chart series must match the label count."
            )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    figure_width = min(
        max(
            7.8,
            len(chart.labels) * 0.72,
        ),
        14.0,
    )

    figure = plt.figure(
        figsize=(figure_width, 4.8),
        dpi=dpi,
    )

    axis = figure.add_subplot(111)
    labels = _display_labels(chart.labels)
    positions = list(range(len(labels)))

    if chart.chart_type == "pie":
        if len(chart.series) != 1:
            raise ValueError(
                "Pie charts support exactly one data series."
            )

        axis.pie(
            chart.series[0].values,
            labels=labels,
            autopct="%1.1f%%",
            startangle=90,
        )

        axis.axis("equal")

    elif chart.chart_type == "bar":
        series_count = len(chart.series)
        group_width = 0.76
        bar_width = group_width / series_count

        for index, series in enumerate(chart.series):
            offset = (
                index - (series_count - 1) / 2
            ) * bar_width

            axis.bar(
                [position + offset for position in positions],
                series.values,
                width=bar_width,
                label=series.name,
            )

        axis.set_xticks(
            positions,
            labels,
            rotation=(35 if len(labels) > 7 else 0),
            ha=("right" if len(labels) > 7 else "center"),
        )

        axis.grid(
            True,
            axis="y",
            alpha=0.22,
        )

    else:
        for series in chart.series:
            axis.plot(
                positions,
                series.values,
                marker="o",
                linewidth=2,
                label=series.name,
            )

        axis.set_xticks(
            positions,
            labels,
            rotation=(35 if len(labels) > 7 else 0),
            ha=("right" if len(labels) > 7 else "center"),
        )

        axis.grid(
            True,
            alpha=0.22,
        )

    axis.set_title(
        chart.title,
        pad=14,
        fontweight="semibold",
    )

    if chart.chart_type != "pie" and len(chart.series) > 1:
        axis.legend(
            frameon=False,
        )

    figure.tight_layout()

    figure.savefig(
        output_path,
        dpi=dpi,
        bbox_inches="tight",
    )

    plt.close(figure)

    if (
        not output_path.exists()
        or output_path.stat().st_size <= 0
    ):
        raise RuntimeError(
            "Chart image generation failed."
        )

    return output_path