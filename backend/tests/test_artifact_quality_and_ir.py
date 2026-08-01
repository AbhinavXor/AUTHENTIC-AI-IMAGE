from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from artifacts.models import (
    ChartBlock,
    DiagramBlock,
    EquationBlock,
    PageBreakBlock,
    TableBlock,
)
from artifacts.parser import parse_artifact_document
from artifacts.quality import (
    clean_inline_markdown,
    equation_expression_is_structurally_valid,
    inspect_rendered_file,
    normalize_document_structure,
    normalize_markdown_source,
    validate_document_quality,
)
from artifacts.storage import ArtifactStorage
from artifacts.visualization_blocks import (
    extract_authentic_chart_blocks,
    parse_authentic_chart_json,
    preserve_authentic_chart_blocks,
)


SOURCE = """
# Energy Operations Review

## Executive Summary

The source describes a controlled energy operations review for a regional facility. It explains the present process, the measurable risks, and the planned operational controls without inventing external evidence.

## Operating Flow

```diagram
Request received -> Validate inputs -> Approve plan -> Publish result
```

## Control Matrix

| Control | Outcome |
|---|---|
| Validate inputs | Prevent invalid calculations |
| Preserve audit records | Support traceability |

## Workload Visualization

```authentic-chart
{"version":"1.0","title":"Manual versus Automated Workload","description":"Comparison of modeled processing hours.","source":"User-provided scenario","estimated":false,"limitations":[],"option":{"xAxis":{"type":"category","data":["Manual","Automated"]},"yAxis":{"type":"value","name":"Hours"},"series":[{"name":"Hours","type":"bar","data":[100,35]}]},"table":{"columns":["Mode","Hours"],"rows":[["Manual",100],["Automated",35]]}}
```

## Calculation

$$E = P \\times t$$

<!-- pagebreak -->

## Recommendations

- Validate each input before calculation.
- Preserve an audit record for every approved result.
- Review exceptions before publication.

## Conclusion

The proposed process improves reliability while keeping human approval at the required control point.
"""


def test_normalization_removes_visual_markdown_noise() -> None:
    normalized = normalize_markdown_source(
        "# Test\n\n---\n\n**Important** result."
    )

    assert "---" not in normalized


def test_normalization_repairs_provider_markdown_and_html_wrappers() -> None:
    source = """```markdown
# Systems Report

<div><h2>Architecture</h2><p>The <strong>service</strong> is ready.</p></div>

<table><tr><th>Metric</th><th>Value</th></tr><tr><td>Latency</td><td>5 ms</td></tr></table>
```

```html
<div class=\"example\">Intentional HTML code</div>
```
"""
    normalized = normalize_markdown_source(source)

    assert normalized.startswith("# Systems Report")
    assert "## Architecture" in normalized
    assert "| Metric | Value |" in normalized
    assert "| Latency | 5 ms |" in normalized
    assert '```html\n<div class="example">' in normalized


def test_normalization_unwraps_outer_markdown_around_nested_code() -> None:
    source = """```markdown
# Engineering Guide

## Example

```html
<section class="demo">Keep this literal HTML code.</section>
```

<table><tr><th>Input</th><th>Output</th></tr><tr><td>A</td><td>B</td></tr></table>
```"""
    normalized = normalize_markdown_source(source)

    assert normalized.startswith("# Engineering Guide")
    assert '```html\n<section class="demo">' in normalized
    assert "| Input | Output |" in normalized
    assert "<table" not in normalized


def test_structural_quality_ignores_markup_inside_code_blocks() -> None:
    source = """# Developer Guide

## Overview

This guide contains legitimate code examples for students.

```html
<div class=\"card\">**literal markdown token**</div>
```

## Result

The visible explanation is clean and complete.
"""
    document = parse_artifact_document(source)
    quality = validate_document_quality(document)

    assert quality.error_count == 0, quality.to_dict()


def test_visible_html_and_unbalanced_markdown_are_repaired_before_validation() -> None:
    source = """# Project Report

## Summary

<div>The **professional report includes <span>validated content</span>.</div>

## Conclusion

The document is ready for faculty review.**
"""
    document = parse_artifact_document(source)
    quality = validate_document_quality(document)
    visible = " ".join(
        block.text
        for section in document.sections
        for block in section.blocks
        if hasattr(block, "text")
    )

    assert quality.error_count == 0, quality.to_dict()
    assert "<div" not in visible
    assert "<span" not in visible
    assert "**" not in visible


def test_final_ir_normalization_repairs_all_visible_fields_but_not_code() -> None:
    document = parse_artifact_document(
        """# Field Repair

## Evidence

The source contains enough useful content for a complete professional quality
check of visible fields and literal implementation examples.

```html
<div>**keep literal syntax**</div>
```

## Conclusion

The validation path remains deterministic and safe.
"""
    )
    section = document.sections[0]
    deliberately_dirty = replace(
        document,
        subtitle="<span>**Academic edition**</span>",
        sections=(
            replace(section, title="<b>**Evidence**</b>"),
            *document.sections[1:],
        ),
    )

    repaired = normalize_document_structure(deliberately_dirty)
    code = next(
        block.code
        for current_section in repaired.sections
        for block in current_section.blocks
        if hasattr(block, "code")
    )

    assert repaired.subtitle == "Academic edition"
    assert repaired.sections[0].title == "Evidence"
    assert "<div>**keep literal syntax**</div>" in code


def test_parser_builds_structured_equation_diagram_and_page_break() -> None:
    document = parse_artifact_document(SOURCE)
    blocks = [
        block
        for section in document.sections
        for block in section.blocks
    ]

    assert any(isinstance(block, DiagramBlock) for block in blocks)
    assert any(isinstance(block, ChartBlock) for block in blocks)
    assert any(isinstance(block, EquationBlock) for block in blocks)
    assert any(isinstance(block, TableBlock) for block in blocks)
    assert any(isinstance(block, PageBreakBlock) for block in blocks)

    report = validate_document_quality(
        document,
        source_snapshot={
            "summary": "Energy operations review",
            "content": SOURCE,
        },
    )

    assert report.error_count == 0


def test_engineering_equations_allow_labels_units_and_latex_commands() -> None:
    valid_expressions = (
        r"\text{Mean waiting time}\quad W_q = \frac{P(W>0)}{c\mu-\lambda}",
        r"P_0 = \left[\sum_{n=0}^{c-1}\frac{a^n}{n!}+\frac{a^c}{c!(1-\rho)}\right]^{-1}",
        r"c_1=8,\quad \lambda_1=36,\quad \mu_1=25,\quad \rho_1=0.18",
        r"\Delta W_q=W_{q,0}-W_{q,1}=12.4\ \mathrm{minutes}",
        r"\text{Total annual benefit}=630000+120000=750000",
    )

    for expression in valid_expressions:
        assert equation_expression_is_structurally_valid(expression)


def test_equation_quality_still_rejects_prose_wrapped_as_display_math() -> None:
    invalid_expressions = (
        "The legacy system has a higher waiting time because demand exceeds capacity.",
        "The result is x = 9 and it is correct.",
        r"\text{This is a complete prose sentence without a mathematical expression}",
    )

    for expression in invalid_expressions:
        assert not equation_expression_is_structurally_valid(expression)


def test_inline_greek_symbols_are_professional_in_headings_and_toc() -> None:
    assert clean_inline_markdown(
        r"AI system (c_1 = 8, \lambda_1 = 36, \mu_1 = 25, \rho_1 = 0.18)"
    ) == "AI system (c₁ = 8, λ₁ = 36, μ₁ = 25, ρ₁ = 0.18)"


def test_all_renderers_reopen_and_pass_quality(tmp_path: Path) -> None:
    storage = ArtifactStorage(
        tmp_path / "artifacts",
        retention_hours=1,
        maximum_file_bytes=20 * 1024 * 1024,
    )
    document = parse_artifact_document(SOURCE)

    for format_value in ("pdf", "docx", "pptx"):
        stored = storage.create(
            document,
            format=format_value,
            filename=f"Energy Operations.{format_value}",
        )
        report = inspect_rendered_file(
            stored.path,
            format=format_value,
        )

        assert stored.path.is_file()
        assert stored.size_bytes > 500
        assert report.error_count == 0
        assert report.page_or_slide_count >= 1

def test_visualization_preservation_deduplicates_equivalent_json() -> None:
    source = """
```authentic-chart
{"title":"Zero Baseline","option":{"xAxis":{"data":["A","B"]},"series":[{"type":"bar","name":"Value","data":[0,0]}]},"table":{"columns":["Category","Value"],"rows":[["A",0],["B",0]]}}
```
""".strip()
    reformatted = """
# Report

## Visualization

```authentic-chart
{
  "table": {"rows": [["A", 0], ["B", 0]], "columns": ["Category", "Value"]},
  "option": {"series": [{"data": [0, 0], "name": "Value", "type": "bar"}], "xAxis": {"data": ["A", "B"]}},
  "title": "Zero Baseline"
}
```
""".strip()

    raw_json = extract_authentic_chart_blocks(source)[0]
    raw_json = raw_json.removeprefix("```authentic-chart\n").removesuffix("\n```")
    parsed = parse_authentic_chart_json(raw_json)

    assert parsed is not None
    assert parsed.series[0].values == (0.0, 0.0)
    assert preserve_authentic_chart_blocks(source, reformatted) == reformatted
