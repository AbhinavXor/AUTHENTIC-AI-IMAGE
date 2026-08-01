from __future__ import annotations

import hashlib
import math
import textwrap
from collections import OrderedDict
from pathlib import Path
from threading import RLock

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from artifacts.models import ChartBlock


_CHART_RENDER_LOCK = RLock()
_CHART_PNG_CACHE: OrderedDict[str, bytes] = OrderedDict()
_MAXIMUM_CACHED_CHARTS = 128

_PALETTE = (
    "#147D6D",
    "#315C8C",
    "#D17A22",
    "#7A4EAB",
    "#B94E5D",
)


def _display_labels(labels: tuple[str, ...]) -> list[str]:
    displayed: list[str] = []
    for label in labels:
        normalized = " ".join(label.split())
        if len(normalized) > 42:
            normalized = normalized[:39].rstrip() + "..."
        displayed.append("\n".join(textwrap.wrap(normalized, width=18)) or normalized)
    return displayed


def _prefer_horizontal_bar(labels: tuple[str, ...]) -> bool:
    if not labels or len(labels) > 12:
        return False
    average = sum(len(label) for label in labels) / len(labels)
    longest = max(len(label) for label in labels)
    return average >= 15 or longest >= 24

def _numeric_labels(labels: tuple[str, ...]) -> list[float] | None:
    result: list[float] = []
    for label in labels:
        value = label.replace("°", "").strip()
        try:
            result.append(float(value))
        except ValueError:
            return None
    return result


def _style_axis(axis, chart: ChartBlock) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_color("#A7B0BE")
    axis.spines["bottom"].set_color("#A7B0BE")
    axis.tick_params(
        colors="#475467",
        labelsize=8.6,
        width=0.6,
        length=3,
    )
    axis.set_facecolor("#FCFDFE")
    axis.margins(x=0.025)
    if chart.x_label:
        axis.set_xlabel(
            chart.x_label,
            fontsize=9.2,
            color="#344054",
            labelpad=8,
        )
    if chart.y_label:
        axis.set_ylabel(
            chart.y_label,
            fontsize=9.2,
            color="#344054",
            labelpad=8,
        )


def _render_unit_circle(axis, chart: ChartBlock) -> None:
    if len(chart.series) < 2:
        raise ValueError(
            "Unit-circle charts require cosine and sine series."
        )
    x_values = chart.series[0].values
    y_values = chart.series[1].values
    axis.plot(
        x_values,
        y_values,
        linewidth=2.1,
        color=_PALETTE[0],
    )
    axis.scatter(
        x_values,
        y_values,
        s=24,
        color=_PALETTE[1],
        edgecolor="white",
        linewidth=0.5,
        zorder=3,
    )
    for label, x_value, y_value in zip(
        chart.labels,
        x_values,
        y_values,
    ):
        if label in {"0°", "90°", "180°", "270°", "360°"}:
            axis.annotate(
                label,
                (x_value, y_value),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=7.8,
                color="#475467",
            )
    axis.axhline(0, color="#A7B0BE", linewidth=0.8)
    axis.axvline(0, color="#A7B0BE", linewidth=0.8)
    axis.set_aspect("equal", adjustable="box")
    axis.set_xlim(-1.18, 1.18)
    axis.set_ylim(-1.18, 1.18)
    axis.set_xlabel("cos(θ)")
    axis.set_ylabel("sin(θ)")
    axis.grid(True, alpha=0.14, linewidth=0.6)


def _render_slope_field(axis, chart: ChartBlock) -> None:
    if not chart.series:
        raise ValueError("Slope-field chart requires a slope series.")
    x_values: list[float] = []
    y_values: list[float] = []
    slopes: list[float] = []
    for label, slope in zip(
        chart.labels,
        chart.series[0].values,
    ):
        try:
            raw_x, raw_y = label.split(",", 1)
            x_values.append(float(raw_x))
            y_values.append(float(raw_y))
            slopes.append(float(slope))
        except (ValueError, TypeError):
            continue
    if not x_values:
        raise ValueError(
            "Slope-field labels must contain x,y coordinates."
        )
    lengths = [math.sqrt(1 + slope * slope) for slope in slopes]
    u = [0.70 / length for length in lengths]
    v = [
        0.70 * slope / length
        for slope, length in zip(slopes, lengths)
    ]
    axis.quiver(
        x_values,
        y_values,
        u,
        v,
        angles="xy",
        scale_units="xy",
        scale=1,
        width=0.0055,
        color=_PALETTE[1],
        pivot="middle",
    )
    axis.axhline(0, color="#A7B0BE", linewidth=0.8)
    axis.axvline(0, color="#A7B0BE", linewidth=0.8)
    axis.set_xlim(min(x_values) - 0.6, max(x_values) + 0.6)
    axis.set_ylim(min(y_values) - 0.6, max(y_values) + 0.6)
    axis.set_xlabel("x")
    axis.set_ylabel("y")
    axis.grid(True, alpha=0.16, linewidth=0.6)


def render_chart_image(
    chart: ChartBlock,
    output_path: Path,
    *,
    dpi: int = 220,
) -> Path:
    if not chart.labels:
        raise ValueError("Chart must contain at least one label.")
    if not chart.series:
        raise ValueError("Chart must contain at least one data series.")
    for series in chart.series:
        if len(series.values) != len(chart.labels):
            raise ValueError(
                "Every chart series must match the label count."
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cache_payload = repr(
        (
            chart.title,
            chart.labels,
            tuple((series.name, series.values) for series in chart.series),
            chart.chart_type,
            chart.caption,
            chart.x_label,
            chart.y_label,
            dpi,
        )
    )
    cache_key = hashlib.sha256(cache_payload.encode("utf-8")).hexdigest()
    with _CHART_RENDER_LOCK:
        cached = _CHART_PNG_CACHE.get(cache_key)
        if cached is not None:
            _CHART_PNG_CACHE.move_to_end(cache_key)
            output_path.write_bytes(cached)
            return output_path

    rc = {
        "font.family": "DejaVu Sans",
        "axes.titleweight": "semibold",
        "axes.titlesize": 12.2,
        "axes.labelsize": 9.2,
        "legend.fontsize": 8.2,
        "figure.facecolor": "white",
    }
    with plt.rc_context(rc):
        horizontal_bar = (
            chart.chart_type == "bar"
            and _prefer_horizontal_bar(chart.labels)
        )
        figure_height = (
            max(4.15, 2.4 + len(chart.labels) * 0.42)
            if horizontal_bar
            else 4.35
        )
        figure = plt.figure(
            figsize=(7.35, figure_height),
            dpi=dpi,
            facecolor="white",
        )
        axis = figure.add_subplot(111)
        _style_axis(axis, chart)

        labels = _display_labels(chart.labels)
        numeric_positions = _numeric_labels(chart.labels)
        positions = (
            numeric_positions
            if numeric_positions is not None
            else list(range(len(labels)))
        )

        if chart.chart_type == "unit_circle":
            _render_unit_circle(axis, chart)
        elif chart.chart_type == "slope_field":
            _render_slope_field(axis, chart)
        elif chart.chart_type == "pie":
            if len(chart.series) != 1:
                raise ValueError(
                    "Pie charts support exactly one data series."
                )
            axis.pie(
                chart.series[0].values,
                labels=labels,
                autopct="%1.1f%%",
                startangle=90,
                colors=_PALETTE,
                textprops={"fontsize": 8.2, "color": "#344054"},
                wedgeprops={
                    "linewidth": 0.8,
                    "edgecolor": "white",
                },
            )
            axis.axis("equal")
        elif chart.chart_type == "bar":
            series_count = len(chart.series)
            group_width = 0.70
            bar_width = group_width / series_count
            if horizontal_bar:
                for index, series in enumerate(chart.series):
                    offset = (
                        index - (series_count - 1) / 2
                    ) * bar_width
                    axis.barh(
                        [position + offset for position in positions],
                        series.values,
                        height=bar_width,
                        label=series.name,
                        color=_PALETTE[index % len(_PALETTE)],
                        alpha=0.92,
                        edgecolor="white",
                        linewidth=0.55,
                    )
                axis.set_yticks(positions, labels)
                axis.invert_yaxis()
                axis.grid(True, axis="x", alpha=0.16, linewidth=0.6)
            else:
                for index, series in enumerate(chart.series):
                    offset = (
                        index - (series_count - 1) / 2
                    ) * bar_width
                    axis.bar(
                        [position + offset for position in positions],
                        series.values,
                        width=bar_width,
                        label=series.name,
                        color=_PALETTE[index % len(_PALETTE)],
                        alpha=0.92,
                        edgecolor="white",
                        linewidth=0.55,
                    )
                axis.grid(True, axis="y", alpha=0.16, linewidth=0.6)
        elif chart.chart_type == "area":
            series = chart.series[0]
            axis.plot(
                positions,
                series.values,
                linewidth=2.05,
                color=_PALETTE[0],
                label=series.name,
            )
            axis.fill_between(
                positions,
                series.values,
                0,
                color=_PALETTE[0],
                alpha=0.18,
            )
            axis.axhline(0, color="#A7B0BE", linewidth=0.8)
            axis.grid(True, alpha=0.14, linewidth=0.6)
        elif chart.chart_type == "scatter":
            for index, series in enumerate(chart.series):
                if index == 0:
                    axis.scatter(
                        positions,
                        series.values,
                        s=34,
                        color=_PALETTE[index],
                        edgecolor="white",
                        linewidth=0.55,
                        label=series.name,
                        zorder=3,
                    )
                else:
                    axis.plot(
                        positions,
                        series.values,
                        linewidth=2.05,
                        color=_PALETTE[index],
                        label=series.name,
                    )
            axis.grid(True, alpha=0.16, linewidth=0.6)
        else:
            for index, series in enumerate(chart.series):
                axis.plot(
                    positions,
                    series.values,
                    marker="o",
                    markersize=3.8,
                    linewidth=1.95,
                    color=_PALETTE[index % len(_PALETTE)],
                    label=series.name,
                )
            axis.grid(True, alpha=0.16, linewidth=0.6)

        if chart.chart_type not in {
            "unit_circle",
            "slope_field",
            "pie",
        } and not horizontal_bar:
            if numeric_positions is None:
                axis.set_xticks(
                    positions,
                    labels,
                    rotation=(30 if len(labels) > 8 else 0),
                    ha=("right" if len(labels) > 8 else "center"),
                )
            elif len(positions) <= 16:
                axis.set_xticks(positions)

        axis.set_title(
            chart.title,
            pad=12,
            color="#162033",
        )
        if chart.chart_type != "pie" and len(chart.series) > 1:
            handles, legend_labels = axis.get_legend_handles_labels()
            if handles and legend_labels:
                axis.legend(
                    frameon=False,
                    loc="best",
                    handlelength=2.1,
                )

        figure.tight_layout(pad=1.25)
        figure.savefig(
            output_path,
            dpi=dpi,
            bbox_inches="tight",
            facecolor="white",
        )
        plt.close(figure)

    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise RuntimeError("Chart image generation failed.")
    with _CHART_RENDER_LOCK:
        _CHART_PNG_CACHE[cache_key] = output_path.read_bytes()
        _CHART_PNG_CACHE.move_to_end(cache_key)
        while len(_CHART_PNG_CACHE) > _MAXIMUM_CACHED_CHARTS:
            _CHART_PNG_CACHE.popitem(last=False)
    return output_path
