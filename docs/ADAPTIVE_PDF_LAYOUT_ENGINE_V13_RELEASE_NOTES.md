# Authentic AI - Adaptive PDF Layout Engine V13

## Product changes

- PDF branding defaults to `none`.
- Repeated Authentic AI page headers, footers, watermarks, and generator credits are no longer injected into unbranded documents.
- AI requests now resolve a deterministic `ArtifactLayoutBrief` before rendering.
- Supported layout families:
  - executive report
  - research paper
  - academic textbook
  - technical specification
  - proposal document
  - data report
  - case study
  - modern summary
- Natural-language requests can select the layout family, branding level, and visual density without opening a large settings panel.
- Cover treatment, typography, section openers, running headers, table pages, chart pages, callouts, and footers are layout-family aware.
- Wide comparison tables automatically render on landscape pages.
- Table cells disable mid-word splitting and use content-aware column widths.
- Long chart category labels use wrapped labels or horizontal bars to avoid collisions.
- Revision, export, and duplicate operations preserve the original layout brief settings.

## Default publishing policy

- Branding: none
- Layout: auto-selected
- Visual density: auto/balanced
- Header: minimal or section-aware
- Footer: page number only
- Table of contents: enabled for documents with three or more sections
- Section openers: enabled when appropriate for the selected family

## Verification

- Full backend suite: 45 tests passed, including 4 storage subtests.
- Frontend artifact logic: 9 tests passed.
- TypeScript layout-intent files passed strict no-emit validation.
- Render validation confirmed an unbranded cover and landscape wide-table page.
