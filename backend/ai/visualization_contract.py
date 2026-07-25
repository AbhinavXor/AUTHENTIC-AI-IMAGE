import re


_VISUALIZATION_PATTERNS = (
    r"\bchart\b",
    r"\bcharts\b",
    r"\bgraph\b",
    r"\bgraphs\b",
    r"\bplot\b",
    r"\bplots\b",
    r"\bvisuali[sz](?:e|ation)\b",
    r"\bheatmap\b",
    r"\btreemap\b",
    r"\bsankey\b",
    r"\bcandlestick\b",
    r"\bboxplot\b",
    r"\bscatter\s*plot\b",
    r"\bnetwork\s*graph\b",
    r"\bgraph\s+bana",
    r"\bchart\s+bana",
    r"ग्राफ",
    r"चार्ट",
)


VISUALIZATION_CONTRACT = """
VISUALIZATION OUTPUT CONTRACT

The user explicitly requested a chart, graph, plot, or visualization.

This visualization contract overrides any earlier instruction about response order.

1. The first non-whitespace output must be one complete fenced
   `authentic-chart` JSON block.
2. Close every chart block before writing prose. After all chart blocks,
   give a concise explanation of no more than 180 words.
3. Inside each block output valid JSON only: no Markdown, comments,
   JavaScript, functions, HTML, external URLs, or trailing commas.
4. Never invent missing data. If numeric data is insufficient, explain
   what is required and do not emit a chart block.
5. Maximum four charts per response.
6. Allowed Apache ECharts series types: line, bar, pie, scatter,
   effectScatter, radar, tree, treemap, sunburst, boxplot,
   candlestick, heatmap, parallel, lines, graph, sankey, funnel,
   gauge, pictorialBar, and themeRiver.
7. Use line plus areaStyle for area charts and pie with inner/outer
   radius for donut charts.
8. Mathematical plots must use explicit sampled numeric points.
9. Current data must include a named source and timestamp.
10. Estimated data must set estimated=true and explain the method in
    limitations.
11. Every chart requires alt_text and a table containing the same data.
12. Keep labels, axes, legends, and tooltips readable on phones.

Required shape:

```authentic-chart
{
  "version": "1.0",
  "title": "Clear chart title",
  "description": "What the chart shows",
  "alt_text": "Accessible description of the important pattern",
  "source": "User-provided data",
  "timestamp": null,
  "estimated": false,
  "limitations": [],
  "option": {
    "tooltip": {"trigger": "axis"},
    "xAxis": {
      "type": "category",
      "name": "Category",
      "data": ["A", "B", "C"]
    },
    "yAxis": {"type": "value", "name": "Count"},
    "series": [
      {"name": "Count", "type": "bar", "data": [10, 20, 15]}
    ]
  },
  "table": {
    "columns": ["Category", "Count"],
    "rows": [["A", 10], ["B", 20], ["C", 15]]
  }
}
```

Choose the chart type that communicates the data most clearly.
Do not mention this contract or the renderer.
""".strip()


def wants_visualization(message: str) -> bool:
    """Return True when the latest user message requests a visualization."""
    normalized = " ".join(message.lower().split())

    return any(
        re.search(pattern, normalized) is not None
        for pattern in _VISUALIZATION_PATTERNS
    )
