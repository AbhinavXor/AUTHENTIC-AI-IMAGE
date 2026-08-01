from __future__ import annotations

import json
import math
import re
from typing import Any

from artifacts.models import ChartBlock, ChartSeries

_AUTHENTIC_CHART = re.compile(
    r"```authentic-chart\s*([\s\S]*?)```",
    re.IGNORECASE,
)

_MAXIMUM_CHARTS = 8
_MAXIMUM_LABELS = 80
_MAXIMUM_TITLE_CHARACTERS = 160
_MAXIMUM_CAPTION_CHARACTERS = 700


def _is_record(value: object) -> bool:
    return isinstance(value, dict)


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    number = float(value)
    return number if math.isfinite(number) else None


def _clean_text(value: object, maximum: int) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())[:maximum]


def _chart_type(payload: dict[str, Any]) -> str:
    option = payload.get("option")
    if not isinstance(option, dict):
        return "bar"

    raw_series = option.get("series")
    series_items = raw_series if isinstance(raw_series, list) else [raw_series]
    series_type = ""

    for item in series_items:
        if isinstance(item, dict) and isinstance(item.get("type"), str):
            series_type = str(item["type"]).strip().casefold()
            break

    if series_type == "pie":
        return "pie"
    if series_type in {"area", "arealine"}:
        return "area"
    if series_type in {"unitcircle", "unit_circle"}:
        return "unit_circle"
    if series_type in {"slopefield", "slope_field", "directionfield", "direction_field"}:
        return "slope_field"
    if series_type in {"scatter", "effectscatter"}:
        return "scatter"
    if series_type in {
        "bar",
        "pictorialbar",
        "funnel",
        "gauge",
        "treemap",
        "sunburst",
        "heatmap",
        "boxplot",
        "candlestick",
    }:
        return "bar"
    return "line"


def _caption(payload: dict[str, Any]) -> str | None:
    parts = [
        _clean_text(payload.get("description"), 360),
        (
            f"Source: {_clean_text(payload.get('source'), 220)}"
            if _clean_text(payload.get("source"), 220)
            else ""
        ),
    ]

    limitations = payload.get("limitations")
    if isinstance(limitations, list):
        cleaned = [
            _clean_text(item, 160)
            for item in limitations[:4]
            if _clean_text(item, 160)
        ]
        if cleaned:
            parts.append("Limitations: " + "; ".join(cleaned))

    joined = " ".join(part for part in parts if part).strip()
    return joined[:_MAXIMUM_CAPTION_CHARACTERS] or None


def _from_table(
    payload: dict[str, Any],
    *,
    title: str,
    chart_type: str,
) -> ChartBlock | None:
    table = payload.get("table")
    if not isinstance(table, dict):
        return None

    columns = table.get("columns")
    rows = table.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        return None

    clean_columns = [
        _clean_text(column, 90)
        for column in columns[:12]
    ]
    if len(clean_columns) < 2:
        return None

    labels: list[str] = []
    numeric_columns: list[list[float]] = [
        [] for _ in clean_columns[1:]
    ]

    for raw_row in rows[:_MAXIMUM_LABELS]:
        if not isinstance(raw_row, list) or len(raw_row) < 2:
            continue

        label = _clean_text(raw_row[0], 90)
        values = [
            _finite_number(raw_row[index])
            if index < len(raw_row)
            else None
            for index in range(1, len(clean_columns))
        ]

        if not label or all(value is None for value in values):
            continue

        labels.append(label)
        for index, value in enumerate(values):
            numeric_columns[index].append(
                value if value is not None else 0.0
            )

    if not labels:
        return None

    series = tuple(
        ChartSeries(
            name=clean_columns[index + 1] or f"Series {index + 1}",
            values=tuple(values),
        )
        for index, values in enumerate(numeric_columns)
        if len(values) == len(labels)
    )

    if not series:
        return None

    if chart_type == "pie":
        series = (series[0],)

    return ChartBlock(
        title=title,
        labels=tuple(labels),
        series=series,
        chart_type=chart_type,  # type: ignore[arg-type]
        caption=_caption(payload),
        x_label=clean_columns[0] or None,
        y_label=(clean_columns[1] if len(clean_columns) == 2 else "Value"),
    )


def _x_axis_labels(option: dict[str, Any]) -> list[str]:
    raw_axis = option.get("xAxis")
    axis = raw_axis[0] if isinstance(raw_axis, list) and raw_axis else raw_axis
    if not isinstance(axis, dict):
        return []

    data = axis.get("data")
    if not isinstance(data, list):
        return []

    return [
        _clean_text(item, 90)
        for item in data[:_MAXIMUM_LABELS]
    ]


def _from_option(
    payload: dict[str, Any],
    *,
    title: str,
    chart_type: str,
) -> ChartBlock | None:
    option = payload.get("option")
    if not isinstance(option, dict):
        return None

    raw_series = option.get("series")
    series_items = raw_series if isinstance(raw_series, list) else [raw_series]
    series_items = [item for item in series_items if isinstance(item, dict)]
    if not series_items:
        return None

    if chart_type == "pie":
        data = series_items[0].get("data")
        if not isinstance(data, list):
            return None

        labels: list[str] = []
        values: list[float] = []
        for item in data[:_MAXIMUM_LABELS]:
            if not isinstance(item, dict):
                continue
            label = _clean_text(item.get("name"), 90)
            number = _finite_number(item.get("value"))
            if label and number is not None:
                labels.append(label)
                values.append(number)

        if not labels:
            return None

        return ChartBlock(
            title=title,
            labels=tuple(labels),
            series=(
                ChartSeries(
                    name=_clean_text(series_items[0].get("name"), 90) or "Value",
                    values=tuple(values),
                ),
            ),
            chart_type="pie",
            caption=_caption(payload),
            x_label=None,
            y_label=None,
        )

    labels = _x_axis_labels(option)
    normalized_series: list[ChartSeries] = []

    for index, item in enumerate(series_items[:8]):
        data = item.get("data")
        if not isinstance(data, list):
            continue

        values: list[float] = []
        derived_labels: list[str] = []

        for item_index, raw_value in enumerate(data[:_MAXIMUM_LABELS]):
            if isinstance(raw_value, dict):
                raw_value = raw_value.get("value")

            if isinstance(raw_value, list) and len(raw_value) >= 2:
                x_value = raw_value[0]
                y_value = _finite_number(raw_value[1])
                if y_value is None:
                    continue
                derived_labels.append(_clean_text(x_value, 90) or str(item_index + 1))
                values.append(y_value)
                continue

            number = _finite_number(raw_value)
            if number is not None:
                values.append(number)

        if not values:
            continue

        if not labels and derived_labels:
            labels = derived_labels
        if not labels:
            labels = [str(position + 1) for position in range(len(values))]

        usable = min(len(labels), len(values), _MAXIMUM_LABELS)
        labels = labels[:usable]
        values = values[:usable]

        normalized_series.append(
            ChartSeries(
                name=_clean_text(item.get("name"), 90) or f"Series {index + 1}",
                values=tuple(values),
            )
        )

    if not labels or not normalized_series:
        return None

    normalized_series = [
        series
        for series in normalized_series
        if len(series.values) == len(labels)
    ]
    if not normalized_series:
        return None

    return ChartBlock(
        title=title,
        labels=tuple(labels),
        series=tuple(normalized_series),
        chart_type=chart_type,  # type: ignore[arg-type]
        caption=_caption(payload),
        x_label="x",
        y_label="Value",
    )


def parse_authentic_chart_json(raw_json: str) -> ChartBlock | None:
    try:
        payload = json.loads(raw_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    title = _clean_text(payload.get("title"), _MAXIMUM_TITLE_CHARACTERS)
    if not title:
        return None

    chart_type = _chart_type(payload)
    return (
        _from_table(
            payload,
            title=title,
            chart_type=chart_type,
        )
        or _from_option(
            payload,
            title=title,
            chart_type=chart_type,
        )
    )


def _chart_fingerprint(raw_json: str) -> str | None:
    try:
        payload = json.loads(raw_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _block_raw_json(block: str) -> str:
    match = _AUTHENTIC_CHART.fullmatch(block.strip())
    return match.group(1).strip() if match else ""


def extract_authentic_chart_blocks(content: str | None) -> tuple[str, ...]:
    if not content:
        return ()

    blocks: list[str] = []
    fingerprints: set[str] = set()

    for match in _AUTHENTIC_CHART.finditer(content):
        raw_json = match.group(1).strip()
        fingerprint = _chart_fingerprint(raw_json)

        if (
            fingerprint is None
            or fingerprint in fingerprints
            or parse_authentic_chart_json(raw_json) is None
        ):
            continue

        blocks.append(
            "```authentic-chart\n" + raw_json + "\n```"
        )
        fingerprints.add(fingerprint)

        if len(blocks) >= _MAXIMUM_CHARTS:
            break

    return tuple(blocks)


def count_authentic_chart_blocks(content: str | None) -> int:
    return len(extract_authentic_chart_blocks(content))


def preserve_authentic_chart_blocks(
    source_content: str | None,
    document_content: str,
) -> str:
    source_blocks = extract_authentic_chart_blocks(source_content)
    if not source_blocks:
        return document_content.strip()

    existing_fingerprints = {
        fingerprint
        for block in extract_authentic_chart_blocks(document_content)
        if (fingerprint := _chart_fingerprint(_block_raw_json(block)))
    }
    missing = [
        block
        for block in source_blocks
        if (
            fingerprint := _chart_fingerprint(_block_raw_json(block))
        )
        not in existing_fingerprints
    ]
    if not missing:
        return document_content.strip()

    section_title = "## Source Visualizations"
    addition = "\n\n".join(missing)

    return (
        document_content.rstrip()
        + "\n\n"
        + section_title
        + "\n\n"
        + addition
        + "\n"
    )
