# Authentic AI - Artifact Reliability V7

## Purpose

Artifact Reliability V7 fixes the recovery failure that occurred when a completed artifact version was recovered from an older compact-preview conversation and then passed back through the raw-source organiser.

## Root cause

A recovered artifact version already contains canonical Markdown with a title, sections, equations, tables, charts, page breaks, and conclusion. The previous pipeline treated that canonical document as raw source, organised it again, duplicated every section and chart, leaked Markdown markers, and then failed structural validation.

## Changes

- Detects recovered canonical artifact Markdown.
- Re-renders canonical artifact versions idempotently instead of organising them again.
- Repairs command-like legacy titles.
- Removes compact-preview markers and internal production-requirement sections.
- Removes duplicate equivalent chart blocks.
- Preserves all existing chapters, equations, examples, tables, visuals, glossary, and conclusion.
- Provides the exact structural or rendered quality error in failed job messages instead of a generic validation error.
- Adds a regression suite for canonical source recovery, legacy title repair, and PDF rendering.

## Recovery policy

1. Full source in the browser source vault is preferred.
2. A complete source snapshot is used when available.
3. A canonical artifact version is re-rendered directly when the original source is unavailable.
4. Canonical content is never routed through the raw-source organiser twice.
5. If neither full source nor a completed artifact version exists, the system requests the original source rather than inventing missing content.

## Verification target

The mathematics regression fixture produces a 40-page PDF with all 37 chapters, embedded source-derived visualisations, no duplicated sections, no hidden-preview marker, and zero quality errors or warnings.
