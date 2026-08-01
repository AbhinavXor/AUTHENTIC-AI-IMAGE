# Authentic AI Artifact UX V2

## Release purpose

This release corrects the artifact timeline, revision routing, verified download experience, and visualization preservation behavior discovered during the Phase 1–6 browser test.

## Problems corrected

1. A rename command updated only the earlier artifact card and did not provide a new result card at the latest chat position.
2. Requests such as “Add a comparison table and create a new version” could be routed to normal chat, allowing the language model to produce a non-functional Markdown download link instead of a real artifact operation.
3. A new or renamed artifact could use stale client metadata during preview or download.
4. Browser popup restrictions could prevent an asynchronously opened PDF preview.
5. `authentic-chart` visualization blocks were treated as generic code during artifact composition and rendering.
6. A model revision could accidentally omit a source visualization.

## Implemented behavior

### Artifact timeline

- Rename, revision, export, duplicate, and restore commands now create a fresh, verified artifact card at the latest position in the chat.
- Earlier cards for the same artifact are synchronized with current metadata so subsequent operations do not use a stale version.
- Revision responses identify the new version and keep prior versions accessible through Version history.
- Delete removes every visible card reference for the deleted artifact.

### Command routing

The artifact command router now recognizes direct and indirect revision language, including:

- Add a comparison table and create a new version.
- Add the graph and prepare an updated version.
- Create a revised version.
- Remove the chart.
- Naya version banao.

These commands are executed by the artifact lifecycle service instead of normal chat generation.

### Verified open and download

- Current metadata is refreshed before opening or downloading the current artifact.
- Historical version downloads continue to use the exact selected version.
- The PDF preview window is created synchronously before the network request, avoiding browser popup blocking caused by delayed `window.open` calls.
- Empty downloads are rejected with a clear error.
- Model-authored “Download PDF” style links are rendered as non-actionable text unless a verified artifact card exists.

### Visualization preservation

- Recent generated visualizations and their related prompts are retained in the artifact source snapshot.
- Snapshot compaction never cuts an `authentic-chart` JSON fence in the middle.
- The backend parses valid `authentic-chart` blocks into structured chart IR.
- Bar, line, pie, and scatter charts render into PDF, DOCX, and PPTX.
- Charts are deterministically reattached if the AI provider omits them during initial composition or revision.
- Semantically identical chart JSON is deduplicated even when whitespace or key order differs.
- A quality gate fails artifact generation when required source charts are missing.

## Validation

- Backend: 15 tests passed, including API lifecycle, version downloads, chart parsing, chart deduplication, zero-value chart data, and source visualization preservation.
- Frontend artifact logic: 4 tests passed, including the exact failed revision phrase and visualization source retention.
- TypeScript source: full local semantic check completed with dependency interface stubs.
- Render validation: PDF, DOCX, and PPTX were created and reopened successfully with a real chart block; PDF visual inspection confirmed the chart was rendered in the document.

The installer runs the repository’s real backend tests, frontend tests, and Vite production build on the target Mac before accepting the update.
