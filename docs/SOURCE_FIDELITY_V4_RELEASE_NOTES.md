# Authentic AI Source Fidelity V4

## Purpose

Source Fidelity V4 prevents long pasted or uploaded source material from being compressed into a short, unrelated, or incomplete artifact.

## Core behavior

- Detects explicit preservation instructions such as authoritative source, preserve all content, do not remove details, and Hinglish equivalents.
- Automatically selects lossless preservation for source bodies above 8,000 characters unless the user explicitly requests summarization or shortening.
- Separates trailing PDF-generation instructions from the authoritative document body.
- Converts numbered source chapters into professional document sections without asking an external model to rewrite or summarize them.
- Retains equations, examples, warnings, lists, and verification steps.
- Adds deterministic page breaks for long multi-chapter documents.
- Derives supported charts only from explicit formulas and numeric examples in the source.
- Preserves existing `authentic-chart` visualizations.
- Rejects output that fails token, heading, character-retention, or minimum-page fidelity checks.
- Stores the complete explicit source snapshot for future revisions and exports.

## Revision safety

- `Add a comparison table and create a new version` is handled additively and deterministically.
- Existing content is preserved and a new comparison-table section is appended.
- Non-destructive model revisions are rejected if they remove too much of the current artifact.
- Explicit shortening or summarization requests remain allowed.

## Rendering improvements

- Inline `$...$` markers are removed from normal PDF text.
- Common LaTeX commands are converted to readable symbols in prose.
- Multi-line `$$...$$` equation blocks are parsed correctly.
- Source-derived charts are embedded inside PDF, DOCX, PPTX, or PDF-volume outputs.

## Validation baseline

The supplied 37-chapter mathematics source was rendered as a 43-page PDF with:

- all 37 numbered chapters;
- equations and worked examples;
- final verification requirements;
- eight source-derived charts;
- no raw dollar-sign math markers;
- 40 outline entries;
- zero quality errors or warnings.
