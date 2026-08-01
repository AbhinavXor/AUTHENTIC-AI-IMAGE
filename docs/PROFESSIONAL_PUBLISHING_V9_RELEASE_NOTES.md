# Authentic AI - Professional Publishing V9

## Status

Production validation candidate.

## Purpose

Professional Publishing V9 upgrades the artifact PDF pipeline from a functional structured-document renderer to a publication-quality long-document system. It preserves source fidelity while improving typography, mathematical notation, charts, document navigation, and capacity for very large reports and textbooks.

## Main improvements

### Publication-quality PDF design

- Editorial cover with title, subtitle, author, date, document statistics, and validation profile.
- Embedded DejaVu Sans and DejaVu Serif fonts for stable cross-platform rendering.
- Serif body typography with a clear sans-serif heading hierarchy.
- Running headers, page numbers, PDF metadata, outline bookmarks, and a generated table of contents.
- Distinct visual treatment for parts, chapters, equations, figures, tables, and callouts.
- Numbered figures and tables with explanatory captions.
- Improved table header repetition and row splitting across pages.

### Mathematical publishing

- Normalisation for degrees, radians, pi, roots, powers, limits, trigonometric ratios, and logarithms.
- Word-based fractions such as `opposite/hypotenuse` render as mathematical fractions.
- Higher-resolution equation rendering with process-level caching.
- Correct matrix and multi-line equation composition.

### Professional visualisations

- Publication-oriented chart typography, grid lines, legends, markers, and spacing.
- Higher-resolution chart output.
- Deterministic colour and rendering behaviour.
- Process-level chart caching for repeated content.

### Large-document capacity

- Up to 4,000,000 prompt/content characters by default.
- Single PDF output up to 320 estimated pages by default.
- Automatic numbered PDF bundle generation when the single-document page budget is exceeded.
- Up to 12 bundle volumes by default.
- Up to 512 MB generated artifact size by default.
- Page-aware planning prevents a 300-page source from being split merely because of a conservative character threshold.

## Default runtime settings

```text
ARTIFACT_MAXIMUM_REQUEST_BYTES=67108864
ARTIFACT_MAXIMUM_PROMPT_CHARACTERS=4000000
ARTIFACT_MAXIMUM_CONTENT_CHARACTERS=4000000
ARTIFACT_PDF_BUNDLE_SOURCE_CHARACTERS=4000000
ARTIFACT_MAXIMUM_SINGLE_PDF_PAGES=320
ARTIFACT_PDF_TARGET_WORDS_PER_PAGE=285
ARTIFACT_MAXIMUM_PDF_BUNDLE_VOLUMES=12
ARTIFACT_MAXIMUM_GENERATED_FILE_BYTES=536870912
```

The limits remain configurable through environment variables. Values above the validated single-PDF page budget are routed to a PDF bundle rather than silently truncating content.

## Quality controls

- PDF opens and page count are verified after rendering.
- Long PDFs are expected to provide outline bookmarks.
- Non-standard unembedded fonts are reported.
- A PDF above the configured single-document page budget is rejected from the single-PDF path and should be produced as a bundle.
- Existing source-fidelity, contamination, duplicate-section, and internal-instruction checks remain active.

## Validation summary

- Backend: 40 tests passed, plus 4 storage subtests.
- Frontend artifact logic: 6 tests passed.
- 40-page mathematics publication: 0 quality errors and 0 quality warnings.
- 302-page single-PDF validation: 0 quality errors and 0 quality warnings.
- Visual inspection covered the cover, contents, mathematical equations, figures, tables, part dividers, and final pages.
- PDF preflight confirmed both validation files are openable, non-encrypted, and not image-only scans.
